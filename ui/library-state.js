const bookmarkLibraryDrafts=new Map(),bookmarkLibraryViews=new Map(),bookmarkCollectionDrafts=new Map();
function bookmarkDraftChanged(draft){for(const listener of [...(draft.listeners||[])])listener();}
function bookmarkScopeCheck(adapter,scope){if(adapter.currentScope&&adapter.currentScope()!==scope){const error=Error('The connection or profile changed. Reopen this library.');error.code='scope_changed';error.dispatched=false;throw error;}}
function bookmarkPayload(payload){
 if(!payload?.ok){const detail=payload?.error,error=Error(typeof detail?.message==='string'?detail.message.slice(0,2000):'The library request failed.');error.code=typeof detail?.code==='string'?detail.code:'invalid_response';if(Number.isSafeInteger(detail?.current_revision)&&detail.current_revision>0)error.current_revision=detail.current_revision;throw error;}
 return payload;
}
function bookmarkHostError(error){
 // Public Dashboard ApiError exposes status + a raw body, unlike ctx.rest.
 if(Number.isInteger(error?.status)&&error.status>=400&&error.status<=599&&typeof error.body==='string'&&error.body.length<=131072){
  try{const body=JSON.parse(error.body);if(body?.ok===false&&['invalid_argument','invalid_url','not_found','conflict','configuration_error','storage_error'].includes(body.error?.code)){try{bookmarkPayload(body);}catch(domain){return domain;}}}catch{}
 }
 return error;
}
async function bookmarkOwnedRequest(adapter,ctx,scope,route,init){
 bookmarkScopeCheck(adapter,scope);
 try{return bookmarkPayload(await adapter.request(ctx,route,init));}catch(error){throw bookmarkHostError(error);}
}
function bookmarkLibraryKey(scope,libraryId){let connection=scope;try{const value=JSON.parse(scope);if(Array.isArray(value))connection=value[0];}catch{}return JSON.stringify([connection,libraryId]);}
function bookmarkItemName(item){return item.title||item.url||'Untitled image';}
function bookmarkQuery(state){const params=new URLSearchParams({query:state.query||'',view:state.view||'all',limit:String(state.limit||50),offset:String(state.offset||0)});if(state.collectionId)params.set('collection_id',state.collectionId);for(const tag of state.tags||[])params.append('tag',tag);return params.toString();}
async function bookmarkRequest(adapter,ctx,scope,route,init){
 const payload=await bookmarkOwnedRequest(adapter,ctx,scope,route,init);bookmarkScopeCheck(adapter,scope);return payload;
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
