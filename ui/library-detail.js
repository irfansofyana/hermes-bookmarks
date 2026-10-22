function createLibraryDetail(React,adapter,components){
 const {createElement:h,useState,useEffect}=React,Button=components.Button||'button',Dialog=createLibraryDialog(React,components),AssetImage=createBookmarkAssetImage(React,adapter);
 return function LibraryDetail({ctx,scope,libraryId,itemId,onEdit,onAsk,onClose}){
  const [item,setItem]=useState(null),[error,setError]=useState('');
  useEffect(()=>{let live=true;bookmarkRequest(adapter,ctx,scope,'/items/'+encodeURIComponent(itemId)).then(payload=>{if(live)setItem(payload.result);}).catch(error=>{if(live)setError(error.message);});return()=>{live=false;};},[ctx,scope,libraryId,itemId]);
  let original=null;try{const url=new URL(item?.url);if(['http:','https:'].includes(url.protocol)&&!url.username&&!url.password)original=url.href;}catch{}
  return h(Dialog,{title:item?bookmarkItemName(item):'Bookmark details',description:'Saved content in your shared library.',onCloseRequest:onClose},
   error?h('p',{role:'alert'},error):!item?h('p',{role:'status'},'Loading saved item…'):h('div',{className:'hb-item-detail'},
    original&&h('a',{href:original,target:'_blank',rel:'noopener noreferrer'},'Open original'),
    item.description&&h('p',null,item.description),h('div',{className:'hb-tags'},(item.tag_details||[]).map(tag=>h('span',{key:tag.name,className:'hb-tag',title:tag.source==='generated'?'AI-generated tag':'Manual tag'},tag.name,tag.source==='generated'?' · AI':''))),
    h('section',null,h('h3',null,'Saved AI summary'),item.summary?bookmarkMarkdown(React,item.summary):h('p',{className:'hb-muted'},item.kind==='image'?'Visual analysis is not available in this preview.':'No saved summary yet.'),h('p',{className:'hb-muted'},'Processing: '+(item.enrichment_status||'not_started'))),
    h('section',null,h('h3',null,'Personal notes'),item.notes?bookmarkMarkdown(React,item.notes):h('p',{className:'hb-muted'},'No personal notes yet.')),
    item.attachments?.length>0&&h('section',null,h('h3',null,'Images'),h('div',{className:'hb-attachments'},item.attachments.map(asset=>h(AssetImage,{key:asset.asset_id,ctx,scope,assetId:asset.asset_id,alt:asset.role==='primary'?'Primary image':'Attached image'})))),
    h('div',{className:'hb-form-actions'},!item.deleted_at&&h(Button,{type:'button',onClick:()=>onEdit(item)},'Edit'),h(Button,{type:'button',onClick:()=>{onAsk?.(item);onClose();}},'Ask Hermes'))),
   h('div',{className:'hb-form-actions'},h(Button,{type:'button',onClick:onClose},'Close details')));
 };
}
