'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),React=require('react');
const {mount,click,typeField,button}=require('./helpers/emitted-client.cjs');
test('both emitted hosts declare a Bookmarks library and distinct loader contracts',()=>{
 const desktop=fs.readFileSync('desktop/plugin.js','utf8'),dashboard=fs.readFileSync('dashboard/dist/index.js','utf8');
 assert.match(desktop,/@hermes\/plugin-sdk/);assert.doesNotMatch(dashboard,/from ['"]@hermes\/plugin-sdk/);assert.match(desktop,/Bookmarks/);assert.match(dashboard,/Bookmarks/);
});
for(const target of ['desktop','dashboard'])test(target+': saved data, failed-input retention, duplicate guard and owned-image preview',async()=>{
 let writes=0,finish,failSave=true;
 const items=[{id:'existing',title:'Existing bookmark',url:'https://example.org',kind:'link',revision:1,tags:[],attachments:[],enrichment_status:'not_started'}];
 const app=await mount(target,{overrideApi:async(route,init)=>{
  if(route==='/items'&&init?.method==='POST'){
   writes++;if(failSave){await new Promise(resolve=>finish=resolve);return {ok:false,error:{code:'invalid_argument',message:'Synthetic save rejection'}};}
   const saved={...items[0],...init.body,id:'saved',title:'Saved through UI'};items.unshift(saved);return {ok:true,result:saved};
  }
  if(route.startsWith('/items?')){const query=new URL(route,'https://fixture.invalid').searchParams.get('query')||'',filtered=items.filter(item=>item.title.toLowerCase().includes(query.toLowerCase()));return {ok:true,result:{items:filtered,total:filtered.length,offset:0,limit:50}};}
 }});
 try{
  assert.match(app.element.querySelector('.hb-library-content').textContent,/Existing bookmark/);
  await click(button(app,'Add'),app);await typeField(app,'Bookmark URL','https://example.org/new');const form=app.field('Bookmark URL').form;
  await React.act(async()=>{form.dispatchEvent(new app.dom.window.Event('submit',{bubbles:true,cancelable:true}));form.dispatchEvent(new app.dom.window.Event('submit',{bubbles:true,cancelable:true}));});
  assert.equal(writes,1);assert.equal(button(app,'Saving…').disabled,true);
  await React.act(async()=>finish());assert.equal(app.field('Bookmark URL').value,'https://example.org/new');assert.match(app.element.querySelector('[role="alert"]').textContent,/rejection/);
  failSave=false;await click(button(app,'Save'),app);assert.equal(writes,2);assert.equal(Boolean(app.field('Bookmark URL')),false);assert.match(app.element.querySelector('.hb-library-content').textContent,/Saved through UI/);
  await typeField(app,'Search bookmarks','no-such-title');await click(button(app,'Search'),app);assert.match(app.element.querySelector('.hb-library-content').textContent,/No matching items/);assert.doesNotMatch(app.element.querySelector('[aria-label="Saved items"]').textContent,/Existing bookmark/);
  await click(button(app,'Add'),app);const upload=app.field('Attachment images'),bytes=fs.readFileSync('tests/fixtures/tiny.png');
  Object.defineProperty(upload,'files',{value:[{name:'tiny.png',type:'image/png',size:bytes.length,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)}]});
  await React.act(async()=>{upload.dispatchEvent(new app.dom.window.Event('change',{bubbles:true}));await new Promise(resolve=>setImmediate(resolve));});
  assert.match(app.element.querySelector('img[alt="Attached image"]').src,/^data:image\/png;base64,/);assert.equal(app.element.querySelector('[data-asset-id]').dataset.assetId,'b'.repeat(32));
 }finally{finish?.();await app.close();}
});
