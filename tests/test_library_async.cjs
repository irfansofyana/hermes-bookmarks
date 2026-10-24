'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),React=require('react'),fs=require('node:fs');
const {mount,click,typeField,button}=require('./helpers/emitted-client.cjs');
function fileEvent(app,input){const bytes=fs.readFileSync('tests/fixtures/tiny.png');Object.defineProperty(input,'files',{configurable:true,value:[{name:'fixture.png',type:'image/png',size:bytes.length,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)}]});return React.act(async()=>{input.dispatchEvent(new app.dom.window.Event('change',{bubbles:true}));await new Promise(resolve=>setImmediate(resolve));});}
for(const target of ['desktop','dashboard']){
 test(target+': an uncertain not-found capture locks its original payload until explicit retry',async()=>{
  let posts=0,key;
  const app=await mount(target,{overrideApi:(route,init)=>{
   if(route==='/items'&&init?.method==='POST'){posts++;key=init.body.operation_key;if(posts===1)throw Error('Lost ack');return {ok:true,result:{id:'saved',title:'Saved'},receipt:{operation_key:key,item_id:'saved',outcome:'created'}};}
   if(route.startsWith('/captures/'))return {ok:false,error:{code:'not_found',message:'No receipt'}};
  }});
  try{
   await click(button(app,'Add'),app);await typeField(app,'Bookmark URL','https://example.org/original');await typeField(app,'Personal notes','Original payload');await click(button(app,'Save'),app);await click(button(app,'Verify save'),app);
   assert.equal(app.field('Personal notes').disabled,true,'A retry must not silently ignore new edits while posting an older payload');
   assert.equal(button(app,'Retry original save').disabled,false);await click(button(app,'Retry original save'),app);
   const writes=app.apiCalls.filter(row=>row.route==='/items'&&row.init?.method==='POST');assert.equal(writes.length,2);assert.deepEqual(writes[0].init.body,writes[1].init.body);
  }finally{await app.close();}
 });
 test(target+': a lost Edit acknowledgement is reconciled from the saved item, not a capture key',async()=>{
  let accepted=false;
  const item={id:'bookmark-a',url:'https://example.org/article',title:'A synthetic article',kind:'link',revision:7,notes:'Before',tags:[],attachments:[]};
  const app=await mount(target,{overrideApi:(route,init)=>{
   if(route==='/items/bookmark-a/update'){accepted=true;throw Error('Lost edit ack');}
   if(route==='/items/bookmark-a')return {ok:true,result:{...item,revision:accepted?8:7,notes:accepted?'After':'Before'}};
   if(route.startsWith('/captures/'))return {ok:false,error:{code:'not_found',message:'An edit has no capture receipt'}};
  }});
  try{
   await click(button(app,'Open details A synthetic article'),app);await click(button(app,'Edit'),app);await typeField(app,'Personal notes','After');await click(button(app,'Save'),app);await click(button(app,'Verify save'),app);
   assert.equal(app.apiCalls.filter(row=>row.route.startsWith('/captures/')).length,0);
   assert.equal(Boolean(app.field('Personal notes')),false,'Verified edit should close its form');
   assert.equal(app.apiCalls.filter(row=>row.route==='/items/bookmark-a/update').length,1);
  }finally{await app.close();}
 });
 test(target+': a pending upload is dirty and a discarded upload cannot attach to the next draft',async()=>{
  let release;
  const app=await mount(target,{overrideApi:route=>route==='/assets/base64'?new Promise(resolve=>release=resolve):undefined});
  try{
   await click(button(app,'Add'),app);await fileEvent(app,app.field('Attachment images'));
   await click(button(app,'Cancel'),app);assert.ok(button(app,'Keep editing'),'Staged/in-flight files count as unsaved work');await click(button(app,'Discard'),app);
   await click(button(app,'Add'),app);await typeField(app,'Personal notes','New unrelated draft');
   await React.act(async()=>release({ok:true,result:{id:'b'.repeat(32),mime_type:'image/png'}}));
   assert.equal(app.field('Personal notes').value,'New unrelated draft');assert.equal(app.element.querySelectorAll('[data-asset-id]').length,0);
  }finally{release?.({ok:true,result:{id:'b'.repeat(32)}});await app.close();}
 });
 test(target+': failed identity lookup can be retried without reopening the plugin',async()=>{
  let attempts=0;
  const app=await mount(target,{overrideApi:route=>{if(route==='/library/identity'&&++attempts===1)throw Error('Temporarily unavailable');}});
  try{assert.equal(button(app,'Add').disabled,true);await click(button(app,'Retry library'),app);assert.equal(button(app,'Add').disabled,false);assert.equal(attempts,2);}finally{await app.close();}
 });
 test(target+': item and tag pages beyond fifty remain reachable with correct offsets',async()=>{
  const app=await mount(target,{overrideApi:route=>{
   const url=new URL(route,'https://fixture.invalid'),offset=Number(url.searchParams.get('offset')||0);
   if(url.pathname==='/items')return {ok:true,result:{items:[{id:'page-'+offset,title:'Page '+offset,url:'https://example.org/'+offset,revision:1,tags:[],attachments:[]}],total:51,limit:50,offset}};
   if(url.pathname==='/tags')return {ok:true,result:{tags:Array.from({length:offset?1:50},(_,index)=>({name:'Tag'+(offset+index),count:1})),total:51,limit:50,offset}};
  }});
  try{await click(button(app,'Next page'),app);assert.ok(button(app,'Open details Page 50'));assert.equal(button(app,'Next page').disabled,true);await click(button(app,'More tags'),app);assert.ok(button(app,'Tag Tag50'));await click(button(app,'Tag Tag50'),app);const reads=app.apiCalls.filter(row=>row.route.startsWith('/items?'));assert.equal(new URL(reads.at(-1).route,'https://fixture.invalid').searchParams.get('offset'),'0');}finally{await app.close();}
 });
}
test('Desktop: a late save from another connection cannot close or overwrite the new draft',async()=>{
 let release;
 const app=await mount('desktop',{overrideApi:(route,init)=>route==='/items'&&init?.method==='POST'?new Promise(resolve=>release=resolve):undefined});
 try{
  await click(button(app,'Add'),app);await typeField(app,'Bookmark URL','https://example.org/a');await click(button(app,'Save'),app);
  await app.setScope({connection:'backend-b',profile:'personal'});await click(button(app,'Add'),app);await typeField(app,'Personal notes','B draft');
  await React.act(async()=>release({ok:true,result:{id:'accepted-a',title:'A'}}));assert.equal(app.field('Personal notes').value,'B draft');
 }finally{release?.({ok:true,result:{id:'accepted-a'}});await app.close();}
});
