'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {mount,click,typeField,button,flush}=require('./helpers/emitted-client.cjs');
for(const target of ['desktop','dashboard']){
 test(target+': library-first opening does not initialize chat',async()=>{
  const app=await mount(target);try{
   assert.equal(Boolean(app.element.querySelector('[aria-label="Bookmarks conversation"]')),false);
   assert.equal(app.calls.length,0);
   assert.equal(app.apiCalls.filter(c=>c.route.startsWith('/chat/')).length,0);
   assert.ok(button(app,'Chat'));
  }finally{await app.close();}
 });
 test(target+': collapsing a running chat retains stream, draft, context and exact Stop',async()=>{
  const app=await mount(target);try{
   await click(button(app,'Chat'),app);
   await typeField(app,'Message Hermes','Question');await click(button(app,'Send'),app);
   await typeField(app,'Message Hermes','Unsent follow-up');
   await click(button(app,'Close chat'),app);
   await require('react').act(async()=>app.emit('message.delta',{text:'Working while hidden'}));
   assert.match(button(app,'Chat').textContent,/responding/i);
   assert.equal(app.element.querySelector('.hb-chat-shell').hidden,true);
   await click(button(app,'Chat'),app);
   assert.equal(app.field('Message Hermes').value,'Unsent follow-up');
   assert.match(app.element.querySelector('[role="log"]').textContent,/Working while hidden/);
   assert.equal(app.calls.filter(c=>c.method==='session.create').length,1);
   assert.equal(app.calls.filter(c=>c.method==='prompt.submit').length,1);
   await click(button(app,'Close chat'),app);
   await click(button(app,'Stop conversation'),app);
   assert.equal(app.calls.filter(c=>c.method==='session.interrupt').length,1);
   assert.equal(app.calls.find(c=>c.method==='session.interrupt').params.session_id,'runtime-chat');
  }finally{await app.close();}
 });
 test(target+': hidden decisions never auto-open or authorize; explicit reopen preserves request ownership',async()=>{
  const app=await mount(target);try{
   await click(button(app,'Chat'),app);await typeField(app,'Message Hermes','Question');await click(button(app,'Send'),app);
   await click(button(app,'Close chat'),app);
   await require('react').act(async()=>app.emit('approval',{id:'permission-a',description:'Read?',choices:['once','deny']}));
   assert.equal(app.element.querySelector('.hb-chat-shell').hidden,true);
   assert.match(button(app,'Chat').textContent,/permission/i);
   assert.equal(app.calls.filter(c=>c.method==='request.answer').length,0);
   await click(button(app,'Chat'),app);await click(button(app,'Deny'),app);
   assert.equal(app.calls.find(c=>c.method==='request.answer').params.id,'permission-a');
  }finally{await app.close();}
 });
}
