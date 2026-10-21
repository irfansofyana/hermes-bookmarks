function createLibraryNavigation(React,adapter,components){
 const {createElement:h,useState,useEffect,useRef}=React,Button=components.Button||'button',Input=components.Input||'input',Dialog=createLibraryDialog(React,components);
 function CollectionLevel({ctx,scope,parentId,query,onQueryChange,search,revision,onManage,depth=0}){
  const [rows,setRows]=useState([]),[expanded,setExpanded]=useState(new Set()),[total,setTotal]=useState(0),[offset,setOffset]=useState(0),[error,setError]=useState('');
  useEffect(()=>{setOffset(0);},[search,parentId]);
  useEffect(()=>{let active=true;let path='/collections?limit=50&offset='+offset+'&query='+encodeURIComponent(search);if(parentId)path+='&parent_id='+encodeURIComponent(parentId);
   bookmarkRequest(adapter,ctx,scope,path).then(payload=>{if(active){setRows(previous=>offset?[...previous,...payload.result.collections]:payload.result.collections);setTotal(payload.result.total);setError('');}}).catch(error=>{if(active)setError(error.message);});return()=>{active=false;};
  },[ctx,scope,parentId,search,offset,revision]);
  return h('div',{className:'hb-collection-level'},error&&h('p',{role:'alert'},error),h('ul',null,rows.map(row=>h('li',{key:row.id},
   h('div',{className:'hb-collection-row'},!search&&h(Button,{type:'button','aria-label':(expanded.has(row.id)?'Collapse ':'Expand ')+row.name,'aria-expanded':expanded.has(row.id),disabled:depth>=15,onClick:()=>setExpanded(previous=>{const next=new Set(previous);if(next.has(row.id))next.delete(row.id);else next.add(row.id);return next;})},expanded.has(row.id)?'▾':'▸'),
    h(Button,{type:'button','aria-label':'Collection '+(row.path||[{name:row.name}]).map(part=>part.name).join(' / '),'aria-current':query.collectionId===row.id?'page':undefined,onClick:()=>onQueryChange({view:'all',collectionId:row.id})},search?(row.path||[{name:row.name}]).map(part=>part.name).join(' / '):row.name,h('span',{className:'hb-count'},row.count||0)),
    h(Button,{type:'button','aria-label':'Manage collection '+row.name,onClick:()=>onManage(row)},'⋯')),
   !search&&expanded.has(row.id)&&depth<15&&h(CollectionLevel,{ctx,scope,parentId:row.id,query,onQueryChange,search:'',revision,onManage,depth:depth+1})))),rows.length<total&&h(Button,{type:'button',onClick:()=>setOffset(rows.length)},'More collections'));
 }
 return function LibraryNavigation({ctx,scope,libraryId,query,onQueryChange,onChanged,revision=0}){
  const [counts,setCounts]=useState({}),[tagRows,setTagRows]=useState([]),[tagTotal,setTagTotal]=useState(0),[tagOffset,setTagOffset]=useState(0),[tagQuery,setTagQuery]=useState(''),[collectionSearch,setCollectionSearch]=useState('');
  const [edit,setEdit]=useState(null),[error,setError]=useState(''),[saving,setSaving]=useState(false),[confirm,setConfirm]=useState(false),[parentRows,setParentRows]=useState([]),[parentQuery,setParentQuery]=useState('');
  const alive=useRef(true),busy=useRef(false);
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  useEffect(()=>{let active=true;bookmarkRequest(adapter,ctx,scope,'/counts').then(payload=>{if(active)setCounts(payload.result);}).catch(error=>{if(active)setError(error.message);});return()=>{active=false;};},[ctx,scope,revision]);
  useEffect(()=>{let active=true;bookmarkRequest(adapter,ctx,scope,'/tags?limit=50&offset='+tagOffset+'&query='+encodeURIComponent(tagQuery)).then(payload=>{if(active){setTagRows(previous=>tagOffset?[...previous,...payload.result.tags]:payload.result.tags);setTagTotal(payload.result.total);}}).catch(error=>{if(active)setError(error.message);});return()=>{active=false;};},[ctx,scope,tagOffset,tagQuery,revision]);
  useEffect(()=>{if(!edit)return;let active=true;bookmarkRequest(adapter,ctx,scope,'/collections?limit=100&query='+encodeURIComponent(parentQuery)).then(payload=>{if(active)setParentRows(payload.result.collections);}).catch(error=>{if(active)setError(error.message);});return()=>{active=false;};},[!!edit,parentQuery]);
  function manage(row){setError('');setConfirm(false);setParentQuery('');setEdit({id:row?.id||null,name:row?.name||'',parent_id:row?.parent_id||null,revision:row?.revision,initial:JSON.stringify({name:row?.name||'',parent_id:row?.parent_id||null}),deleting:false,policy:''});}
  function editField(name,value){setEdit(current=>current?{...current,[name]:value}:current);}
  function close(){if(busy.current)return;if(edit&&JSON.stringify({name:edit.name,parent_id:edit.parent_id})!==edit.initial)setConfirm(true);else setEdit(null);}
  async function mutate(event){
   event.preventDefault();if(busy.current||!edit)return;busy.current=true;setSaving(true);setError('');const target=edit;
   try{let path='/collections',body={name:target.name,parent_id:target.parent_id};
    if(target.id){path+='/'+encodeURIComponent(target.id)+(target.deleting?'/delete':'/update');body=target.deleting?{expected_revision:target.revision,contents_policy:target.policy}:{expected_revision:target.revision,changes:{name:target.name,parent_id:target.parent_id}};}
    await bookmarkRequest(adapter,ctx,scope,path,{method:'POST',body});if(alive.current){setEdit(null);onChanged();}
   }catch(error){if(alive.current)setError(error.message);}finally{busy.current=false;if(alive.current)setSaving(false);}
  }
  return h('nav',{className:'hb-library-navigation','aria-label':'Library navigation'},
   h('div',{className:'hb-system-views'},[['all','All items'],['inbox','Inbox'],['favorites','Favorites'],['read_later','Read later']].map(([view,label])=>h(Button,{key:view,type:'button','aria-label':label,'aria-current':query.view===view&&!query.collectionId?'page':undefined,onClick:()=>onQueryChange({view,collectionId:null})},h('span',null,label),h('span',{className:'hb-count'},counts[view]??'…')))),
   h('div',{className:'hb-nav-heading'},h('h2',null,'Collections'),h(Button,{type:'button','aria-label':'New collection',onClick:()=>manage(null)},'+')),
   h(Input,{type:'search','aria-label':'Find collections',placeholder:'Find a collection',value:collectionSearch,onChange:event=>setCollectionSearch(event.target.value),onInput:event=>setCollectionSearch(event.currentTarget.value)}),
   h(CollectionLevel,{ctx,scope,parentId:null,query,onQueryChange,search:collectionSearch,revision,onManage:manage}),
   h('div',{className:'hb-nav-heading'},h('h2',null,'Tags')),
   h(Input,{type:'search','aria-label':'Find tags',placeholder:'Find a tag',value:tagQuery,onChange:event=>{setTagOffset(0);setTagQuery(event.target.value);},onInput:event=>{setTagOffset(0);setTagQuery(event.currentTarget.value);}}),
   h('div',{className:'hb-nav-tags'},tagRows.map(tag=>h(Button,{key:tag.name,type:'button','aria-label':'Tag '+tag.name,'aria-pressed':query.tags.includes(tag.name),onClick:()=>onQueryChange({tags:query.tags.includes(tag.name)?query.tags.filter(name=>name!==tag.name):[...query.tags,tag.name]})},'#'+tag.name,h('span',{className:'hb-count'},tag.count)))),
   tagRows.length<tagTotal&&h(Button,{type:'button',onClick:()=>setTagOffset(tagRows.length)},'More tags'),
   error&&!edit&&h('p',{role:'alert',className:'hb-error'},error),
   edit&&h(Dialog,{title:edit.deleting?'Delete collection':edit.id?'Manage collection':'New collection',description:'Collections organize shared items. Deleting a collection never deletes its bookmarks.',onCloseRequest:close},
    confirm?h('section',null,h('p',null,'Discard these unsaved collection changes?'),h(Button,{type:'button',onClick:()=>setConfirm(false)},'Keep editing'),h(Button,{type:'button',onClick:()=>setEdit(null)},'Discard')):
    h('form',{onSubmit:mutate,className:'hb-item-form'},
     edit.deleting?h('label',{className:'hb-field'},'Move contents',h('select',{'aria-label':'Collection contents policy',value:edit.policy,required:true,onChange:event=>editField('policy',event.target.value)},h('option',{value:''},'Choose where items and child collections go'),h('option',{value:'move_to_parent'},'Move to parent / Inbox'),h('option',{value:'move_to_inbox'},'Move to Inbox / root'))):h(React.Fragment,null,
      h('label',{className:'hb-field'},'Collection name',h(Input,{'aria-label':'Collection name',required:true,maxLength:100,value:edit.name,onChange:event=>editField('name',event.target.value),onInput:event=>editField('name',event.currentTarget.value)})),
      h('label',{className:'hb-field'},'Find parent collection',h(Input,{'aria-label':'Find parent collection',value:parentQuery,onChange:event=>setParentQuery(event.target.value)})),
      h('label',{className:'hb-field'},'Parent collection',h('select',{'aria-label':'Parent collection',value:edit.parent_id||'',onChange:event=>editField('parent_id',event.target.value||null)},h('option',{value:''},'Root'),edit.parent_id&&!parentRows.some(row=>row.id===edit.parent_id)&&h('option',{value:edit.parent_id},'Current parent'),parentRows.filter(row=>row.id!==edit.id).map(row=>h('option',{key:row.id,value:row.id},(row.path||[{name:row.name}]).map(part=>part.name).join(' / ')))))),
     error&&h('p',{role:'alert',className:'hb-error'},error),h('div',{className:'hb-form-actions'},edit.id&&!edit.deleting&&h(Button,{type:'button',disabled:saving,onClick:()=>setEdit(current=>({...current,deleting:true}))},'Delete collection'),h(Button,{type:'button',disabled:saving,onClick:close},'Cancel'),h(Button,{type:'submit',disabled:saving||(edit.deleting&&!edit.policy)},saving?'Saving…':edit.deleting?'Confirm delete':'Save collection')))));
 };
}
