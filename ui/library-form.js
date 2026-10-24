function createLibraryForm(React,adapter,components){
 const {createElement:h,useState,useEffect,useRef}=React,Button=components.Button||'button',Input=components.Input||'input';
 const Dialog=createLibraryDialog(React,components),AssetImage=createBookmarkAssetImage(React,adapter);
 const formatTags=tags=>tags.map(tag=>/[",\r\n]/.test(tag)?'"'+tag.replaceAll('"','""')+'"':tag).join(', ');
 function tagsOf(value,strict=false){
  const tags=[];let label='',quoted=false;
  for(let i=0;i<value.length;i++){const char=value[i];if(char==='"'){if(quoted&&value[i+1]==='"'){label+='"';i++;}else quoted=!quoted;}else if(char===','&&!quoted){if(label.trim())tags.push(label.trim());label='';}else label+=char;}
  if(quoted&&strict)throw Object.assign(Error('Close the quoted tag before saving.'),{code:'invalid_argument'});
  if(label.trim())tags.push(label.trim());return [...new Set(tags)];
 }
 const valueOf=(item,defaultCollection)=>({kind:item?.kind||'link',url:item?.url||'',title:item?.title||'',description:item?.description||'',notes:item?.notes||'',summary:item?.summary||'',collection_id:item?.collection_id||defaultCollection||null,tags:formatTags(item?.tags||[]),favorite:!!item?.favorite,read_later:!!item?.read_later,primary_asset_id:item?.primary_asset_id||null,attachment_ids:(item?.attachments||[]).filter(asset=>asset.role!=='primary').map(asset=>asset.asset_id)});
 return function LibraryForm({ctx,scope,libraryId,item,defaultCollection,onSaved,onClose}){
  const storeKey=bookmarkLibraryKey(scope,libraryId)+'/'+(item?.id||'new');
  if(!bookmarkLibraryDrafts.has(storeKey)){
   const value=valueOf(item,defaultCollection);
   bookmarkLibraryDrafts.set(storeKey,{id:crypto.randomUUID(),key:crypto.randomUUID(),value,initial:JSON.stringify(value),original:item,phase:'editing',error:'',uploads:0,listeners:new Set()});
  }
  const draft=useRef(bookmarkLibraryDrafts.get(storeKey)).current,value=draft.value,live=useRef(true);
  const [,paint]=useState(0),[confirm,setConfirm]=useState(false),[preview,setPreview]=useState(false);
  const [collectionQuery,setCollectionQuery]=useState(''),[collectionOffset,setCollectionOffset]=useState(0),[collections,setCollections]=useState([]),[collectionTotal,setCollectionTotal]=useState(0);
  function changed(){bookmarkDraftChanged(draft);}
  function field(name,next){value[name]=next;if(name==='summary')draft.summaryTouched=true;draft.error='';changed();}
  const api=(route,init)=>bookmarkOwnedRequest(adapter,ctx,scope,route,init);
  useEffect(()=>{live.current=true;const publish=()=>{
   if(!live.current||(adapter.currentScope&&adapter.currentScope()!==scope))return;
   if(draft.phase==='saved'&&!draft.delivered){draft.delivered=true;if(bookmarkLibraryDrafts.get(storeKey)===draft)bookmarkLibraryDrafts.delete(storeKey);onSaved({item:draft.saved,receipt:draft.receipt});}
   else paint(n=>n+1);
  };draft.listeners.add(publish);if(draft.phase==='saved')publish();return()=>{live.current=false;draft.listeners.delete(publish);};},[]);
  useEffect(()=>{let active=true;api('/collections?limit=50&offset='+collectionOffset+'&query='+encodeURIComponent(collectionQuery)).then(payload=>{if(active){setCollections(previous=>collectionOffset?[...previous,...payload.result.collections]:payload.result.collections);setCollectionTotal(payload.result.total);}}).catch(()=>{});return()=>{active=false;};},[collectionQuery,collectionOffset]);
  function discard(){draft.discarded=true;bookmarkLibraryDrafts.delete(storeKey);onClose();}
  function close(){if(draft.phase==='saving'){draft.error='Saving is still in progress. Keep this form open until the outcome is known.';changed();return;}if(JSON.stringify(value)!==draft.initial||draft.summaryTouched||draft.phase==='uncertain'||draft.uploads>0)setConfirm(true);else onClose();}
  function finish(payload){
   const record=payload.item||payload.result,receipt=payload.receipt;
   if(['duplicate','trashed_duplicate'].includes(receipt?.outcome)){draft.phase='duplicate';draft.saved=record;draft.receipt=receipt;draft.error=receipt.outcome==='trashed_duplicate'?'This URL is in Trash. Your staged fields are preserved and have not overwritten it. Open the existing item to inspect it; restore explicitly from Trash.':'This URL is already saved. Your staged fields have not overwritten it.';changed();return;}
   draft.phase='saved';draft.saved=record;draft.receipt=receipt;changed();
  }
  async function verify(){
   if(draft.phase==='saving')return;draft.phase='saving';changed();
   try{
    if(item){
     const payload=await api('/items/'+encodeURIComponent(item.id)),record=payload.result,changes=draft.editSubmission?.changes||{};
     const tagKey=tag=>tag.normalize('NFC').toLowerCase();
     const matches=Object.entries(changes).every(([name,wanted])=>{
      if(name==='add_tags')return wanted.every(tag=>(record.tags||[]).some(existing=>tagKey(existing)===tagKey(tag)));
      if(name==='remove_tags')return wanted.every(tag=>!(record.tags||[]).some(existing=>tagKey(existing)===tagKey(tag)));
      if(name==='attachment_ids')return JSON.stringify([...wanted].sort())===JSON.stringify((record.attachments||[]).filter(asset=>asset.role!=='primary').map(asset=>asset.asset_id).sort());
      if(name==='summary')return record.summary===wanted&&record.summary_source==='manual';
      return record[name]===wanted;
     });
     if(record.revision>draft.original.revision&&matches)finish({item:record});
     else{draft.phase=record.revision===draft.original.revision?'retry':'conflict';draft.error=draft.phase==='retry'?'No matching edit was found. Retry the original edit explicitly.':'The saved item changed. Your local edit is preserved; review the latest version.';changed();}
    }else{const payload=await api('/captures/'+encodeURIComponent(draft.key));finish(payload.result);}
   }
   catch(error){draft.phase=error.code==='not_found'?'retry':'uncertain';draft.error=error.code==='not_found'?'No saved operation was found. You may retry the original save explicitly.':'Could not verify the previous save. Your input is preserved.';changed();}
  }
  async function save(event){
   event.preventDefault();if(['saving','uncertain','duplicate','conflict'].includes(draft.phase)||draft.uploads)return;
   draft.phase='saving';draft.error='';changed();
   try{
    if(new TextEncoder().encode(value.notes).length>65536||new TextEncoder().encode(value.description).length>16384)throw Object.assign(Error('Notes or description exceed their text limit.'),{code:'invalid_argument'});
    const tags=item&&value.tags===JSON.parse(draft.initial).tags?[...(draft.original.tags||[])]:tagsOf(value.tags,true);
    if(item){
     const original=draft.original,oldTags=original.tags||[],changes={};
     for(const name of ['title','description','notes','summary','collection_id','favorite','read_later'])if(value[name]!==JSON.parse(draft.initial)[name]||(name==='summary'&&draft.summaryTouched))changes[name]=value[name];
     const added=tags.filter(tag=>!oldTags.includes(tag)),removed=oldTags.filter(tag=>!tags.includes(tag));
     if(added.length)changes.add_tags=added;if(removed.length)changes.remove_tags=removed;
     if(JSON.stringify(value.attachment_ids)!==JSON.stringify(JSON.parse(draft.initial).attachment_ids))changes.attachment_ids=[...value.attachment_ids];
     if(!draft.editSubmission)draft.editSubmission={expected_revision:original.revision,changes};
     const payload=await api('/items/'+encodeURIComponent(item.id)+'/update',{method:'POST',body:draft.editSubmission});finish({item:payload.result});
    }else{
     if(!draft.submission||draft.phase!=='retry'){
      if(!draft.submission){const body={kind:value.kind,title:value.title,description:value.description,notes:value.notes,collection_id:value.collection_id,tags,favorite:value.favorite,read_later:value.read_later,attachment_ids:[...value.attachment_ids],operation_key:draft.key};
       if(value.kind==='link')body.url=value.url;else body.primary_asset_id=value.primary_asset_id;
       draft.submission=body;
      }
     }
     const payload=await api('/items',{method:'POST',body:draft.submission});finish({item:payload.result,receipt:payload.receipt});
    }
   }catch(error){
    const known=['invalid_argument','invalid_url','not_found','conflict','configuration_error'].includes(error.code)||(error.code==='scope_changed'&&error.dispatched===false);
    draft.phase=error.code==='conflict'?'conflict':known?'editing':'uncertain';draft.error=known?error.message:'Save outcome is uncertain. Verify save before submitting again. Your draft is preserved.';
    if(known&&!item)draft.submission=null;
    if(known&&item)draft.editSubmission=null;
    changed();
   }
  }
  async function reload(){
   try{const payload=await api('/items/'+encodeURIComponent(item.id));if(!live.current)return;draft.discarded=true;bookmarkLibraryDrafts.delete(storeKey);onSaved({item:payload.result,reopenEdit:true});}
   catch(error){draft.error=error.message;changed();}
  }
  async function compare(){
   if(draft.comparing)return;draft.comparing=true;changed();
   try{const payload=await api('/items/'+encodeURIComponent(item.id));draft.review=payload.result;}
   catch(error){draft.error=error.message;}finally{draft.comparing=false;changed();}
  }
  function adoptReviewed(){
   try{
   const record=draft.review;if(!record||draft.phase!=='conflict')return;
   const before=JSON.parse(draft.initial),base=valueOf(record,null),local={};
   for(const name of Object.keys(base))if(JSON.stringify(value[name])!==JSON.stringify(before[name])||(name==='summary'&&draft.summaryTouched))local[name]=value[name];
   if(Object.hasOwn(local,'tags')){const previous=draft.original.tags||[],desired=tagsOf(local.tags,true),removed=previous.filter(tag=>!desired.includes(tag)),added=desired.filter(tag=>!previous.includes(tag));local.tags=formatTags([...new Set([...(record.tags||[]).filter(tag=>!removed.includes(tag)),...added])]);}
   Object.assign(value,base,local);draft.initial=JSON.stringify(base);draft.original=record;draft.review=null;draft.editSubmission=null;draft.phase='editing';draft.error='Reviewed revision selected. Save explicitly to apply your local changes.';changed();
   }catch(error){draft.error=error.message;changed();}
  }
  async function upload(event,primary){
   const files=[...(event.currentTarget.files||[])];if(!files.length||draft.uploads)return;
   draft.uploads++;changed();
   try{for(const file of files){
    if(draft.discarded)break;
    const count=value.attachment_ids.length+(value.primary_asset_id?1:0);
    if((!primary&&count>=10)||file.size>10*1024*1024||!['image/png','image/jpeg','image/webp'].includes(file.type))throw Error('Choose up to 10 PNG, JPEG or WebP images, each at most 10 MiB.');
    const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));
    const payload=await api('/assets/base64',{method:'POST',body:{content_base64:btoa(binary),mime_type:file.type}});
    if(draft.discarded)continue;
    if(primary)value.primary_asset_id=payload.result.id;else if(!value.attachment_ids.includes(payload.result.id))value.attachment_ids.push(payload.result.id);
   }}catch(error){draft.error=error.message;}finally{draft.uploads--;changed();}
  }
  const busy=draft.phase==='saving',locked=['uncertain','duplicate','retry'].includes(draft.phase),selected=collections.some(row=>row.id===value.collection_id);
  function input(label,name,props={}){return h('label',{className:'hb-field',key:'field-'+name},h('span',null,label),h(Input,{'aria-label':label,name,value:value[name]||'',onInput:event=>field(name,event.currentTarget.value),onChange:event=>field(name,event.currentTarget.value),disabled:busy||locked,...props}));}
  return h(Dialog,{className:'hb-dialog-form',title:item?'Edit bookmark':'Add bookmark',description:'Save a link or image with your own context. Notes stay separate from AI summaries.',onCloseRequest:close},
   confirm?h('section',{'aria-label':'Unsaved changes'},h('h3',null,'Discard these unsaved changes?'),h('p',null,'Uploaded images may remain staged. Closing does not undo a save already accepted by the backend.'),h('div',{className:'hb-form-actions'},h(Button,{type:'button',onClick:()=>setConfirm(false)},'Keep editing'),h(Button,{type:'button',onClick:discard},'Discard'))):h('form',{onSubmit:save,className:'hb-item-form'},
    h('section',{className:'hb-form-essentials','aria-label':'Bookmark essentials'},
    h('label',{className:'hb-field'},'Type',h('select',{'aria-label':'Item type',value:value.kind,disabled:!!item||busy||locked,onChange:event=>field('kind',event.target.value)},h('option',{value:'link'},'Link'),h('option',{value:'image'},'Image'))),
    value.kind==='link'?input('Bookmark URL','url',{type:'url',required:true,maxLength:8192,readOnly:!!item,placeholder:'https://…'}):h('label',{className:'hb-field'},'Primary image',!item&&h('input',{type:'file','aria-label':'Primary image',accept:'image/png,image/jpeg,image/webp',disabled:busy||locked||!!draft.uploads,onChange:event=>upload(event,true)}),value.primary_asset_id&&h(AssetImage,{ctx,scope,assetId:value.primary_asset_id,alt:'Primary saved image'})),
    input('Title','title',{maxLength:1000,placeholder:'Optional title'}),
    h('div',{className:'hb-field hb-collection-picker'},h('label',null,'Collection search',h(Input,{'aria-label':'Collection search',value:collectionQuery,onChange:event=>{setCollectionOffset(0);setCollectionQuery(event.target.value);}})),h('label',null,'Collection',h('select',{'aria-label':'Collection',value:value.collection_id||'',disabled:busy||locked,onChange:event=>field('collection_id',event.target.value||null)},h('option',{value:''},'Inbox'),!selected&&value.collection_id&&h('option',{value:value.collection_id},'Current collection'),collections.map(row=>h('option',{key:row.id,value:row.id},(row.path||[{name:row.name}]).map(part=>part.name).join(' / '))))),collections.length<collectionTotal&&h(Button,{type:'button',onClick:()=>setCollectionOffset(collections.length)},'More collections'))),
    h('details',{className:'hb-form-section',open:!!value.tags},h('summary',null,'Tags',value.tags?' · '+tagsOf(value.tags).length:''),h('label',{className:'hb-field'},'Tags',h('textarea',{'aria-label':'Tags',rows:2,value:value.tags,disabled:busy||locked,placeholder:'Comma-separated; quote tags containing commas',onInput:event=>field('tags',event.currentTarget.value),onChange:event=>field('tags',event.target.value)})),h('p',{className:'hb-muted'},'Use double quotes around a tag containing a comma; double a quote inside a quoted tag.'),item?.tag_details?.some(tag=>tag.source==='generated')&&h('p',{className:'hb-muted'},'Existing AI tags stay generated unless you change them.')),
    h('details',{className:'hb-form-section hb-notes-section',open:!!value.notes},h('summary',null,'Notes',value.notes?' · has content':''),h('p',{className:'hb-section-hint'},'Your own context, kept separate from the saved AI summary. Markdown is supported.'),h('label',{className:'hb-field'},'Personal notes',h('textarea',{'aria-label':'Personal notes',value:value.notes,rows:8,disabled:busy||locked,onInput:event=>field('notes',event.currentTarget.value),onChange:event=>field('notes',event.target.value)})),h(Button,{type:'button',onClick:()=>setPreview(current=>!current)},preview?'Hide note preview':'Preview notes'),preview&&h('div',{className:'hb-note-preview','aria-label':'Personal notes preview'},bookmarkMarkdown(React,value.notes))),
    item&&h('details',{className:'hb-form-section hb-summary-section',open:!!value.summary},h('summary',null,'Saved summary'),h('p',{className:'hb-section-hint'},'Editing this summary makes it manual and protects it from delayed AI results. A later explicitly reviewed regeneration can replace the reviewed summary.'),h('label',{className:'hb-field'},'Saved summary',h('textarea',{'aria-label':'Saved summary',value:value.summary,rows:6,maxLength:16000,disabled:busy||locked,onInput:event=>field('summary',event.currentTarget.value),onChange:event=>field('summary',event.currentTarget.value)}))),
    h('details',{className:'hb-form-section',open:!!value.description},h('summary',null,'Description'),h('label',{className:'hb-field'},'Description',h('textarea',{'aria-label':'Description',value:value.description,rows:3,disabled:busy||locked,onChange:event=>field('description',event.target.value),onInput:event=>field('description',event.currentTarget.value)}))),
    h('details',{className:'hb-form-section',open:value.attachment_ids.length>0},h('summary',null,'Image attachments · '+value.attachment_ids.length),h('input',{type:'file',multiple:true,'aria-label':'Attachment images',accept:'image/png,image/jpeg,image/webp',disabled:busy||locked||!!draft.uploads,onChange:event=>upload(event,false)}),h('div',{className:'hb-attachments'},value.attachment_ids.map(assetId=>h('div',{key:assetId,'data-asset-id':assetId},h(AssetImage,{ctx,scope,assetId,alt:'Attached image'}),h(Button,{type:'button',disabled:busy||locked,onClick:()=>field('attachment_ids',value.attachment_ids.filter(id=>id!==assetId))},'Remove image'))))),
    h('div',{className:'hb-flags'},['favorite','read_later'].map(name=>h('label',{key:name},h('input',{type:'checkbox','aria-label':name==='favorite'?'Favorite':'Read later',checked:value[name],disabled:busy||locked,onChange:event=>field(name,event.target.checked)}),name==='favorite'?'Favorite':'Read later'))),
    draft.uploads>0&&h('p',{role:'status'},'Uploading images…'),draft.error&&h('div',{role:'alert',className:'hb-error'},draft.error),
    draft.phase==='conflict'&&h('div',null,h('p',null,'A newer version exists. Keep editing compares the saved version while preserving your local fields. Reload saved discards them only after confirmation.'),h(Button,{type:'button',onClick:()=>{if(draft.reloadConfirm)reload();else{draft.reloadConfirm=true;changed();}}},draft.reloadConfirm?'Confirm reload saved':'Reload saved'),h(Button,{type:'button',disabled:!!draft.comparing,onClick:compare},draft.comparing?'Comparing…':'Keep editing'),draft.review&&h('section',{'aria-label':'Saved version comparison'},h('h3',null,'Saved revision '+draft.review.revision),h('pre',null,JSON.stringify({title:draft.review.title,description:draft.review.description,notes:draft.review.notes,summary:draft.review.summary,summary_source:draft.review.summary_source,tags:draft.review.tags,collection_id:draft.review.collection_id,favorite:draft.review.favorite,read_later:draft.review.read_later},null,2)),h('p',null,'Your edited fields remain above. Unedited fields adopt this saved version only after confirmation; Save still checks its revision.'),h(Button,{type:'button',onClick:adoptReviewed},'Use reviewed revision'))),
    draft.phase==='duplicate'&&h(Button,{type:'button',onClick:()=>onSaved({item:draft.saved,receipt:draft.receipt,openExisting:true})},'Open existing'),
    h('div',{className:'hb-form-footer'},h('p',{className:'hb-muted hb-processing-note'},item?'Metadata and manual summary edits do not request regeneration.':value.kind==='link'?'Saving follows the library’s automatic tags and summary settings; provider charges and retries may apply.':'The image is stored in the library. Automatic analysis requires standalone-image opt-in and an enabled generated field in AI settings; provider charges and retries may apply.'),
    h('div',{className:'hb-form-actions'},h(Button,{type:'button',onClick:close},'Cancel'),draft.phase==='uncertain'?h(Button,{type:'button',className:'hb-primary',onClick:verify},'Verify save'):h(Button,{type:'submit',disabled:busy||['uncertain','duplicate','conflict'].includes(draft.phase)||draft.uploads>0||(value.kind==='image'&&!value.primary_asset_id)},busy?'Saving…':draft.phase==='retry'?'Retry original save':'Save')))));
 };
}
