'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),React=require('react'),fs=require('node:fs');
const {mount,click,typeField,button}=require('./helpers/emitted-client.cjs');
for(const target of ['desktop','dashboard']){
 test(target+': duplicate receipt leaves staged input intact and opens the existing item only explicitly',async()=>{
  const app=await mount(target,{overrideApi:(route,init)=>route==='/items'&&init?.method==='POST'?{ok:true,result:{id:'bookmark-a',title:'Existing'},receipt:{outcome:'duplicate',item_id:'bookmark-a'}}:undefined});
  try{await click(button(app,'Add'),app);await typeField(app,'Bookmark URL','https://example.org/article');await typeField(app,'Personal notes','Unapplied duplicate notes');await click(button(app,'Save'),app);assert.equal(app.field('Personal notes').value,'Unapplied duplicate notes');assert.equal(button(app,'Save').disabled,true);assert.equal(app.apiCalls.filter(row=>row.route.endsWith('/update')).length,0);await click(button(app,'Open existing'),app);assert.ok(button(app,'Edit'));assert.equal(app.apiCalls.filter(row=>row.route.endsWith('/update')).length,0);}finally{await app.close();}
 });
 test(target+': stale edit conflict retains fields until a confirmed reload of saved content',async()=>{
  let version=1;
  const app=await mount(target,{overrideApi:(route,init)=>{
   if(route==='/items/bookmark-a/update'){version=2;return {ok:false,error:{code:'conflict',message:'Newer revision',current_revision:2}};}
   if(route==='/items/bookmark-a')return {ok:true,result:{id:'bookmark-a',title:'A synthetic article',url:'https://example.org/article',kind:'link',revision:version,notes:version===1?'Before':'Remote edit',tags:[],attachments:[]}};
  }});
  try{await click(button(app,'Open details A synthetic article'),app);await click(button(app,'Edit'),app);await typeField(app,'Personal notes','Local edit');await click(button(app,'Save'),app);assert.equal(app.field('Personal notes').value,'Local edit');await click(button(app,'Reload saved'),app);assert.equal(app.field('Personal notes').value,'Local edit');await click(button(app,'Confirm reload saved'),app);assert.equal(app.field('Personal notes').value,'Remote edit');assert.equal(app.apiCalls.filter(row=>row.route.endsWith('/update')).length,1);}finally{await app.close();}
 });
 test(target+': stale search completions cannot replace a newer page and tag filters compose with AND',async()=>{
  const pending=new Map();const app=await mount(target,{overrideApi:route=>{if(route.startsWith('/items?')){const query=new URL(route,'https://fixture.invalid').searchParams.get('query');if(['old','new'].includes(query))return new Promise(resolve=>pending.set(query,resolve));}}});
  try{
   await typeField(app,'Search bookmarks','old');await click(button(app,'Search'),app);await typeField(app,'Search bookmarks','new');await click(button(app,'Search'),app);
   const result=title=>({ok:true,result:{items:[{id:title,title,url:'https://example.org/'+title,tags:[],attachments:[],revision:1}],total:1,offset:0,limit:50}});
   await React.act(async()=>pending.get('new')(result('Newest')));await React.act(async()=>pending.get('old')(result('Obsolete')));assert.ok(button(app,'Open details Newest'));assert.equal(Boolean(button(app,'Open details Obsolete')),false);
   await typeField(app,'Search bookmarks','');await click(button(app,'Search'),app);await click(button(app,'Tag Reading'),app);
   assert.equal(new URL(app.apiCalls.filter(row=>row.route.startsWith('/items?')).at(-1).route,'https://fixture.invalid').searchParams.getAll('tag').join(','),'Reading');assert.equal(app.calls.length,0);
  }finally{for(const resolve of pending.values())resolve({ok:true,result:{items:[],total:0}});await app.close();}
 });
 test(target+': failed capture retains uploaded asset identities as well as notes and description',async()=>{
  const app=await mount(target,{overrideApi:(route,init)=>route==='/items'&&init?.method==='POST'?{ok:false,error:{code:'invalid_argument',message:'Rejected fixture'}}:undefined});
  try{await click(button(app,'Add'),app);await typeField(app,'Bookmark URL','https://example.org/new');await typeField(app,'Personal notes','Keep notes');await typeField(app,'Description','Keep description');const input=app.field('Attachment images'),bytes=fs.readFileSync('tests/fixtures/tiny.png');Object.defineProperty(input,'files',{value:[{name:'fixture.png',type:'image/png',size:bytes.length,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)}]});await React.act(async()=>{input.dispatchEvent(new app.dom.window.Event('change',{bubbles:true}));await new Promise(resolve=>setImmediate(resolve));});await click(button(app,'Save'),app);assert.equal(app.field('Personal notes').value,'Keep notes');assert.equal(app.field('Description').value,'Keep description');assert.equal(app.element.querySelector('[data-asset-id]').dataset.assetId,'b'.repeat(32));assert.equal(app.apiCalls.filter(row=>row.route==='/items'&&row.init?.method==='POST').length,1);}finally{await app.close();}
 });
}
