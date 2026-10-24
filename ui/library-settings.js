// Session-only drafts include the full connection/profile/library identity.
const bookmarkSettingsDrafts=new Map();
const bookmarkAIEditable=['provider','model','automatic_tags','automatic_summary','image_analysis','summary_language','summary_length','preferred_tags','guidance','retain_extracted_text','paused'];
function bookmarkSettingsEnvelope(record){
 if(!record||!Number.isSafeInteger(record.revision)||record.revision<1||!record.settings||typeof record.route_ready!=='boolean')throw Error('AI settings response is invalid.');
 const settings=record.settings;
 for(const name of ['provider','model','owner_profile','summary_language','summary_length','guidance'])if(typeof settings[name]!=='string')throw Error('AI settings response is incomplete.');
 for(const name of ['automatic_tags','automatic_summary','image_analysis','retain_extracted_text','paused'])if(typeof settings[name]!=='boolean')throw Error('AI settings response is incomplete.');
 if(!Array.isArray(settings.preferred_tags)||!settings.preferred_tags.every(tag=>typeof tag==='string'))throw Error('AI settings response is incomplete.');
 return record;
}
function createLibrarySettings(React,adapter,components){
 const {createElement:h,useEffect,useRef,useState}=React,Button=components.Button||'button',Input=components.Input||'input',Dialog=createLibraryDialog(React,components);
 const copy=record=>({...record.settings,preferred_tags:record.settings.preferred_tags.join('\n')});
 const fresh=()=>({base:null,value:null,phase:'editing',request:null,readback:null,readBusy:false,readEpoch:0,health:null,healthError:'',error:'',notice:'',confirmClose:false,completion:0,delivered:0,listeners:new Set()});
 return function LibrarySettings({ctx,scope,libraryId,open,onClose,onChanged}){
  const key=JSON.stringify([scope,libraryId]);if(!bookmarkSettingsDrafts.has(key))bookmarkSettingsDrafts.set(key,fresh());
  const state=bookmarkSettingsDrafts.get(key),owner=useRef(null),callbacks=useRef(null),[,paint]=useState(0);callbacks.current={onClose,onChanged};
  const current=()=>owner.current?.active&&owner.current.state===state&&!state.discarded&&(!adapter.currentScope||adapter.currentScope()===scope);
  const changed=()=>{if(!state.discarded)bookmarkDraftChanged(state);};
  const owned=async(route,init)=>bookmarkOwnedRequest(adapter,ctx,scope,route,init);
  const dirty=()=>state.value&&JSON.stringify(state.value)!==JSON.stringify(copy(state.base));
  useEffect(()=>{const lease={active:true,state};owner.current=lease;
   const listener=()=>{if(!current())return;paint(n=>n+1);if(state.delivered<state.completion){state.delivered=state.completion;callbacks.current.onChanged?.();}};
   state.listeners.add(listener);listener();return()=>{lease.active=false;state.listeners.delete(listener);};
  },[state]);
  useEffect(()=>{if(!open)return;let active=true;const lease=owner.current,ticket=++state.readEpoch;
   const valid=()=>active&&lease.active&&ticket===state.readEpoch&&current();
   state.readBusy=true;changed();
   owned('/settings').then(payload=>{if(!valid())return;const record=bookmarkSettingsEnvelope(payload.result);if(state.base&&record.revision<state.base.revision)return;
    if(!state.base||(!dirty()&&state.phase==='editing'&&!state.request)){state.base=record;state.value=copy(record);}
   }).catch(error=>{if(valid())state.error=error.message;}).finally(()=>{if(valid()){state.readBusy=false;changed();}});
   owned('/health').then(payload=>{if(valid()){state.health=payload;state.healthError='';changed();}}).catch(()=>{if(valid()){state.healthError='Startup observations are unavailable.';changed();}});
   return()=>{active=false;if(ticket===state.readEpoch){state.readEpoch++;state.readBusy=false;}};
  },[open,state]);
  function field(name,value){if(!current()||state.phase!=='editing'||state.readBusy)return;state.value[name]=value;state.error='';state.notice='';changed();}
  function changes(){
   const value=state.value,result={};for(const name of bookmarkAIEditable)result[name]=value[name];
   result.preferred_tags=value.preferred_tags.split(/\r?\n/).map(tag=>tag.trim()).filter(Boolean);
   if(result.preferred_tags.length>20||result.preferred_tags.some(tag=>[...tag].length>80))throw Error('Use at most 20 preferred tags, each at most 80 characters.');
   if(!result.summary_language.trim()||[...result.summary_language].length>80)throw Error('Summary language must contain 1–80 characters.');
   if([...result.guidance].length>2000||new TextEncoder().encode(result.guidance).length>8000)throw Error('Guidance is limited to 2,000 characters and 8,000 UTF-8 bytes.');
   for(const name of ['provider','model'])if([...result[name]].length>300||(result[name]&&!result[name].trim()))throw Error('Provider and model identifiers must be empty or contain 1–300 characters.');
   return result;
  }
  async function save(event){
   event.preventDefault();if(!current()||state.phase!=='editing'||state.readBusy||!state.base)return;
   let body;try{body={expected_revision:state.base.revision,changes:changes()};}catch(error){state.error=error.message;changed();return;}
   Object.freeze(body.changes.preferred_tags);Object.freeze(body.changes);Object.freeze(body);
   const request={body};state.request=request;state.phase='saving';state.error='';state.notice='';state.readback=null;changed();
   try{const record=bookmarkSettingsEnvelope((await owned('/settings',{method:'POST',body})).result);if(state.discarded||state.request!==request)return;
    state.base=record;state.value=copy(record);state.phase='editing';state.request=null;state.notice='AI settings saved. No existing items were regenerated.';state.completion++;
   }catch(error){if(state.discarded||state.request!==request)return;
    const known=['invalid_argument','configuration_error','conflict'].includes(error.code)||(error.code==='scope_changed'&&error.dispatched===false);
    state.phase=error.code==='conflict'?'conflict':known?'editing':'uncertain';
    state.error=known?error.message:'Settings Save outcome is uncertain. The original revision and options are frozen. Check the saved settings before another Save.';
    if(known)state.request=null;
   }finally{changed();}
  }
  async function inspect(){
   if(!current()||state.readBusy||state.phase==='saving')return;const lease=owner.current,ticket=++state.readEpoch;state.readBusy=true;state.error='';changed();
   try{const record=bookmarkSettingsEnvelope((await owned('/settings')).result);if(!lease.active||ticket!==state.readEpoch||!current())return;
    state.readback=record;
    if(state.phase==='uncertain'){
     const body=state.request.body,matches=record.revision>=body.expected_revision&&Object.entries(body.changes).every(([name,value])=>JSON.stringify(record.settings[name])===JSON.stringify(value));
     state.verified=matches;state.error=matches?'Saved settings verified by revision and content. Explicitly use the checked settings to continue.':'Save not verified: current revision/content does not match the frozen Save. No request was replayed. Review the saved revision before explicitly resolving this draft.';
    }
   }catch(error){if(lease.active&&ticket===state.readEpoch&&current())state.error='Could not check saved settings. Your draft and original Save are preserved. '+error.message;}
   finally{if(lease.active&&ticket===state.readEpoch&&current()){state.readBusy=false;changed();}}
  }
  function useChecked(){if(!current()||!state.readback||!state.verified||state.readBusy)return;state.base=state.readback;state.value=copy(state.readback);state.readback=null;state.request=null;state.phase='editing';state.verified=false;state.error='';state.notice='Checked saved settings selected.';state.completion++;changed();}
  function useReviewed(){if(!current()||!state.readback||state.readBusy||state.phase==='saving')return;state.base=state.readback;state.value.owner_profile=state.base.settings.owner_profile;state.request=null;state.readback=null;state.phase='editing';state.error='';state.notice='Reviewed revision selected; all local options remain in this draft. Save explicitly to replace the reviewed options.';changed();}
  function reload(){if(!state.readback||!current()||state.readBusy)return;if(!state.reloadConfirm){state.reloadConfirm=true;changed();return;}state.base=state.readback;state.value=copy(state.readback);state.request=null;state.readback=null;state.phase='editing';state.reloadConfirm=false;state.error='';state.notice='Saved settings loaded; previous local changes discarded.';changed();}
  function close(){if(!current())return;if(dirty()||['saving','uncertain','conflict'].includes(state.phase)){state.confirmClose=true;changed();}else callbacks.current.onClose();}
  function leave(){state.confirmClose=false;callbacks.current.onClose();changed();}
  function discard(){if(!current()||['saving','uncertain'].includes(state.phase))return;state.discarded=true;state.readEpoch++;bookmarkSettingsDrafts.delete(key);callbacks.current.onClose();}
  function adoptRestored(){if(!current()||state.phase!=='editing'||state.readBusy||!state.base.restored_intent)return;const restored=state.base.restored_intent;for(const name of bookmarkAIEditable)if(Object.hasOwn(restored,name))state.value[name]=name==='preferred_tags'?restored[name].join('\n'):restored[name];state.showRestored=false;state.notice='Restored options are only a local draft. Save explicitly to adopt them; execution owner is unchanged.';changed();}
  if(!open)return null;
  const locked=state.phase!=='editing'||state.readBusy,value=state.value;
  function input(label,name,props={}){return h('label',{className:'hb-field',key:name},h('span',null,label),h(Input,{'aria-label':label,value:value[name],disabled:locked,onInput:event=>field(name,event.currentTarget.value),onChange:event=>field(name,event.currentTarget.value),...props}));}
  function toggle(label,name){return h('label',{className:'hb-ai-toggle',key:name},h('input',{type:'checkbox','aria-label':label,checked:value[name],disabled:locked,onChange:event=>field(name,event.currentTarget.checked)}),h('span',null,label));}
  return h(Dialog,{className:'hb-dialog-settings',title:'Library AI settings',description:'Shared-library processing, independent of the active chat model. Drafts stay in this client session only.',onCloseRequest:close},
   state.confirmClose?h('section',{'aria-label':'Unsaved AI settings'},h('h3',null,'Keep or discard this settings draft?'),h('p',null,'An accepted Save cannot be undone by closing. An unresolved Save stays frozen until checked.'),h('div',{className:'hb-ai-actions'},h(Button,{type:'button',onClick:()=>{state.confirmClose=false;changed();}},'Keep editing settings'),h(Button,{type:'button',onClick:leave},'Close and keep settings draft'),h(Button,{type:'button',disabled:['saving','uncertain'].includes(state.phase),onClick:discard},'Discard settings draft'))):h('form',{className:'hb-settings-form',onSubmit:save},
    !value?h('p',{role:'status'},state.error||'Loading AI settings…'):h(React.Fragment,null,
     h('p',{className:'hb-ai-disclosure'},'Changes apply to future jobs. Existing accepted jobs retain their settings. Saving does not regenerate existing items.'),
     h('section',{className:'hb-ai-section','aria-label':'AI execution'},h('h3',null,'Execution'),input('Library provider','provider',{maxLength:300,autoComplete:'off'}),input('Library model','model',{maxLength:300,autoComplete:'off'}),h('label',{className:'hb-field'},h('span',null,'Execution owner'),h(Input,{'aria-label':'Execution owner',readOnly:true,value:value.owner_profile||'Not configured'})),
      h('p',{role:'status'},state.base.route_ready?'Saved route configured.':'Route not configured. Provider, model and a fixed execution owner are required.'),h('p',{className:'hb-muted'},'The saved owner is not proof it is online. Startup observations are not a liveness check. Model/image compatibility needs verification; Hermes owns credentials, trust, retries and fallback.'),
      h('p',{className:'hb-muted'},state.healthError||('Read-only startup observations: '+(state.health?.enrichment_startups?.length?state.health.enrichment_startups.map(row=>[row.profile,row.status||row.error_code||row.state||'observed'].filter(Boolean).join(' · ')).join('; '):'none reported.')))),
     h('section',{className:'hb-ai-section','aria-label':'Automatic processing'},h('h3',null,'Automatic processing'),toggle('Automatic tags','automatic_tags'),toggle('Automatic summaries','automatic_summary'),toggle('Analyze standalone images','image_analysis'),h('p',{className:'hb-muted'},'Both automatic fields off means no automatic job. Image analysis sends the owned primary image to the configured model and may incur charges. Attachments and inline-note images are not analyzed automatically.')),
     h('section',{className:'hb-ai-section','aria-label':'Summary preferences'},h('h3',null,'Summary preferences'),input('Summary language','summary_language',{maxLength:80,required:true}),h('label',{className:'hb-field'},h('span',null,'Summary length'),h('select',{'aria-label':'Summary length',value:value.summary_length,disabled:locked,onChange:event=>field('summary_length',event.currentTarget.value)},['short','medium','long'].map(length=>h('option',{key:length,value:length},length)))),h('p',{className:'hb-muted'},'Language and length are preferences, not exact word-count guarantees.'),h('label',{className:'hb-field'},h('span',null,'Preferred tags'),h('textarea',{'aria-label':'Preferred tags',rows:3,value:value.preferred_tags,disabled:locked,onInput:event=>field('preferred_tags',event.currentTarget.value),onChange:event=>field('preferred_tags',event.currentTarget.value)})),h('p',{className:'hb-muted'},'One tag per line; at most 20 tags, 80 characters each.'),h('label',{className:'hb-field'},h('span',null,'AI guidance'),h('textarea',{'aria-label':'AI guidance',rows:4,maxLength:2000,value:value.guidance,disabled:locked,onInput:event=>field('guidance',event.currentTarget.value),onChange:event=>field('guidance',event.currentTarget.value)})),h('p',{className:'hb-ai-disclosure'},'Do not paste secrets, API keys, passwords or endpoints into guidance. Guidance is sent to the model with source content.')),
     h('section',{className:'hb-ai-section','aria-label':'Privacy and processing'},h('h3',null,'Privacy and processing'),toggle('Retain extracted text','retain_extracted_text'),h('p',{className:'hb-muted'},'Retention affects future jobs only. Turning it off does not delete previously retained bodies; clear those separately on each item. Backups containing retained bodies are unencrypted.'),toggle('Pause processing','paused'),h('p',{className:'hb-ai-disclosure'},'Pause prevents new claims. Accepted extraction or inference may still finish and incur charges. Queue attempts and Hermes provider retries/fallback are separate.')),
     state.base.restored_intent&&h('section',{className:'hb-ai-section'},h('h3',null,'Restored AI options (inactive)'),h('p',null,'Restored intent is inert. Adoption requires a separate explicit Save and cannot transfer the execution owner.'),h(Button,{type:'button',disabled:locked,onClick:()=>{state.showRestored=true;changed();}},'Review restored AI options'),state.showRestored&&h('div',null,h('pre',{className:'hb-ai-comparison'},JSON.stringify(Object.fromEntries(bookmarkAIEditable.filter(name=>Object.hasOwn(state.base.restored_intent,name)).map(name=>[name,state.base.restored_intent[name]])),null,2)),h(Button,{type:'button',disabled:locked,onClick:adoptRestored},'Use restored options in draft')))),
    state.notice&&h('p',{role:'status'},state.notice),state.error&&h('p',{role:'alert',className:'hb-error'},state.error),
    ['conflict','uncertain'].includes(state.phase)&&h('div',{className:'hb-ai-section'},state.request&&h('p',{className:'hb-ai-id'},'Frozen settings revision '+state.request.body.expected_revision),h(Button,{type:'button',disabled:state.readBusy,onClick:inspect},state.phase==='uncertain'?'Check settings save':'Review saved settings'),state.readback&&h('section',{'aria-label':'Saved settings comparison'},h('h3',null,'Saved settings revision '+state.readback.revision),h('pre',{className:'hb-ai-comparison'},JSON.stringify(state.readback.settings,null,2)),h('p',null,'Your fields are preserved above. Selecting a revision does not Save or silently rebase; review every option before replacing the saved settings.'),state.verified?h(Button,{type:'button',disabled:state.readBusy,onClick:useChecked},'Use checked settings'):h(Button,{type:'button',disabled:state.readBusy,onClick:useReviewed},'Use reviewed settings revision'),h(Button,{type:'button',disabled:state.readBusy,onClick:reload},state.reloadConfirm?'Confirm reload saved settings':'Reload saved settings'))),
    h('footer',{className:'hb-ai-footer hb-ai-actions'},h(Button,{type:'button',onClick:close},'Cancel AI settings'),h(Button,{type:'submit','aria-label':'Save AI settings',className:'hb-primary',disabled:!value||locked},state.phase==='saving'?'Saving AI settings…':'Save AI settings'))));
 };
}
