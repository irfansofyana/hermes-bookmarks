const bookmarkLibraryDrafts=new Map(),bookmarkLibraryViews=new Map();
function bookmarkLibraryKey(scope,libraryId){let connection=scope;try{const value=JSON.parse(scope);if(Array.isArray(value))connection=value[0];}catch{}return JSON.stringify([connection,libraryId]);}
function bookmarkItemName(item){return item.title||item.url||'Untitled image';}
function bookmarkQuery(state){const params=new URLSearchParams({query:state.query||'',view:state.view||'all',limit:String(state.limit||50),offset:String(state.offset||0)});if(state.collectionId)params.set('collection_id',state.collectionId);for(const tag of state.tags||[])params.append('tag',tag);return params.toString();}
async function bookmarkRequest(adapter,ctx,scope,route,init){
 const check=()=>{if(adapter.currentScope&&adapter.currentScope()!==scope){const error=Error('The connection or profile changed. Reopen this library.');error.code='scope_changed';throw error;}};
 check();const payload=await adapter.request(ctx,route,init);check();
 if(!payload?.ok){const error=Error(payload?.error?.message||'The library request failed.');error.code=payload?.error?.code||'invalid_response';error.current_revision=payload?.error?.current_revision;throw error;}
 return payload;
}
function createBookmarkAssetImage(React,adapter){
 const {createElement:h,useEffect,useRef,useState}=React;
 return function AssetImage({ctx,scope,assetId,alt=''}){
  const [preview,setPreview]=useState(null),[failed,setFailed]=useState(false),anchor=useRef(null);
  useEffect(()=>{let active=true,observer;setPreview(null);setFailed(false);if(!assetId)return;
   const load=()=>bookmarkRequest(adapter,ctx,scope,'/assets/'+encodeURIComponent(assetId)+'/preview').then(payload=>{if(active&&['image/png','image/jpeg','image/webp'].includes(payload.result.mime_type))setPreview(payload.result);}).catch(()=>{if(active)setFailed(true);});
   if(typeof IntersectionObserver!=='undefined'&&anchor.current){observer=new IntersectionObserver(entries=>{if(entries.some(row=>row.isIntersecting)){observer.disconnect();load();}},{rootMargin:'200px'});observer.observe(anchor.current);}else load();
   return()=>{active=false;observer?.disconnect();};
  },[ctx,scope,assetId]);
  return h('div',{className:'hb-cover',ref:anchor},preview?h('img',{src:'data:'+preview.mime_type+';base64,'+preview.content_base64,alt,loading:'lazy'}):h('span',{'aria-label':failed?'Image unavailable':'No cover'},failed?'Image unavailable':'↗'));
 };
}
