// Bounded, explicit selection edits over the existing revision-checked API.
// No background scheduler, retries, rebase or all-or-nothing promise.
const bookmarkBulkReports=new Map();
function createLibraryBulk(React,adapter,components){
 const {createElement:h,useRef,useState,useEffect}=React,Button=components.Button||'button',Dialog=createLibraryDialog(React,components);
 const fresh=()=>({phase:'idle',completion:0,action:'favorite_on',tags:'',collection:null,rows:[],error:'',stop:false,acknowledged:false,listeners:new Set()});
 const actions=[['favorite_on','Add to Favorites'],['favorite_off','Remove from Favorites'],['read_later_on','Mark Read later'],['read_later_off','Remove Read later'],['move','Move to collection'],['add_tags','Add tags'],['remove_tags','Remove tags'],['trash','Move to Trash'],['restore','Restore from Trash']];
 function tags(text){
  const result=[];let label='',quoted=false;
  for(let i=0;i<text.length;i++){const char=text[i];if(char==='"'){if(quoted&&text[i+1]==='"'){label+='"';i++;}else quoted=!quoted;}else if(char===','&&!quoted){if(label.trim())result.push(label.trim());label='';}else label+=char;}
  if(quoted)throw Error('Close the quoted tag before applying.');if(label.trim())result.push(label.trim());
  if(!result.length||result.length>20||result.some(tag=>tag.length>80))throw Error('Enter 1–20 tags, at most 80 characters each. Quote a tag containing commas.');
  return [...new Set(result)];
 }
 return function LibraryBulk({ctx,scope,libraryId,ids,open,onClose,onChanged,onInspect}){
  const key=JSON.stringify([scope,libraryId]);if(!bookmarkBulkReports.has(key))bookmarkBulkReports.set(key,fresh());
  const state=useRef(bookmarkBulkReports.get(key)).current,alive=useRef(true),callbacks=useRef(null),[,paint]=useState(0);
  const [query,setQuery]=useState(''),[offset,setOffset]=useState(0),[collections,setCollections]=useState([]),[collectionTotal,setCollectionTotal]=useState(0);
  callbacks.current={ids,onClose,onChanged,onInspect};
  const owned=(route,init)=>bookmarkOwnedRequest(adapter,ctx,scope,route,init);
  const current=()=>alive.current&&(!adapter.currentScope||adapter.currentScope()===scope);
  const changed=()=>bookmarkDraftChanged(state);
  useEffect(()=>{alive.current=true;let completion=state.completion;const listener=()=>{if(!current())return;paint(n=>n+1);if(completion!==state.completion){completion=state.completion;callbacks.current.onChanged();}};state.listeners.add(listener);return()=>{alive.current=false;state.stop=true;state.listeners.delete(listener);};},[]);
  async function review(){
   if(['loading','running'].includes(state.phase))return;
   const selected=[...new Set(callbacks.current.ids)];if(!selected.length||selected.length>100){state.error='Choose between 1 and 100 items. No changes were sent.';changed();return;}
   state.phase='loading';state.stop=false;state.error='';state.acknowledged=false;state.rows=selected.map(id=>({id,status:'not_processed'}));changed();
   for(const row of state.rows){
    if(state.stop||!current())break;
    try{const result=(await owned('/items/'+encodeURIComponent(row.id))).result;
     if(result.id!==row.id||!Number.isSafeInteger(result.revision)||result.revision<1)throw Error('Saved item revision is unavailable.');
     row.item=result;row.status='ready';
    }catch(error){row.status='failed';row.message=error.code==='not_found'?'Item no longer exists.':error.message;}
    changed();
   }
   state.phase='review';changed();
  }
  useEffect(()=>{if(open&&state.phase==='idle')review();},[open]);
  useEffect(()=>{if(!open||state.action!=='move')return;let active=true;
   owned('/collections?limit=50&offset='+offset+'&query='+encodeURIComponent(query)).then(payload=>{if(active&&current()){setCollections(old=>offset?[...old,...payload.result.collections]:payload.result.collections);setCollectionTotal(payload.result.total);}}).catch(error=>{if(active&&current()){state.error=error.message;changed();}});
   return()=>{active=false;};
  },[open,state.action,query,offset]);
  function changes(){
   if(state.action==='move')return {collection_id:state.collection};
   if(state.action==='add_tags'||state.action==='remove_tags')return {[state.action]:tags(state.tags)};
   if(state.action.startsWith('favorite_'))return {favorite:state.action==='favorite_on'};
   if(state.action.startsWith('read_later_'))return {read_later:state.action==='read_later_on'};
   return null;
  }
  async function apply(){
   if(state.phase!=='review'||!current())return;
   let fields;try{fields=changes();}catch(error){state.error=error.message;changed();return;}
   const action=state.action;state.phase='running';state.stop=false;state.error='';changed();
   for(const row of state.rows){
    if(row.status!=='ready')continue;
    if(state.stop||!current())break;
    const item=row.item;
    if(action==='restore'?!item.deleted_at:!!item.deleted_at){row.status='skipped';row.message=action==='restore'?'Already active.':'Item is in Trash; restore it first.';changed();continue;}
    row.status='running';changed();
    const route='/items/'+encodeURIComponent(row.id)+(action==='trash'?'/trash':action==='restore'?'/restore':'/update');
    const body={expected_revision:item.revision};if(fields)body.changes=fields;
    try{const result=await owned(route,{method:'POST',body});row.status='applied';row.saved=result.result;}
    catch(error){
     if(error.code==='conflict'){row.status='conflict';row.message='Changed since review. Inspect and review a new action; no automatic overwrite.';}
     else if(['invalid_argument','invalid_url','not_found','configuration_error'].includes(error.code)||(error.code==='scope_changed'&&error.dispatched===false)){row.status='failed';row.message=error.message;}
     else{row.status='uncertain';row.message='Acknowledgement was lost. Inspect the saved item before another action. No automatic retry.';state.stop=true;}
    }
    changed();
   }
   for(const row of state.rows)if(row.status==='ready')row.status='not_processed';
   state.phase='done';state.completion++;changed();
  }
  function close(){
   if(['loading','running'].includes(state.phase)){state.stop=true;state.error='Stopping after the current request. Already accepted changes are kept.';changed();return;}
   callbacks.current.onClose();
  }
  if(!open)return null;
  const busy=['loading','running'].includes(state.phase),uncertain=state.rows.some(row=>row.status==='uncertain');
  const count=status=>state.rows.filter(row=>row.status===status).length;
  return h(Dialog,{title:'Edit selected items',description:'Review up to 100 explicit items. Each change checks its reviewed revision; successful changes are kept if another item fails.',className:'hb-dialog-bulk',onCloseRequest:close},
   state.phase==='loading'?h('div',null,h('p',{role:'status'},'Reading selected items…'),h(Button,{type:'button',onClick:()=>{state.stop=true;changed();}},'Stop remaining changes')):
   h('section',{className:'hb-bulk-review','aria-label':'Selection review'},h('p',null,state.rows.length+' items reviewed'),h('p',{className:'hb-muted'},'Action: '+actions.find(([key])=>key===state.action)[1]),
    state.phase==='review'&&h(React.Fragment,null,h('label',{className:'hb-field'},'Action',h('select',{'aria-label':'Bulk action',value:state.action,onChange:event=>{state.action=event.target.value;state.error='';changed();}},actions.map(([value,label])=>h('option',{key:value,value},label)))),
     ['add_tags','remove_tags'].includes(state.action)&&h('label',{className:'hb-field'},'Tags',h('textarea',{'aria-label':'Selection tags',value:state.tags,rows:2,onInput:event=>{state.tags=event.currentTarget.value;changed();},onChange:event=>{state.tags=event.target.value;changed();}}),h('span',{className:'hb-muted'},'Comma-separated; quote a tag containing commas. Other tags and notes are kept.')),
     state.action==='move'&&h(React.Fragment,null,h('label',{className:'hb-field'},'Find collection',h('input',{'aria-label':'Selection collection search',value:query,onInput:event=>{const value=event.currentTarget.value;setOffset(0);setQuery(value);},onChange:event=>{setOffset(0);setQuery(event.target.value);}})),h('label',{className:'hb-field'},'Destination',h('select',{'aria-label':'Selection collection',value:state.collection||'',onChange:event=>{state.collection=event.target.value||null;changed();}},h('option',{value:''},'Inbox'),state.collection&&!collections.some(row=>row.id===state.collection)&&h('option',{value:state.collection},'Selected collection'),collections.map(row=>h('option',{key:row.id,value:row.id},(row.path||[{name:row.name}]).map(part=>part.name).join(' / '))))),collections.length<collectionTotal&&h(Button,{type:'button',onClick:()=>setOffset(collections.length)},'More selection collections')),
     state.action==='trash'&&h('p',{className:'hb-bulk-warning'},'These items will be kept in Trash with their notes and images. Apply confirms this change; nothing is permanently deleted.'),
     state.action==='restore'&&h('p',null,'Restore only trashed items. Active items are skipped. No enrichment is started.')),
    state.phase!=='review'&&h('p',{role:'status'},`Applied: ${count('applied')} · Conflicts: ${count('conflict')} · Failed: ${count('failed')} · Skipped: ${count('skipped')} · Uncertain: ${count('uncertain')} · Not processed: ${count('not_processed')+count('ready')}`),
    h('ul',{className:'hb-bulk-results'},state.rows.map(row=>h('li',{key:row.id},h('span',null,row.item?bookmarkItemName(row.item):row.id),h('span',{className:'hb-muted'},' · '+row.status.replaceAll('_',' ')),row.message&&h('p',null,row.message),['conflict','uncertain','applied'].includes(row.status)&&h(Button,{type:'button',disabled:busy,onClick:()=>callbacks.current.onInspect(row.id)},'Inspect saved item '+(row.item?bookmarkItemName(row.item):row.id))))),
    state.phase==='done'&&h('p',{className:'hb-muted'},'This report stays in this session only. Reloading the page loses it. An interrupted batch never resumes automatically.'),
    state.phase==='done'&&uncertain&&h('label',null,h('input',{type:'checkbox','aria-label':'I inspected uncertain outcomes',checked:state.acknowledged,onChange:event=>{state.acknowledged=event.target.checked;changed();}}),' I inspected uncertain outcomes before starting a new action.'),
    h('div',{className:'hb-form-actions'},state.phase==='review'&&h(Button,{type:'button',onClick:review},'Review current selection'),state.phase==='review'&&h(Button,{type:'button',disabled:busy||count('ready')===0,onClick:apply},'Apply to '+state.rows.length+' items'),busy&&h(Button,{type:'button',onClick:()=>{state.stop=true;changed();}},'Stop remaining changes'),state.phase==='done'&&h(Button,{type:'button',disabled:uncertain&&!state.acknowledged,onClick:review},'Review a new action'),h(Button,{type:'button',disabled:busy,onClick:close},'Close bulk actions'))),
   state.error&&h('p',{role:'alert',className:'hb-error'},state.error));
 };
}
