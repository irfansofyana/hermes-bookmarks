'use strict';
// Protocol fixtures only: these doubles do not establish host/model acceptance.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const React=require('react'),{JSDOM}=require('jsdom'),{webcrypto}=require('node:crypto');
async function flush(){await React.act(async()=>{await new Promise(resolve=>setImmediate(resolve));});}
function button(app,name){return [...app.element.querySelectorAll('button')].find(node=>(node.getAttribute('aria-label')||node.textContent.trim())===name);}
async function click(node,app){assert.ok(node,'Expected control');await React.act(async()=>node.dispatchEvent(new app.dom.window.MouseEvent('click',{bubbles:true,cancelable:true})));}
async function typeField(app,label,value){const node=app.field(label);assert.ok(node,'Expected '+label);await React.act(async()=>{const proto=node.tagName==='TEXTAREA'?app.dom.window.HTMLTextAreaElement.prototype:node.tagName==='SELECT'?app.dom.window.HTMLSelectElement.prototype:app.dom.window.HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,'value').set.call(node,value);node.dispatchEvent(new app.dom.window.Event('input',{bubbles:true}));node.dispatchEvent(new app.dom.window.Event('change',{bubbles:true}));});}
async function mount(target,{saved=[],overrideRpc,overrideApi,autoOpen=false}={}){
 const dom=new JSDOM('<div id="root"></div>',{url:'https://fixture.invalid'});
 global.window=dom.window;global.document=dom.window.document;global.HTMLElement=dom.window.HTMLElement;global.IS_REACT_ACT_ENVIRONMENT=true;
 // jsdom cannot implement modal focus/top-layer layout; actual-browser tests do.
 dom.window.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
 dom.window.HTMLDialogElement.prototype.close=function(){this.open=false;};
 const {createRoot}=require('react-dom/client');
 const resizeObservers=new Set();
 class ResizeObserver{constructor(callback){this.callback=callback;}observe(){resizeObservers.add(this);}disconnect(){resizeObservers.delete(this);}}
 let page,running=false,reads=0,navigations=0,profile='work',connection='fixture-backend';
 const callbacks=new Set(),calls=[],apiCalls=[],bindings=[...saved],sockets=[];
 const identity={library_id:'a'.repeat(32),profile:'work'};
 const item={id:'bookmark-a',url:'https://example.org/article',title:'A synthetic article',kind:'link',description:'',notes:'',revision:1,tags:[],tag_details:[],attachments:[],collection_id:null,favorite:false,read_later:false,summary:'',enrichment_status:'not_started'};
 const items=[item],collections=[{id:'engineering',name:'Engineering',parent_id:null,revision:1,count:1,path:[{id:'engineering',name:'Engineering'}]}];
 async function api(raw,init){
  const route=raw.replace('/api/plugins/hermes-bookmarks','');
  const body=typeof init?.body==='string'?JSON.parse(init.body):init?.body===undefined?undefined:JSON.parse(JSON.stringify(init.body));
  const request=init?{...init,body}:undefined;apiCalls.push({route,init:request});
  if(overrideApi){const result=await overrideApi(route,request);if(result!==undefined)return result;}
  const url=new URL(route,'https://fixture.invalid');
  if(url.pathname==='/library/identity')return {ok:true,result:{library_id:identity.library_id}};
  if(url.pathname==='/chat/identity')return {ok:true,result:{...identity,profile}};
  if(url.pathname==='/chat/threads'){
   if(init?.method==='POST'){const row={...body,profile,created_at:0};bindings.push(row);return {ok:true,result:row};}
   return {ok:true,result:{threads:bindings,total:bindings.length,offset:0,limit:50}};
  }
  if(url.pathname==='/counts')return {ok:true,result:{all:items.length,inbox:items.length,favorites:0,read_later:0}};
  if(url.pathname==='/collections')return {ok:true,result:{collections,total:collections.length,limit:50,offset:0}};
  if(url.pathname==='/tags')return {ok:true,result:{tags:[{name:'Reading',count:1}],total:1,limit:50,offset:0}};
  if(url.pathname==='/items'&&(!init||init.method==='GET')){reads++;return {ok:true,result:{items,total:items.length,offset:0,limit:50}};}
  if(url.pathname==='/items'&&init?.method==='POST'){
   const created={...item,...body,id:'created-bookmark',revision:1,attachments:(body.attachment_ids||[]).map(asset_id=>({asset_id,role:'attachment'}))};items.push(created);
   return {ok:true,result:created,receipt:{operation_key:body.operation_key,item_id:created.id,accepted_revision:1,outcome:'created'}};
  }
  if(url.pathname.startsWith('/items/')&&url.pathname.endsWith('/update')){const got=items.find(row=>row.id===url.pathname.split('/')[2]);Object.assign(got,body.changes,{revision:got.revision+1});return {ok:true,result:got};}
  if(url.pathname.startsWith('/items/'))return {ok:true,result:items.find(row=>row.id===url.pathname.split('/')[2])||item};
  if(url.pathname==='/assets/base64')return {ok:true,result:{id:'b'.repeat(32),mime_type:'image/png',width:2,height:2,size:72}};
  if(url.pathname.startsWith('/assets/')&&url.pathname.endsWith('/preview'))return {ok:true,result:{id:'b'.repeat(32),mime_type:'image/png',content_base64:fs.readFileSync('tests/fixtures/tiny.png').toString('base64')}};
  throw Error('Unexpected fixture API '+route);
 }
 function emit(type,payload){const event={type,profile,session_id:'runtime-chat',payload};for(const callback of callbacks)callback(event);for(const socket of sockets)socket.frame({method:'event',params:event});}
 function rpc(method,params){
  calls.push({method,params});if(overrideRpc){const result=overrideRpc(method,params);if(result!==undefined)return result;}
  if(method==='client.capabilities')return {ok:true};
  if(method==='model.options')return {providers:[{slug:'fixture',name:'Fixture',authenticated:true,models:['synthetic']}]};
  if(method==='session.create')return {session_id:'runtime-chat',stored_session_id:'stored-chat'};
  if(method==='prompt.submit'){running=true;return {status:'streaming',user_row_id:1};}
  if(method==='session.activate')return {session_id:'runtime-chat',running,open_requests:[]};
  if(method==='session.history')return {messages:[{role:'user',text:'A question'},{role:'assistant',text:'Saved answer'}]};
  if(method==='session.resume')return {session_id:'runtime-chat',stored_session_id:params.session_id,running,messages:[{role:'assistant',text:'Saved answer'}],open_requests:[]};
  if(method==='session.interrupt'){running=false;return {status:'interrupted'};}
  if(['request.answer','clarify.lock'].includes(method))return {status:'ok',remaining:[]};
  if(method==='gateway.ping')return {pong:true};
  throw Error('Unexpected fixture RPC '+method);
 }
 class Socket extends EventTarget{
  constructor(){super();sockets.push(this);this.readyState=0;queueMicrotask(()=>{this.readyState=1;this.dispatchEvent(new Event('open'));});}
  frame(frame){const event=new Event('message');event.data=JSON.stringify(frame);this.dispatchEvent(event);}
  send(raw){const frame=JSON.parse(raw);if(frame.method)queueMicrotask(async()=>{try{this.frame({id:frame.id,result:await rpc(frame.method,frame.params)});}catch(error){this.frame({id:frame.id,error:{code:-32603,message:error.message}});}});}
  close(){this.readyState=3;}
 }
 const host={state:{profile:{get:()=>profile},connectionId:{get:()=>connection},gateway:{get:()=> 'open'}},request:async(method,params)=>rpc(method,params),onEvent:(_type,callback)=>{callbacks.add(callback);return()=>callbacks.delete(callback);},navigate(){navigations++;}};
 const SDK={React,hooks:React,components:{},fetchJSON:api,buildWsUrl:async()=> 'wss://fixture.invalid/api/ws?ticket=synthetic'};
 const ctx={rest:api,register:entry=>{if(entry.render)page=entry.render;}};
 const scope={React,host,ctx,useValue:atom=>atom?.get?.(),ROUTES_AREA:'routes',SIDEBAR_NAV_AREA:'nav',Button:'button',Input:'input',
  ResizeObserver,crypto:webcrypto,WebSocket:Socket,console,setTimeout,clearTimeout,setInterval,clearInterval,URL,URLSearchParams,TextEncoder,btoa,Uint8Array,document:dom.window.document,
  window:{__HERMES_PLUGIN_SDK__:SDK,__HERMES_PLUGINS__:{register:(_name,Page)=>{page=()=>React.createElement(Page);}}}};
 let source=fs.readFileSync(target==='desktop'?'desktop/plugin.js':'dashboard/dist/index.js','utf8');
 if(target==='desktop')source=source.replace(/^import .*;\n/gm,'').replace('export default','const plugin=')+'\nplugin.register(ctx);';
 vm.runInNewContext(source,scope);
 const root=createRoot(document.getElementById('root'));
 await React.act(async()=>{root.render(page());await new Promise(resolve=>setImmediate(resolve));});
 const app={dom,root,element:document.getElementById('root'),calls,bindings,emit,apiCalls,
  get reads(){return reads;},get navigations(){return navigations;},
  field(label){return app.element.querySelector(`[aria-label="${label}"]`);},
  async rerender(){await React.act(async()=>root.render(page()));},
  async setScope(next){profile=next.profile||profile;connection=next.connection||connection;await app.rerender();},
  async resize(width){await React.act(async()=>{for(const observer of [...resizeObservers])observer.callback([{contentRect:{width}}]);});},
  async close(){await React.act(async()=>root.unmount());dom.window.close();delete global.window;delete global.document;}};
 if(autoOpen&&button(app,'Chat'))await click(button(app,'Chat'),app);
 return app;
}
module.exports={mount,click,typeField,button,flush};
