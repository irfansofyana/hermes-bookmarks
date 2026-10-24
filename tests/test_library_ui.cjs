'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),React=require('react');
const {mount,click,typeField,button,flush}=require('./helpers/emitted-client.cjs');
for(const target of ['desktop','dashboard']){
 test(target+': Add opens a real metadata form, dirty Cancel preserves it until Discard',async()=>{
  const app=await mount(target);try{
   await click(button(app,'Add'),app);
   assert.ok(app.element.ownerDocument.querySelector('[role="dialog"],dialog'));
   await typeField(app,'Bookmark URL','https://example.org/new');await typeField(app,'Personal notes','Keep my draft');
   await click(button(app,'Cancel'),app);assert.ok(button(app,'Keep editing'));
   await click(button(app,'Keep editing'),app);assert.equal(app.field('Personal notes').value,'Keep my draft');
   await click(button(app,'Cancel'),app);await click(button(app,'Discard'),app);
   assert.equal(Boolean(app.field('Personal notes')),false);
  }finally{await app.close();}
 });
 test(target+': capture saves notes and tags without submitting a chat prompt',async()=>{
  const app=await mount(target);try{
   await click(button(app,'Add'),app);await typeField(app,'Bookmark URL','https://example.org/new');
   await typeField(app,'Title','Saved with context');await typeField(app,'Personal notes','# Personal\nA useful note');await typeField(app,'Tags','AI, Reading');
   await click(button(app,'Save'),app);
   const save=app.apiCalls.find(row=>row.route==='/items'&&row.init?.method==='POST');
   assert.equal(save.init.body.notes,'# Personal\nA useful note');assert.deepEqual(save.init.body.tags,['AI','Reading']);
   assert.ok(save.init.body.operation_key);assert.equal(app.calls.filter(c=>c.method==='prompt.submit').length,0);
  }finally{await app.close();}
 });
 test(target+': validation rejection retains every edited field and allows explicit retry',async()=>{
  const app=await mount(target,{overrideApi:(route,init)=>route==='/items'&&init?.method==='POST'?{ok:false,error:{code:'invalid_argument',message:'Synthetic rejection'}}:undefined});try{
   await click(button(app,'Add'),app);await typeField(app,'Bookmark URL','https://example.org/rejected');
   await typeField(app,'Title','My title');await typeField(app,'Personal notes','My notes');await click(button(app,'Save'),app);
   assert.equal(app.field('Title').value,'My title');assert.equal(app.field('Personal notes').value,'My notes');
   assert.match(app.element.textContent,/Synthetic rejection/);assert.equal(button(app,'Save').disabled,false);
  }finally{await app.close();}
 });
 test(target+': uncertain capture reconciles the original key without blindly posting again',async()=>{
  let key;
  const app=await mount(target,{overrideApi:(route,init)=>{
   if(route==='/items'&&init?.method==='POST'){key=init.body.operation_key;throw Error('Lost acknowledgement');}
   if(route.startsWith('/captures/'))return {ok:true,result:{item:{id:'accepted',title:'Accepted',url:'https://example.org/accepted',revision:1,tags:[],attachments:[]},receipt:{operation_key:key,item_id:'accepted',outcome:'created'}}};
  }});try{
   await click(button(app,'Add'),app);await typeField(app,'Bookmark URL','https://example.org/accepted');await click(button(app,'Save'),app);
   assert.ok(button(app,'Verify save'));await click(button(app,'Verify save'),app);
   assert.equal(app.apiCalls.filter(row=>row.route==='/items'&&row.init?.method==='POST').length,1);
   assert.equal(app.apiCalls.filter(row=>row.route==='/captures/'+key).length,1);
  }finally{await app.close();}
 });
 test(target+': detail reads saved content safely and Edit uses its expected revision',async()=>{
  const saved={id:'bookmark-a',title:'A synthetic article',url:'https://example.org/article',kind:'link',revision:7,notes:'# Saved note\n<img src=x onerror=alert(1)>',summary:'Saved summary',tags:['AI'],tag_details:[{name:'AI',source:'generated'}],attachments:[]};
  const app=await mount(target,{overrideApi:route=>route==='/items/bookmark-a'?{ok:true,result:saved}:undefined});try{
   await click(button(app,'Open details A synthetic article'),app);
   assert.match(app.element.textContent,/Saved summary/);assert.equal(app.element.querySelectorAll('[onerror],script').length,0);
   await click(button(app,'Edit'),app);await typeField(app,'Personal notes','Updated note');await click(button(app,'Save'),app);
   const update=app.apiCalls.find(row=>row.route==='/items/bookmark-a/update');
   assert.equal(update.init.body.expected_revision,7);assert.equal(update.init.body.changes.notes,'Updated note');
   assert.equal(update.init.body.changes.add_tags?.length||0,0,'Unchanged generated tags stay generated');
   assert.equal(app.calls.length,0,'Reading/editing does not initialize chat');
  }finally{await app.close();}
 });
 test(target+': navigation exposes persistent views, tag filters and view mode without chat remount',async()=>{
  const app=await mount(target);try{
   assert.ok(app.element.querySelector('[aria-label="Library navigation"]'));
   await click(button(app,'Favorites'),app);
   await click(button(app,'Tag Reading'),app);
   const reads=app.apiCalls.filter(row=>row.route.startsWith('/items?'));const query=new URL('https://fixture.invalid'+reads.at(-1).route).searchParams;
   assert.equal(query.get('view'),'favorites');assert.deepEqual(query.getAll('tag'),['Reading']);
   await click(button(app,'List view'),app);assert.equal(app.element.querySelector('[aria-label="Saved items"]').getAttribute('data-mode'),'list');
   assert.equal(app.calls.length,0);
  }finally{await app.close();}
 });
 test(target+': an image capture has a real primary owned asset and no invented URL',async()=>{
  const app=await mount(target);try{
   await click(button(app,'Add'),app);const oldURL=app.field('Bookmark URL');await typeField(app,'Item type','image');
   const input=app.field('Primary image'),bytes=require('node:fs').readFileSync('tests/fixtures/tiny.png');
   assert.equal(input===oldURL,false,'File input must not reuse a controlled URL input');
   Object.defineProperty(input,'files',{value:[{name:'fixture.png',type:'image/png',size:bytes.length,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)}],configurable:true});
   await React.act(async()=>{input.dispatchEvent(new app.dom.window.Event('change',{bubbles:true}));await new Promise(r=>setImmediate(r));});
   await click(button(app,'Save'),app);
   const save=app.apiCalls.find(row=>row.route==='/items'&&row.init?.method==='POST');
   assert.equal(save.init.body.kind,'image');assert.equal(save.init.body.primary_asset_id,'b'.repeat(32));assert.equal(save.init.body.url,undefined);
  }finally{await app.close();}
 });
 test(target+': item selection checkboxes do not inherit the old full-width capture input styling',async()=>{
  const app=await mount(target);try{const checkbox=app.element.querySelector('input[type="checkbox"][aria-label^="Select "]');assert.ok(checkbox);assert.notEqual(app.dom.window.getComputedStyle(checkbox).width,'100%');}finally{await app.close();}
 });
}
