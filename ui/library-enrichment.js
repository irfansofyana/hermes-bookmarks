// One deliberate item operation at a time; accepted writes survive remounts.
const bookmarkEnrichmentDrafts=new Map();
function createLibraryEnrichment(React,adapter,components){
 const {createElement:h,useEffect,useRef,useState}=React,Button=components.Button||'button';
 const terminal=job=>job&&['succeeded','failed','cancelled'].includes(job.state),active=job=>job&&['pending','running'].includes(job.state);
 const errors={configuration_required:'Configure the library provider, model and fixed execution owner in AI settings.',trust_denied:'Hermes denied model access. Review the execution owner’s trust permissions.',extraction_failed:'Page extraction failed. The saved item is unchanged.',invalid_result:'The model did not return valid structured output.',provider_failed:'The provider failed. Check route access and model/image compatibility before a deliberate retry.',missing_asset:'The owned primary image is unavailable.',generation_conflict:'This generation no longer owns the item. Review the current item before a new generation.',manual_summary_conflict:'A manual summary edit was protected. Any safely applied fields are listed separately.'};
 const fresh=()=>({fields:['summary','tags'],phase:'idle',review:null,confirmed:false,request:null,receipt:null,job:null,previous:[],lookupId:'',cancelUncertain:false,sourceReview:null,sourceUncertain:null,error:'',busy:'',task:null,completion:0,delivered:0,listeners:new Set()});
 const uuid=value=>typeof value==='string'&&/^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/.test(value);
 return function LibraryEnrichment({ctx,scope,libraryId,item,onChanged,onReload,onItemChanged}){
  const key=JSON.stringify([scope,libraryId,item.id]);if(!bookmarkEnrichmentDrafts.has(key))bookmarkEnrichmentDrafts.set(key,fresh());
  const state=bookmarkEnrichmentDrafts.get(key),owner=useRef(null),callbacks=useRef(null),[,paint]=useState(0);callbacks.current={onChanged,onReload,onItemChanged};
  const current=()=>owner.current?.active&&owner.current.state===state&&(!adapter.currentScope||adapter.currentScope()===scope);
  const changed=()=>bookmarkDraftChanged(state),owned=async(route,init)=>(await bookmarkOwnedRequest(adapter,ctx,scope,route,init)).result;
  useEffect(()=>{const lease={active:true,state};owner.current=lease;
   const listener=()=>{if(!current())return;paint(n=>n+1);if(state.delivered<state.completion){state.delivered=state.completion;if(state.latestRecord)callbacks.current.onItemChanged?.(state.latestRecord);callbacks.current.onChanged?.();callbacks.current.onReload?.();}};
   state.listeners.add(listener);listener();return()=>{lease.active=false;state.listeners.delete(listener);if(state.task?.owner===lease&&!state.task.write){state.task=null;state.busy='';if(state.phase==='reviewing')state.phase='idle';}};
  },[state]);
  function begin(kind,write=false){if(!current()||state.task)return null;const task={kind,write,owner:owner.current};state.task=task;state.busy=kind;state.error='';changed();return task;}
  const valid=task=>state.task===task&&task.owner.active&&current();
  function finish(task){if(state.task===task){state.task=null;state.busy='';changed();}}
  function validateJob(job,expected){
   if(!job||job.item_id!==item.id||typeof job.id!=='string'||!['pending','running','succeeded','failed','cancelled'].includes(job.state)||!Number.isSafeInteger(job.revision)||job.revision<1||!Number.isSafeInteger(job.generation)||job.generation<1||!Number.isSafeInteger(job.attempts)||job.attempts<0||!Number.isSafeInteger(job.settings_revision)||job.settings_revision<1||!Array.isArray(job.fields)||!job.fields.length||job.fields.some(name=>!['summary','tags'].includes(name))||!Array.isArray(job.applied_fields)||!Array.isArray(job.conflicted_fields))throw Error('Processing status identity or fields are invalid.');
   if(expected&&(job.id!==expected.id||job.generation!==expected.generation||job.revision!==expected.revision))throw Error('Processing status belongs to a different generation.');
   return job;
  }
  function applyJob(job,expected){validateJob(job,expected);if(JSON.stringify(job)!==JSON.stringify(state.job)){state.job=job;state.completion++;}state.phase='job';state.review=null;state.confirmed=false;state.cancelUncertain=false;state.statusUnknown=false;}
  function accept(result,request){
   const receipt=result?.receipt,job=validateJob(result?.job);
   if(!receipt||receipt.item_id!==item.id||receipt.request_id!==request.request_id||receipt.accepted_revision!==request.expected_revision||JSON.stringify(receipt.fields)!==JSON.stringify(request.fields)||receipt.job_id!==job.id||receipt.generation!==job.generation||receipt.accepted_revision!==job.revision||receipt.settings_revision!==job.settings_revision||JSON.stringify(receipt.fields)!==JSON.stringify(job.fields))throw Error('The enrichment receipt does not match the exact reviewed request.');
   state.receipt=receipt;applyJob(job);state.review=null;state.confirmed=false;
  }
  async function readStatus(selected=state.job){
   const id=selected?.id||item.enrichment_job_id;if(!id)return;const task=begin('status');if(!task)return;
   try{const job=await owned('/enrichment/jobs/'+encodeURIComponent(id));if(!valid(task))return;validateJob(job,selected);if(job.id!==id)throw Error('The status response names another job.');applyJob(job,selected);}
   catch(error){if(valid(task)){state.error='Processing status could not be verified. '+error.message;if(!state.job)state.statusUnknown=true;}}
   finally{finish(task);}
  }
  useEffect(()=>{if(item.enrichment_job_id&&!state.task&&!['admitting','uncertain'].includes(state.phase)&&(!state.job||state.job.id!==item.enrichment_job_id))readStatus(null);},[state,item.enrichment_job_id]);
  useEffect(()=>{if(!active(state.job)||state.cancelUncertain||state.phase!=='job')return;const selected=state.job;const timer=setInterval(()=>{if(current()&&!state.task&&state.job?.id===selected.id)readStatus(selected);},1000);return()=>clearInterval(timer);},[state,state.job?.id,state.job?.state,state.cancelUncertain,state.phase]);
  function choose(name,checked){if(!current()||state.task||state.review||state.phase==='uncertain'||active(state.job)||state.cancelUncertain)return;state.fields=['summary','tags'].filter(field=>field===name?checked:state.fields.includes(field));changed();}
  async function review(){
   if(!state.fields.length||active(state.job)||state.phase==='uncertain'||state.cancelUncertain||item.deleted_at)return;
   const task=begin('review');if(!task)return;const fields=Object.freeze([...state.fields]);state.phase='reviewing';state.review=null;state.confirmed=false;
   try{
    const [record,config]=await Promise.all([owned('/items/'+encodeURIComponent(item.id)),owned('/settings')]);if(!valid(task))return;
    if(record?.id!==item.id||!Number.isSafeInteger(record.revision)||record.revision<1||record.deleted_at)throw Error('This item is unavailable or in Trash.');
    const cfg=bookmarkSettingsEnvelope(config);
    if(record.enrichment_job_id&&['pending','running'].includes(record.enrichment_status)){
     const job=await owned('/enrichment/jobs/'+encodeURIComponent(record.enrichment_job_id));if(!valid(task))return;applyJob(job);state.error='An accepted job is already active. Inspect or cancel it before another generation.';return;
    }
    state.review=Object.freeze({item_id:record.id,expected_revision:record.revision,fields,settings_revision:cfg.revision,settings:cfg.settings,route_ready:cfg.route_ready,blocked:record.kind==='image'&&!cfg.settings.image_analysis?'Image analysis is off. Enable standalone image analysis in AI settings before reviewing an image request.':''});
    state.phase='review';state.confirmed=false;
   }catch(error){if(valid(task)){state.phase='idle';state.error=error.message;}}
   finally{finish(task);}
  }
  function cancelReview(){if(!current()||state.task||state.phase!=='review')return;state.review=null;state.confirmed=false;state.phase=state.job?'job':'idle';changed();}
  async function start(reviewed){
   if(!current()||state.task||state.review!==reviewed||state.phase!=='review'||!state.confirmed||reviewed.blocked)return;
   const task=begin('admission',true);if(!task)return;
   if(state.request)state.previous.push({request:state.request,receipt:state.receipt});
   const request=Object.freeze({expected_revision:reviewed.expected_revision,request_id:crypto.randomUUID(),fields:reviewed.fields});state.request=request;state.receipt=null;state.phase='admitting';state.error='';changed();
   try{const result=await owned('/items/'+encodeURIComponent(reviewed.item_id)+'/enrich',{method:'POST',body:request});if(state.task!==task||state.request!==request)return;accept(result,request);}
   catch(error){if(state.task!==task||state.request!==request)return;const known=['invalid_argument','not_found','conflict','configuration_error'].includes(error.code)||(error.code==='scope_changed'&&error.dispatched===false);
    if(known){state.phase=state.job?'job':'idle';state.review=null;state.request=null;state.error=error.code==='conflict'?'This item changed or already has active work. Refresh and review a new request; no automatic replay was sent.':error.message;}
    else{state.phase='uncertain';state.error='Enrichment admission is uncertain. Keep this exact request ID and use GET-only lookup. Not found never authorizes replay.';}
   }finally{finish(task);}
  }
  async function inspect(retained){
   const request=retained?state.request:null,id=retained?request?.request_id:state.lookupId;if(!uuid(id)){state.error='Enter the exact UUID request ID, without changing its spelling or adding whitespace.';changed();return;}
   const task=begin('request');if(!task)return;
   try{const result=await owned('/enrichment/requests/'+encodeURIComponent(id));if(!valid(task))return;
    const receipt=result?.receipt;if(!receipt||receipt.request_id!==id||receipt.item_id!==item.id)throw Error('This receipt does not belong to the selected item and request.');
    const tuple=request||Object.freeze({request_id:id,expected_revision:receipt.accepted_revision,fields:Object.freeze([...(receipt.fields||[])])});accept(result,tuple);state.request=tuple;
   }catch(error){if(valid(task))state.error=error.code==='not_found'?'Request not found among accepted receipts yet. Keep the exact ID and check again; nothing was replayed.':error.message;}
   finally{finish(task);}
  }
  async function cancel(selected){
   if(!current()||state.task||state.job!==selected||!active(selected)||state.cancelUncertain||state.phase==='uncertain')return;
   const task=begin('cancel',true);if(!task)return;
   try{const job=await owned('/enrichment/jobs/'+encodeURIComponent(selected.id)+'/cancel',{method:'POST',body:{}});if(state.task!==task)return;applyJob(job,selected);state.completion++;}
   catch(error){if(state.task===task){state.cancelUncertain=true;state.error='Cancellation outcome is uncertain. Check this exact job’s status before any new generation. Provider work may continue and incur charges.';}}
   finally{finish(task);}
  }
  function reviewClear(){if(!current()||state.task||state.sourceReview||state.sourceUncertain||!item.extracted_text)return;state.sourceReview=Object.freeze({item_id:item.id,expected_revision:item.revision});changed();}
  function cleared(record,request){if(record?.id!==request.item_id||!Number.isSafeInteger(record.revision)||record.revision<request.expected_revision||record.extracted_text!=='')throw Error('Retained-text removal could not be verified.');state.sourceReview=null;state.sourceUncertain=null;state.latestRecord=record;state.completion++;}
  async function clearSource(reviewed){
   if(!current()||state.task||state.sourceReview!==reviewed||state.sourceUncertain)return;const task=begin('source',true);if(!task)return;
   try{const record=await owned('/items/'+encodeURIComponent(reviewed.item_id)+'/source/clear',{method:'POST',body:{expected_revision:reviewed.expected_revision}});if(state.task!==task)return;cleared(record,reviewed);}
   catch(error){if(state.task===task){if(['conflict','invalid_argument','not_found'].includes(error.code)){state.sourceReview=null;state.error='Retained-text removal was rejected. Reload this item before another confirmed removal. '+error.message;}else{state.sourceUncertain=reviewed;state.error='Retained-text removal is uncertain. Check the saved item; no removal will be replayed automatically.';}}}
   finally{finish(task);}
  }
  async function checkClear(){const request=state.sourceUncertain;if(!request)return;const task=begin('source-check');if(!task)return;try{const record=await owned('/items/'+encodeURIComponent(request.item_id));if(valid(task))cleared(record,request);}catch(error){if(valid(task))state.error=error.message;}finally{finish(task);}}
  const busy=!!state.task,job=state.job,reviewed=state.review,clearReviewed=state.sourceReview,unknown=state.phase==='uncertain',locked=busy||!!reviewed||unknown||active(job)||state.cancelUncertain;
  return h('section',{className:'hb-ai-section hb-enrichment','aria-label':'Item AI processing'},h('h3',null,'AI processing'),
   h('p',{className:'hb-ai-disclosure'},'Explicit processing replaces only the chosen generated fields. Personal notes, manual tags and suppressed tag choices are preserved. Confirmed summary generation can replace the summary reviewed here; later manual edits are protected. Sources or the owned primary image are sent to the library model. Charges, queue attempts and Hermes retries/fallback may apply.'),
   job&&h('div',{'aria-label':'Processing status'},h('p',{role:'status'},'Processing '+job.state),h('p',{className:'hb-ai-id'},'Job '+job.id+' · generation '+job.generation+' · item revision '+job.revision+' · settings revision '+job.settings_revision),h('p',null,'Requested: '+job.fields.join(', ')+' · Queue attempts: '+job.attempts+' / 3'),job.provider&&h('p',null,'Actual provider/model: '+job.provider+' / '+(job.model||'not reported')),job.coverage&&h('p',null,'Coverage: '+job.coverage),job.applied_fields.length>0&&h('p',null,'Applied fields: '+job.applied_fields.join(', ')),job.conflicted_fields.length>0&&h('p',null,'Conflicted fields (not overwritten): '+job.conflicted_fields.join(', ')),job.error_code&&h('p',{role:'alert'},errors[job.error_code]||'Processing failed. Review the saved item before a new generation.',' Error code: '+job.error_code)),
   state.statusUnknown&&h('p',{role:'alert'},'The existing job status is unverified. Check it before requesting another generation.'),
   h('div',{className:'hb-ai-options'},['summary','tags'].map(name=>h('label',{key:name,className:'hb-ai-toggle'},h('input',{type:'checkbox','aria-label':name==='summary'?'Generate summary':'Generate tags',checked:state.fields.includes(name),disabled:locked||!!item.deleted_at,onChange:event=>choose(name,event.currentTarget.checked)}),name==='summary'?'Generate summary':'Generate tags'))),
   (!active(job)&&!unknown&&!state.statusUnknown&&!reviewed&&!item.deleted_at)&&h(Button,{type:'button',disabled:busy||!state.fields.length||state.cancelUncertain,onClick:review},job?job.state==='succeeded'?'Regenerate enrichment':'Retry enrichment':'Review enrichment'),
   state.phase==='reviewing'&&h('p',{role:'status'},'Reading the saved item and library settings for review…'),
   reviewed&&h('section',{className:'hb-ai-review','aria-label':'Enrichment review'},h('h4',null,'Review item revision '+reviewed.expected_revision),h('p',null,'Replace: '+reviewed.fields.join(', ')+' · library settings revision '+reviewed.settings_revision),h('p',null,'Configured route: '+(reviewed.settings.provider||'not configured')+' / '+(reviewed.settings.model||'not configured')+' · fixed owner '+(reviewed.settings.owner_profile||'unset')),h('p',null,'Accepted jobs snapshot settings at admission; concurrent settings changes may be reflected in the receipt. The saved route is not proof the owner is online or model/image compatibility is verified.'),!reviewed.route_ready&&h('p',{role:'alert'},'The route is unconfigured. Admission would fail configuration checks without a provider request.'),reviewed.settings.paused&&h('p',{role:'status'},'Processing was paused at review. An accepted job may remain pending until resumed.'),reviewed.blocked&&h('p',{role:'alert'},reviewed.blocked),h('label',{className:'hb-ai-toggle'},h('input',{type:'checkbox','aria-label':'Confirm enrichment replacement and costs',checked:state.confirmed,disabled:busy||state.phase!=='review'||!!reviewed.blocked,onChange:event=>{if(!current()||busy||state.phase!=='review'||state.review!==reviewed)return;state.confirmed=event.currentTarget.checked;changed();}}),' I reviewed the chosen fields, data transfer, possible replacement and costs.'),h('div',{className:'hb-ai-actions'},h(Button,{type:'button',disabled:busy||state.phase!=='review',onClick:cancelReview},'Cancel enrichment review'),h(Button,{type:'button','aria-label':'Start enrichment',className:'hb-primary',disabled:busy||!state.confirmed||!!reviewed.blocked||unknown,onClick:()=>start(reviewed)},state.phase==='admitting'?'Starting enrichment…':'Start enrichment'))),
   state.request&&h('div',null,h('p',{className:'hb-ai-id'},'Enrichment request ID: '+state.request.request_id),h(Button,{type:'button',disabled:busy,onClick:()=>inspect(true)},'Check enrichment request')),
   (job||item.enrichment_job_id)&&h('div',{className:'hb-ai-actions'},h(Button,{type:'button',disabled:busy||unknown,onClick:()=>readStatus(job)},'Check processing status'),active(job)&&h(Button,{type:'button',disabled:busy||state.cancelUncertain||unknown,onClick:()=>cancel(job)},'Cancel processing')),
   h('p',{className:'hb-muted'},'Cancel revokes application ownership and stops undispatched work, not remote provider execution. Already accepted requests may finish and incur charges. Closing stops polling, not accepted work.'),
   h('details',{className:'hb-enrichment-lookup'},h('summary',null,'Inspect a saved enrichment request'),h('p',{className:'hb-muted'},'After page reload, inspect an exact request ID for this item. This read-only lookup never replays processing. Session-only drafts and receipts are not browser persistence.'),h('label',{className:'hb-field'},h('span',null,'Enrichment request ID'),h('input',{'aria-label':'Enrichment request ID',value:state.lookupId,disabled:busy||unknown,maxLength:36,onInput:event=>{state.lookupId=event.currentTarget.value;changed();},onChange:event=>{state.lookupId=event.currentTarget.value;changed();}})),h(Button,{type:'button',disabled:busy||unknown||!state.lookupId,onClick:()=>inspect(false)},'Inspect enrichment request')),
   state.previous.length>0&&h('details',null,h('summary',null,'Previous enrichment request IDs (session only)'),state.previous.map(row=>h('p',{key:row.request.request_id,className:'hb-ai-id'},row.request.request_id))),
   (item.extracted_text||state.sourceUncertain)&&h('section',{className:'hb-ai-section','aria-label':'Retained extracted text controls'},h('h4',null,'Retained extracted text'),h('p',null,'Only plugin-generated retained article text is cleared. Imported source content is not removed; personal notes, summary and tags are unchanged.'),h(Button,{type:'button',disabled:busy||!!clearReviewed||!!state.sourceUncertain,onClick:reviewClear},'Clear retained extracted text'),clearReviewed&&h('div',null,h('p',null,'Remove retained extracted text from item revision '+clearReviewed.expected_revision+'? This does not remove imported source text.'),h('div',{className:'hb-ai-actions'},h(Button,{type:'button',disabled:busy,onClick:()=>{state.sourceReview=null;changed();}},'Keep retained text'),h(Button,{type:'button',disabled:busy||!!state.sourceUncertain,onClick:()=>clearSource(clearReviewed)},'Confirm clear retained text'))),state.sourceUncertain&&h(Button,{type:'button',disabled:busy,onClick:checkClear},'Check retained text removal')),
   state.error&&h('p',{role:'alert',className:'hb-error'},state.error));
 };
}
