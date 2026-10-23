// Session-only, scope-owned portability operations. Never send file bytes to chat.
const bookmarkDataDrafts=new Map();
function createLibraryData(React,adapter,components){
 const {createElement:h,useEffect,useRef,useState}=React,Button=components.Button||'button',Dialog=createLibraryDialog(React,components);
 const MAX=512*1024*1024,CHUNK=32768;
 const fresh=()=>({format:'bundle',includeTrash:false,exportRequest:null,artifact:null,file:null,uploadRequest:null,upload:null,previousUploads:[],preview:null,confirmed:false,restoreRequest:null,restore:null,restoreRetry:false,lookupKind:'export',lookupId:'',inspection:null,confirmClose:false,error:'',busy:'',epoch:0,task:null,completion:0,listeners:new Set()});
 const hash=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),value=>value.toString(16).padStart(2,'0')).join('');
 return function LibraryData({ctx,scope,libraryId,open,onClose,onChanged}){
  const key=JSON.stringify([scope,libraryId]);if(!bookmarkDataDrafts.has(key))bookmarkDataDrafts.set(key,fresh());
  const state=bookmarkDataDrafts.get(key),owner=useRef(null),callbacks=useRef(null),[,paint]=useState(0);callbacks.current={onClose,onChanged};
  const current=()=>owner.current?.state===state&&owner.current.active&&(!adapter.currentScope||adapter.currentScope()===scope);
  const changed=()=>bookmarkDraftChanged(state),owned=async(route,init)=>(await bookmarkOwnedRequest(adapter,ctx,scope,route,init)).result;
  useEffect(()=>{const lease={state,active:true};owner.current=lease;let completion=state.completion;
   const listener=()=>{if(!current())return;paint(n=>n+1);if(completion!==state.completion){completion=state.completion;callbacks.current.onChanged?.();}};
   state.listeners.add(listener);return()=>{lease.active=false;if(state.task)state.task.stopped=true;state.listeners.delete(listener);};
  },[state]);
  function begin(kind){if(state.busy||!current())return null;const task={epoch:++state.epoch,stopped:false};state.task=task;state.busy=kind;state.error='';changed();return task;}
  const valid=task=>state.task===task&&task.epoch===state.epoch&&!task.stopped&&current();
  const exportLocked=()=>!!(state.exportRequest&&(!state.artifact||!['ready','failed'].includes(state.artifact.state)));
  function finish(task){if(state.task===task){state.busy='';state.task=null;changed();}}
  async function generate(){
   if(exportLocked())return;const task=begin('generate');if(!task)return;
   state.exportRequest={format:state.format,include_trash:state.format==='html'&&state.includeTrash,request_id:crypto.randomUUID()};state.artifact=null;changed();
   try{state.artifact=await owned('/exports',{method:'POST',body:state.exportRequest});}
   catch(error){state.error='Export outcome is uncertain. Inspect its request ID before another generation. '+error.message;}
   finally{finish(task);}
  }
  async function download(selected=null){
   const artifact=selected||state.artifact;if(artifact?.state!=='ready')return;const task=begin('download');if(!task)return;let url=null;
   try{
    if(!Number.isSafeInteger(artifact.size)||artifact.size<1||artifact.size>MAX||!/^[a-f0-9]{64}$/.test(artifact.digest))throw Error('Export metadata exceeds browser limits or has no integrity digest.');
    const bytes=new Uint8Array(artifact.size);let offset=0;
    while(offset<bytes.length){
     const part=await owned('/exports/'+encodeURIComponent(artifact.id)+'?offset='+offset);if(!valid(task))return;
     if(part.artifact_id!==artifact.id||part.offset!==offset||part.size!==artifact.size||part.digest!==artifact.digest||typeof part.content_base64!=='string'||part.content_base64.length>43692)throw Error('Export chunk metadata is inconsistent.');
     const chunk=Uint8Array.from(atob(part.content_base64),char=>char.charCodeAt(0));
     if(!chunk.length||chunk.length>CHUNK||offset+chunk.length>bytes.length||part.next_offset!==offset+chunk.length||part.eof!==(part.next_offset===bytes.length))throw Error('Export chunk offset or size is invalid.');
     bytes.set(chunk,offset);offset=part.next_offset;
    }
    const actual=await hash(bytes);if(!valid(task))return;if(actual!==artifact.digest)throw Error('Export integrity verification failed. Nothing was downloaded.');
    url=URL.createObjectURL(new Blob([bytes],{type:artifact.format==='html'?'text/html;charset=utf-8':'application/zip'}));
    const anchor=document.createElement('a');anchor.href=url;anchor.download=artifact.filename;anchor.click();
   }catch(error){if(state.task===task)state.error=error.message;}finally{if(url)URL.revokeObjectURL(url);finish(task);}
  }
  function retainUpload(){if(state.uploadRequest&&!state.previousUploads.some(request=>request.request_id===state.uploadRequest.request_id))state.previousUploads.push({...state.uploadRequest,id:state.upload?.id});}
  function selectFile(event){
   const file=event.currentTarget.files?.[0];if(!file||state.busy||state.restoreRequest||!current())return;
   if(!Number.isSafeInteger(file.size)||file.size<1||file.size>MAX){state.error='Choose a nonempty backup no larger than 512 MiB.';changed();return;}
   retainUpload();state.epoch++;state.file=file;state.uploadRequest=null;state.upload=null;state.preview=null;state.confirmed=false;state.error='';changed();
  }
  function uploadMetadata(value,request){
   if(!value||typeof value.id!=='string'||value.size!==request.size||value.digest!==request.digest||!Number.isSafeInteger(value.offset)||value.offset<0||value.offset>request.size||(state.upload&&value.id!==state.upload.id))throw Error('Upload identity, integrity or offset is inconsistent.');
   return value;
  }
  async function upload(){
   if(!state.file||state.restoreRequest)return;const task=begin('upload');if(!task)return;const file=state.file;
   try{
    const buffer=await file.arrayBuffer();if(!valid(task))return;
    if(buffer.byteLength!==file.size)throw Error('The selected file size changed.');
    const bytes=new Uint8Array(buffer),digest=await hash(bytes);if(!valid(task))return;
    if(state.uploadRequest&&state.uploadRequest.digest!==digest)throw Error('The selected file no longer matches this upload.');
    if(!state.uploadRequest)state.uploadRequest={size:file.size,digest,request_id:crypto.randomUUID()};changed();
    // Explicit resume reuses upload_create to read its authoritative offset.
    const metadata=uploadMetadata(await owned('/backups/uploads',{method:'POST',body:state.uploadRequest}),state.uploadRequest);
    if(state.task!==task)return;state.upload=metadata;changed();if(!valid(task))return;
    while(state.upload.offset<bytes.length){
     const offset=state.upload.offset,chunk=bytes.subarray(offset,Math.min(offset+CHUNK,bytes.length));
     const content_base64=btoa(Array.from(chunk,value=>String.fromCharCode(value)).join(''));
     const result=uploadMetadata(await owned('/backups/uploads/'+encodeURIComponent(state.upload.id)+'/chunks',{method:'POST',body:{offset,content_base64}}),state.uploadRequest);
     if(state.task!==task)return;if(result.offset!==offset+chunk.length)throw Error('Upload chunk was not acknowledged at the expected offset.');state.upload=result;changed();if(!valid(task))return;
    }
    const preview=await owned('/backups/preview',{method:'POST',body:{upload_id:state.upload.id}});if(!valid(task))return;
    if(preview.input_digest!==state.uploadRequest.digest||typeof preview.preview_id!=='string'||typeof preview.empty_target!=='boolean')throw Error('Backup preview integrity is inconsistent.');
    state.preview=preview;state.confirmed=false;changed();
   }catch(error){if(state.task===task)state.error='Upload or preview stopped: '+error.message+' Resume explicitly with this same file; no restore was sent.';}
   finally{finish(task);}
  }
  async function restore(retry=false){
   if(!state.preview?.empty_target||!state.confirmed||(retry?(!state.restoreRequest||!state.restoreRetry):!!state.restoreRequest))return;const task=begin('restore');if(!task)return;
   if(!retry)state.restoreRequest={preview_id:state.preview.preview_id,input_digest:state.preview.input_digest,request_id:crypto.randomUUID()};
   // Only an exact read-back failed receipt permits a human-initiated replay.
   // Consume that permission before dispatch; a lost retry needs another GET.
   state.restoreRetry=false;changed();
   try{state.restore=await owned('/backups/restore',{method:'POST',body:state.restoreRequest});if(state.restore.state==='succeeded')state.completion++;}
   catch(error){state.error='Restore outcome is uncertain. Check this exact request ID; never submit another restore automatically. '+error.message;}
   finally{finish(task);}
  }
  async function inspect(kind,id,retained=false){
   if(typeof id!=='string'||!id.trim())return;const task=begin('inspect');if(!task)return;
   if(retained&&kind==='restore')state.restoreRetry=false;
   try{
    const result=await owned((kind==='export'?'/exports/requests/':'/backups/requests/')+encodeURIComponent(id));if(!valid(task))return;
    if(retained&&kind==='export')state.artifact=result;
    else if(retained){if(result.state==='succeeded'&&state.restore?.state!=='succeeded')state.completion++;state.restore=result;state.restoreRetry=result.state==='failed';}
    else state.inspection={kind,id,result};
   }catch(error){if(valid(task))state.error=error.code==='not_found'?'No accepted operation found yet. Keep the original request ID and check again; no request was replayed.':error.message;}
   finally{finish(task);}
  }
  function stop(){if(!state.task||!['upload','download'].includes(state.busy))return;state.task.stopped=true;state.error='Transfer stopped after the current request. Accepted upload bytes are kept; resume explicitly. An admitted restore cannot be cancelled.';changed();}
  function leave(){if(state.task)state.task.stopped=true;state.confirmClose=false;callbacks.current.onClose();}
  function discard(){
   if(state.restoreRequest)return;retainUpload();
   // Discarding a file invalidates transfer continuations, not a separate
   // admitted operation whose acknowledgement must still settle its identity.
   if(!state.task||['upload','download'].includes(state.busy)){if(state.task)state.task.stopped=true;state.epoch++;state.task=null;state.busy='';}
   state.file=null;state.uploadRequest=null;state.upload=null;state.preview=null;state.confirmed=false;state.error='';leave();changed();
  }
  function close(){if(state.file&&!state.restoreRequest){stop();state.confirmClose=true;changed();return;}leave();}
  if(!open)return null;
  const busy=!!state.busy;
  return h(Dialog,{title:'Library data',description:'Portable exports and empty-library restore. Backups are unencrypted and contain private notes and images. No chat, credentials or executable jobs are included.',className:'hb-dialog-data',onCloseRequest:close},
   state.confirmClose?h('section',{'aria-label':'Keep selected backup'},h('p',null,'Keep this selected backup for later, or discard the file draft? Accepted upload bytes are not undone; operation request IDs are retained.'),h('div',{className:'hb-data-actions'},h(Button,{type:'button',onClick:()=>{state.confirmClose=false;changed();}},'Keep editing data'),h(Button,{type:'button',onClick:leave},'Close and keep file'),h(Button,{type:'button',onClick:discard},'Discard file and close'))):h(React.Fragment,null,
   h('section',{className:'hb-data-section','aria-label':'Export library'},h('h3',null,'Export'),
    h('label',{className:'hb-field'},'Export format',h('select',{'aria-label':'Export format',value:state.format,disabled:busy||exportLocked(),onChange:event=>{state.format=event.target.value;changed();}},h('option',{value:'bundle'},'Portable backup (ZIP)'),h('option',{value:'html'},'Bookmark HTML (links only)'))),
    state.format==='html'&&h('label',null,h('input',{type:'checkbox','aria-label':'Include Trash in HTML',checked:state.includeTrash,disabled:busy,onChange:event=>{state.includeTrash=event.target.checked;changed();}}),' Include trashed links'),
    h('p',{className:'hb-muted'},'HTML omits notes, images and other portable-backup data. Browser transfers are limited to 512 MiB and require memory for the full file. Artifacts expire after 24 hours; cleanup is lazy.'),
    h('div',{className:'hb-data-actions'},h(Button,{type:'button',disabled:busy||exportLocked(),onClick:generate},'Generate export'),h(Button,{type:'button',disabled:busy||state.artifact?.state!=='ready',onClick:()=>download()},'Download export'),state.exportRequest&&h(Button,{type:'button',disabled:busy,onClick:()=>inspect('export',state.exportRequest.request_id,true)},'Check export request')),
    state.exportRequest&&h('p',{className:'hb-data-id'},'Export request ID: '+state.exportRequest.request_id),state.artifact&&h('div',null,h('p',{role:'status'},'Export '+state.artifact.state),state.artifact.state==='ready'&&h('div',{'aria-label':'Export integrity'},h('p',null,state.artifact.filename+' · '+state.artifact.size+' bytes'),state.artifact.format==='bundle'&&h('p',null,'Backup format version '+state.artifact.format_version),h('p',{className:'hb-data-id'},'SHA-256: '+state.artifact.digest)),h('p',null,JSON.stringify(state.artifact.counts)),h('ul',null,(state.artifact.limitations||[]).map((text,index)=>h('li',{key:index},text))))),
   h('section',{className:'hb-data-section','aria-label':'Restore library'},h('h3',null,'Restore portable backup'),h('p',null,'Restore is atomic and only allowed into an empty library. Existing content is never merged or overwritten. Jobs, chat and credentials are not restored; model-route hints stay inactive.'),
    h('label',{className:'hb-field'},'Backup file',h('input',{type:'file',accept:'.zip',disabled:busy||!!state.restoreRequest,'aria-label':'Backup file',onChange:selectFile})),state.file&&h('p',null,state.file.name+' · '+state.file.size+' bytes'),
    h(Button,{type:'button',disabled:busy||!state.file||!!state.restoreRequest,onClick:upload},state.uploadRequest?'Resume upload and preview':'Upload and preview backup'),state.uploadRequest&&h('p',{className:'hb-data-id'},'Upload request ID: '+state.uploadRequest.request_id),state.upload&&h('p',{role:'status'},'Uploaded '+state.upload.offset+' / '+state.upload.size+' bytes'),
    state.preview&&h('div',{'aria-label':'Backup preview'},h('p',null,'Backup version '+state.preview.format_version+' · '+JSON.stringify(state.preview.counts)),h('ul',null,(state.preview.limitations||[]).map((text,index)=>h('li',{key:index},text))),!state.preview.empty_target&&h('p',{role:'alert'},'The target library is not empty. Restore is disabled.'),
     h('label',null,h('input',{type:'checkbox','aria-label':'Confirm empty-library restore',checked:state.confirmed,disabled:busy||!state.preview.empty_target||!!state.restoreRequest,onChange:event=>{state.confirmed=event.target.checked;changed();}}),' I reviewed this backup and confirm restore into this empty library.'),
     h(Button,{type:'button',disabled:busy||!state.preview.empty_target||!state.confirmed||!!state.restoreRequest,onClick:()=>restore()},'Restore backup')),
    state.previousUploads.length>0&&h('details',null,h('summary',null,'Previous upload request IDs (session only)'),h('p',{className:'hb-muted'},'These file drafts were replaced or discarded. Accepted bytes may remain until expiry; they cannot start a restore on their own.'),h('ul',null,state.previousUploads.map(request=>h('li',{key:request.request_id,className:'hb-data-id'},'Upload request '+request.request_id+(request.id?' · upload '+request.id:''))))),
    state.restoreRequest&&h('div',null,h('p',{className:'hb-data-id'},'Restore request ID: '+state.restoreRequest.request_id),h(Button,{type:'button',disabled:busy,onClick:()=>inspect('restore',state.restoreRequest.request_id,true)},'Check restore request'),state.restoreRetry&&h(Button,{type:'button',disabled:busy,onClick:()=>restore(true)},'Retry failed restore')),state.restore&&h('p',{role:'status'},'Restore '+state.restore.state+' · '+JSON.stringify(state.restore.counts))),
   h('section',{className:'hb-data-section','aria-label':'Inspect saved operation'},h('h3',null,'Inspect an existing operation'),h('p',{className:'hb-muted'},'After page reload, paste a saved request ID for read-only inspection. This does not upload, generate or restore anything. Session file drafts do not survive a page reload.'),
    h('label',{className:'hb-field'},'Operation kind',h('select',{'aria-label':'Operation kind',value:state.lookupKind,disabled:busy,onChange:event=>{state.lookupKind=event.target.value;state.inspection=null;changed();}},h('option',{value:'export'},'Export'),h('option',{value:'restore'},'Restore'))),
    h('label',{className:'hb-field'},'Operation request ID',h('input',{'aria-label':'Operation request ID',value:state.lookupId,disabled:busy,maxLength:128,onChange:event=>{state.lookupId=event.target.value;state.inspection=null;changed();},onInput:event=>{state.lookupId=event.currentTarget.value;state.inspection=null;changed();}})),
    h(Button,{type:'button',disabled:busy||!state.lookupId.trim(),onClick:()=>inspect(state.lookupKind,state.lookupId)},'Inspect operation'),state.inspection&&h('div',{'aria-label':'Inspected operation'},h('p',{className:'hb-data-id'},state.inspection.kind+' request '+state.inspection.id),h('p',{role:'status'},state.inspection.result.state),h('p',null,JSON.stringify(state.inspection.result.counts)),state.inspection.kind==='export'&&state.inspection.result.state==='ready'&&h('div',null,h('p',null,state.inspection.result.filename+' · '+state.inspection.result.size+' bytes'),h('p',{className:'hb-data-id'},'SHA-256: '+state.inspection.result.digest),h(Button,{type:'button',disabled:busy,onClick:()=>download(state.inspection.result)},'Download inspected export')))) ,
   busy&&h('p',{role:'status'},'Working: '+state.busy),['upload','download'].includes(state.busy)&&h(Button,{type:'button',onClick:stop},'Stop transfer'),state.restoreRequest&&h('p',{className:'hb-muted'},'An admitted restore cannot be cancelled. Closing this dialog does not undo it. Check the request ID to reconcile its result; restore is never retried automatically.'),state.error&&h('p',{role:'alert',className:'hb-error'},state.error),h(Button,{type:'button',onClick:close},'Close data')));
 };
}
