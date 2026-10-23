function createLibrary(React,adapter,components,styles){
 const {createElement:h,useState,useEffect,useRef}=React,Button=components.Button||'button',Input=components.Input||'input';
 const Navigation=createLibraryNavigation(React,adapter,components),Items=createLibraryItems(React,adapter,components),Form=createLibraryForm(React,adapter,components),Detail=createLibraryDetail(React,adapter,components);
 const Dialog=createLibraryDialog(React,components),Import=createLibraryImport(React,adapter,components),Bulk=createLibraryBulk(React,adapter,components),Data=createLibraryData(React,adapter,components);
 const defaults=()=>({query:'',view:'all',collectionId:null,tags:[],limit:50,offset:0,mode:'grid',selectedIds:[],scroll:0});
 return function Bookmarks({ctx,scope='dashboard',onAsk,onReady}={}){
  const [libraryId,setLibraryId]=useState(null),[query,setQuery]=useState(defaults),[page,setPage]=useState({items:[],total:0}),[loading,setLoading]=useState(true),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const [form,setForm]=useState(null),[detail,setDetail]=useState(null),[revision,setRevision]=useState(0),[drawer,setDrawer]=useState(false),[search,setSearch]=useState(''),[identityRetry,setIdentityRetry]=useState(0),[narrow,setNarrow]=useState(false);
  const libraryRoot=useRef(null);
  const [dataOpen,setDataOpen]=useState(false);
  const [importOpen,setImportOpen]=useState(false),[bulkOpen,setBulkOpen]=useState(false),[noticeItem,setNoticeItem]=useState(null);
  const [trashTarget,setTrashTarget]=useState(null),[trashBusy,setTrashBusy]=useState(false),[undoTrash,setUndoTrash]=useState(null);const trashLock=useRef(false);
  useEffect(()=>{if(typeof ResizeObserver==='undefined'||!libraryRoot.current)return;const observer=new ResizeObserver(entries=>{if(entries[0])setNarrow(entries[0].contentRect.width<=680);});observer.observe(libraryRoot.current.closest('.hb-workspace-frame')||libraryRoot.current);return()=>observer.disconnect();},[]);
  const live=useRef(true),generation=useRef(0),current=useRef(null),surface=useRef(null),restored=useRef(false),selectedItems=useRef(new Map()),updating=useRef(new Set());
  current.current={query,libraryId};
  const api=(route,init)=>bookmarkRequest(adapter,ctx,scope,route,init);
  useEffect(()=>{live.current=true;let active=true;
   api('/library/identity').then(payload=>{if(!active)return;const id=payload.result.library_id;if(typeof id!=='string'||!id)throw Error('Library identity is unavailable.');
    const key=bookmarkLibraryKey(scope,id),saved=bookmarkLibraryViews.get(key)||defaults();
    if(!['grid','list'].includes(saved.mode))saved.mode='grid';if(!['all','inbox','favorites','read_later','trash'].includes(saved.view))saved.view='all';
    bookmarkLibraryViews.set(key,saved);setQuery(saved);setSearch(saved.query);setLibraryId(id);
   }).catch(error=>{if(active){setError(error.message);setLoading(false);}});
   return()=>{active=false;live.current=false;generation.current++;};
  },[ctx,scope,identityRetry]);
  useEffect(()=>{if(libraryId)bookmarkLibraryViews.set(bookmarkLibraryKey(scope,libraryId),query);},[query,libraryId]);
  async function load(state){
   if(!current.current.libraryId)return;const ticket=++generation.current;setLoading(true);
   try{const payload=await api('/items?'+bookmarkQuery(state));if(!live.current||ticket!==generation.current)return;
    const next=payload.result;if(next.total>0&&state.offset>=next.total){change({offset:Math.floor((next.total-1)/state.limit)*state.limit});return;}
    setPage(next);setError('');for(const item of next.items||[])if(state.selectedIds.includes(item.id))selectedItems.current.set(item.id,item);
   }catch(error){if(live.current&&ticket===generation.current)setError(error.message);}
   finally{if(live.current&&ticket===generation.current)setLoading(false);}
  }
  useEffect(()=>{if(libraryId)load(query);},[libraryId,query.query,query.view,query.collectionId,JSON.stringify(query.tags),query.offset,query.limit]);
  useEffect(()=>{if(!loading&&surface.current&&!restored.current){surface.current.scrollTop=query.scroll||0;restored.current=true;}},[loading]);
  function refresh(){if(!current.current.libraryId){setError('');setLoading(true);setIdentityRetry(n=>n+1);return;}load(current.current.query);setRevision(n=>n+1);}
  useEffect(()=>{onReady?.(refresh);return()=>onReady?.(null);},[libraryId]);
  function change(patch){setQuery(previous=>({...previous,...patch,offset:Object.hasOwn(patch,'offset')?patch.offset:0}));setDrawer(false);}
  function select(item,checked){if(checked&&query.selectedIds.length>=100){setNotice('Selection is limited to 100 items per action.');return;}if(checked)selectedItems.current.set(item.id,item);else selectedItems.current.delete(item.id);setQuery(previous=>({...previous,selectedIds:checked?[...new Set([...previous.selectedIds,item.id])]:previous.selectedIds.filter(id=>id!==item.id)}));}
  async function update(item,changes){if(updating.current.has(item.id))return;updating.current.add(item.id);
   try{await api('/items/'+encodeURIComponent(item.id)+'/update',{method:'POST',body:{expected_revision:item.revision,changes}});if(live.current){setNotice('Changes saved.');refresh();}}
   catch(error){if(live.current)setError(error.code==='conflict'?'This item changed elsewhere. Open it to review the saved version.':error.message);}
   finally{updating.current.delete(item.id);}
  }
  async function trashChange(item,restore=false){
   if(trashLock.current)return;trashLock.current=true;setTrashBusy(true);
   try{const result=await api('/items/'+encodeURIComponent(item.id)+(restore?'/restore':'/trash'),{method:'POST',body:{expected_revision:item.revision}});
    if(live.current){setTrashTarget(null);setDetail(null);setUndoTrash(restore?null:result.result);setNotice(restore?'Item restored.':'Moved to trash.');refresh();}}
   catch(error){if(live.current){setError(error.code==='conflict'?'This item changed elsewhere. Reload the library before trying again.':error.message);setTrashTarget(null);}}
   finally{trashLock.current=false;if(live.current)setTrashBusy(false);}
  }
  function saved(result){setForm(null);setNoticeItem(result.item?.id||null);setNotice(result.receipt?.outcome==='trashed_duplicate'?'Already in Trash. Your staged fields were not applied; restore explicitly from Trash.':result.receipt?.outcome==='duplicate'?'Already saved. Your staged fields were not applied.':'Saved to your library.');refresh();if(result.reopenEdit)setForm({item:result.item});else if(result.openExisting)setDetail(result.item.id);}
  function selectVisible(){const rows=page.items||[];for(const row of rows)selectedItems.current.set(row.id,row);const ids=[...new Set([...query.selectedIds,...rows.map(row=>row.id)])];if(ids.length>100)setNotice('Selection is limited to 100 items per action.');setQuery(previous=>({...previous,selectedIds:ids.slice(0,100)}));}
  function askSelection(){const items=query.selectedIds.map(id=>selectedItems.current.get(id)||{id,title:id});onAsk?.(items.slice(0,20));if(items.length>20)setNotice('Only the first 20 selected references were prepared. Nothing was sent.');}
  const heading=query.collectionId?'Collection · includes descendants':({all:'All items',inbox:'Inbox',favorites:'Favorites',read_later:'Read later',trash:'Trash'})[query.view];
  const navigationProps={ctx,scope,libraryId,query,onQueryChange:change,onChanged:refresh,revision,narrow,drawer,onDrawerClose:()=>setDrawer(false)};
  return h('section',{ref:libraryRoot,className:'hb-library','aria-label':'Bookmarks'},
   h('div',{className:'hb-library-topbar'},h(Button,{type:'button','aria-label':'Toggle library navigation','aria-expanded':drawer,onClick:()=>setDrawer(open=>!open)},'☰'),
    h('form',{className:'hb-search',onSubmit:event=>{event.preventDefault();change({query:search});}},h(Input,{type:'search',name:'query','aria-label':'Search bookmarks',value:search,placeholder:'Search your library…',onChange:event=>setSearch(event.target.value),onInput:event=>setSearch(event.currentTarget.value)}),h(Button,{type:'submit'},'Search')),
    h(Button,{type:'button',disabled:!libraryId,onClick:()=>setDataOpen(true)},'Data'),
    h(Button,{type:'button',disabled:!libraryId,onClick:()=>setImportOpen(true)},'Import'),
    h(Button,{type:'button',className:'hb-primary',disabled:!libraryId,onClick:()=>{setDetail(null);setForm({item:null});}},'Add')),
   error&&h('div',{role:'alert',className:'hb-error'},error,h(Button,{type:'button',onClick:refresh},'Retry library')),
   notice&&h('p',{role:'status',className:'hb-notice'},notice,notice==='Saved to your library.'&&noticeItem&&h(Button,{type:'button',onClick:()=>setDetail(noticeItem)},'View item'),undoTrash&&h(Button,{type:'button',disabled:trashBusy,onClick:()=>trashChange(undoTrash,true)},'Undo trash')),
   h('div',{className:'hb-library-layout','data-navigation-open':drawer},libraryId&&h(Navigation,navigationProps),
    h('main',{className:'hb-library-content',ref:surface,onScroll:event=>{query.scroll=event.currentTarget.scrollTop;}},
     h('div',{className:'hb-library-heading'},h('div',null,h('h1',null,heading),h('p',{className:'hb-muted',role:'status'},loading?'Loading library…':page.total+' saved items')),
      h('div',{className:'hb-view-mode'},h(Button,{type:'button',disabled:loading||!page.items.length,onClick:selectVisible},'Select visible items'),h(Button,{type:'button','aria-label':'Grid view','aria-pressed':query.mode==='grid',onClick:()=>setQuery(previous=>({...previous,mode:'grid'}))},'Grid'),h(Button,{type:'button','aria-label':'List view','aria-pressed':query.mode==='list',onClick:()=>setQuery(previous=>({...previous,mode:'list'}))},'List'))),
     h('div',{className:'hb-active-filters'},query.query&&h(Button,{type:'button',onClick:()=>{setSearch('');change({query:''});}},'Clear search: '+query.query),query.tags.map(tag=>h(Button,{key:tag,type:'button','aria-label':'Remove tag filter '+tag,onClick:()=>change({tags:query.tags.filter(name=>name!==tag)})},'#'+tag+' ×'))),
     query.selectedIds.length>0&&h('div',{className:'hb-selection-bar'},h('span',null,query.selectedIds.length+' selected'),h(Button,{type:'button',onClick:()=>setBulkOpen(true)},'Edit selection'),h(Button,{type:'button',onClick:askSelection},'Ask about selection'),h(Button,{type:'button',onClick:()=>setQuery(previous=>({...previous,selectedIds:[]}))},'Clear selection')),
     query.collectionId&&page.items.length>0&&h(Button,{type:'button',onClick:()=>{onAsk?.(page.items.slice(0,20));setNotice('Prepared up to 20 visible item references. Nothing was sent.');}},'Ask about this collection'),
     !loading&&!page.items.length&&h('div',{className:'hb-empty'},h('h2',null,query.query||query.tags.length?'No matching items':'Nothing here yet'),h('p',null,'Save something worth keeping, or try a different filter.')),
     h(Items,{ctx,scope,page,query,onQueryChange:change,onOpen:id=>setDetail(id),onAsk,onUpdate:update,onTrash:item=>item.deleted_at?trashChange(item,true):setTrashTarget(item),selection:query.selectedIds,onSelectionChange:select,onTag:tag=>change({tags:query.tags.includes(tag)?query.tags:[...query.tags,tag]})}))),

   libraryId&&h(Data,{key:'data-'+JSON.stringify([scope,libraryId]),ctx,scope,libraryId,open:dataOpen,onClose:()=>setDataOpen(false),onChanged:refresh}),
   libraryId&&h(Bulk,{key:'bulk-'+JSON.stringify([scope,libraryId]),ctx,scope,libraryId,ids:query.selectedIds,open:bulkOpen,onClose:()=>setBulkOpen(false),onChanged:refresh,onInspect:id=>{setBulkOpen(false);setDetail(id);}}),
   libraryId&&h(Import,{key:JSON.stringify([scope,libraryId]),ctx,scope,libraryId,open:importOpen,onClose:()=>setImportOpen(false),onChanged:refresh}),
   trashTarget&&h(Dialog,{title:'Move to trash?',description:'Notes and images are kept. You can restore this item later.',onCloseRequest:()=>{if(!trashBusy)setTrashTarget(null);}},h('p',null,bookmarkItemName(trashTarget)),h(Button,{type:'button',disabled:trashBusy,onClick:()=>setTrashTarget(null)},'Cancel'),h(Button,{type:'button',disabled:trashBusy,onClick:()=>trashChange(trashTarget)},trashBusy?'Moving…':'Move to trash')),
   form&&h(Form,{key:form.item?JSON.stringify([form.item.id,form.item.revision]):'new',ctx,scope,libraryId,item:form.item,defaultCollection:query.collectionId,onSaved:saved,onClose:()=>setForm(null)}),
   detail&&!form&&h(Detail,{key:detail,ctx,scope,libraryId,itemId:detail,onEdit:item=>{setDetail(null);setForm({item});},onAsk,onClose:()=>setDetail(null)}));
 };
}
