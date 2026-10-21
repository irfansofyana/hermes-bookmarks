function createLibraryItems(React,adapter,components){
 const {createElement:h}=React,Button=components.Button||'button',AssetImage=createBookmarkAssetImage(React,adapter);
 function source(item){if(item.kind==='image')return 'Image';try{return new URL(item.url).hostname;}catch{return 'Source unavailable';}}
 return function LibraryItems({ctx,scope,page,query,onQueryChange,onOpen,onAsk,onUpdate,selection,onSelectionChange,onTag}){
  const rows=page.items||[],total=page.total||0;
  return h(React.Fragment,null,h('ul',{'aria-label':'Saved items','data-mode':query.mode,className:'hb-items-grid'},rows.map(item=>h('li',{key:item.id,className:'hb-card'},
   h(AssetImage,{ctx,scope,assetId:item.primary_asset_id,alt:item.kind==='image'?bookmarkItemName(item):''}),
   h('div',{className:'hb-card-body'},h('div',{className:'hb-card-title'},h('input',{type:'checkbox','aria-label':'Select '+bookmarkItemName(item),checked:selection.includes(item.id),onChange:event=>onSelectionChange(item,event.target.checked)}),h(Button,{type:'button',className:'hb-title-button','aria-label':'Open details '+bookmarkItemName(item),onClick:()=>onOpen(item.id)},bookmarkItemName(item))),
    h('p',{className:'hb-source'},source(item)),item.description&&h('p',{className:'hb-card-description'},item.description.slice(0,200)),
    h('div',{className:'hb-tags'},(item.tags||[]).slice(0,6).map(tag=>h(Button,{key:tag,type:'button',className:'hb-tag','aria-label':'Filter tag '+tag,onClick:()=>onTag(tag)},tag)),item.tags?.length>6&&h('span',null,'+'+(item.tags.length-6))),
    h('p',{className:'hb-processing'},({pending:'Enrichment queued',running:'Enriching…',succeeded:'Summary saved',failed:'Enrichment failed',cancelled:'Cancelled'})[item.enrichment_status]||(item.kind==='image'?'Image saved · visual AI unavailable':'Saved')),
    h('div',{className:'hb-card-actions'},h(Button,{type:'button','aria-label':(item.favorite?'Remove favorite ':'Mark favorite ')+bookmarkItemName(item),'aria-pressed':!!item.favorite,onClick:()=>onUpdate(item,{favorite:!item.favorite})},item.favorite?'★':'☆'),h(Button,{type:'button','aria-label':(item.read_later?'Remove from read later ':'Read later ')+bookmarkItemName(item),'aria-pressed':!!item.read_later,onClick:()=>onUpdate(item,{read_later:!item.read_later})},item.read_later?'Read later ✓':'Read later'),h(Button,{type:'button',onClick:()=>onAsk?.(item)},'Ask Hermes')))))),
   h('nav',{className:'hb-pagination','aria-label':'Item pages'},h(Button,{type:'button',disabled:query.offset===0,onClick:()=>onQueryChange({offset:Math.max(0,query.offset-query.limit)})},'Previous page'),h('span',null,total?`${query.offset+1}–${Math.min(query.offset+rows.length,total)} of ${total}`:'0 items'),h(Button,{type:'button',disabled:query.offset+query.limit>=total,onClick:()=>onQueryChange({offset:query.offset+query.limit})},'Next page')));
 };
}
