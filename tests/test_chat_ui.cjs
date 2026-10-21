'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const React=require('react'),{JSDOM}=require('jsdom'),{webcrypto}=require('node:crypto');

async function mount(target,options={}){return require('./helpers/emitted-client.cjs').mount(target,options);}
async function click(node,dom){assert.ok(node,'Expected in-plugin control');await React.act(async()=>node.dispatchEvent(new dom.window.MouseEvent('click',{bubbles:true})));}
function byText(text){return [...document.querySelectorAll('button')].find(button=>button.textContent.trim()===text);}
async function type(node,value,dom){await React.act(async()=>{Object.getOwnPropertyDescriptor(dom.window.HTMLTextAreaElement.prototype,'value').set.call(node,value);node.dispatchEvent(new dom.window.Event('input',{bubbles:true}));});}

for(const target of ['desktop','dashboard']){
 test(target+': history switching locks the unresolved composer and preserves the prior thread draft',async()=>{
  let release;
  const saved=[{id:'thread-a',session_id:'stored-a',profile:'work',model:null,title:'Thread A',created_at:0},{id:'thread-b',session_id:'stored-b',profile:'work',model:null,title:'Thread B',created_at:0}];
  const app=await mount(target,{saved,overrideRpc:(method,params)=>method==='session.resume'&&params.session_id==='stored-b'?new Promise(resolve=>release=resolve):undefined});
  try{
   await click(byText('Chat'),app.dom);
   const draft=document.querySelector('textarea[aria-label="Message Hermes"]');await type(draft,'Original A draft',app.dom);
   const select=document.querySelector('select[aria-label="Conversation history"]');
   await React.act(async()=>{select.value='thread-b';select.dispatchEvent(new app.dom.window.Event('change',{bubbles:true}));});
   assert.equal(typeof release,'function');
   assert.equal(draft.disabled,true,'Do not accept typing until the destination conversation owns the composer');
   await React.act(async()=>release({session_id:'runtime-chat',stored_session_id:'stored-b',running:false,messages:[],open_requests:[]}));
   assert.equal(draft.disabled,false);assert.equal(draft.value,'');
   await React.act(async()=>{select.value='thread-a';select.dispatchEvent(new app.dom.window.Event('change',{bubbles:true}));});
   assert.equal(draft.value,'Original A draft');
  }finally{release?.({session_id:'runtime-chat',stored_session_id:'stored-b',running:false,messages:[],open_requests:[]});await app.close();}
 });
 for(const kind of ['approval','clarify'])test(target+': stale '+kind+' card cannot answer its replacement',async()=>{
  const app=await mount(target);try{
   await click(byText('Ask Hermes'),app.dom);
   const draft=document.querySelector('textarea[aria-label="Message Hermes"]');await type(draft,'Help',app.dom);
   await React.act(async()=>draft.form.dispatchEvent(new app.dom.window.Event('submit',{bubbles:true,cancelable:true})));
   const first=kind==='approval'?{id:'request-A',description:'Harmless A?',command:'read A',choices:['once','deny']}:{id:'same-request',questions:[{qid:'q-A',question:'Question A?',choices:['Option A']}]};
   const second=kind==='approval'?{id:'request-B',description:'Different B?',command:'delete B',choices:['once','deny']}:{id:'same-request',questions:[{qid:'q-B',question:'Question B?',choices:['Option B']}]};
   await React.act(async()=>app.emit(kind,first));
   const oldButton=byText(kind==='approval'?'Allow once':'Option A');
   await React.act(async()=>{
    app.emit(kind,second);
    assert.match(document.querySelector('[aria-label="Hermes decision"]').textContent,/A\?/,'The human is still looking at card A');
    oldButton.dispatchEvent(new app.dom.window.MouseEvent('click',{bubbles:true}));
   });
   const method=kind==='approval'?'request.answer':'clarify.lock';
   assert.equal(app.calls.filter(call=>call.method===method).length,0,'A stale card must not authorize or answer B');
   assert.match(document.querySelector('[aria-label="Hermes decision"]').textContent,/B\?/);
   if(kind==='approval'){
    await click(byText('Allow once'),app.dom);
    assert.equal(app.calls.find(call=>call.method==='request.answer').params.id,'request-B');
   }
  }finally{await app.close();}
 });
 test(target+': a restored explicitly selected model accepts follow-up messages without a model reset',async()=>{
  const app=await mount(target,{saved:[{id:'existing-thread',session_id:'stored-chat',profile:'work',model:{provider:'fixture',model:'synthetic'},title:'Saved thread',created_at:0}]});
  try{
   await click(byText('Chat'),app.dom);
   assert.match(document.querySelector('[role="log"]').textContent,/Saved answer/);
   const draft=document.querySelector('textarea[aria-label="Message Hermes"]');
   await type(draft,'A follow-up',app.dom);
   await React.act(async()=>draft.form.dispatchEvent(new app.dom.window.Event('submit',{bubbles:true,cancelable:true})));
   assert.equal(app.calls.filter(c=>c.method==='prompt.submit').length,1);
   assert.equal(app.calls.filter(c=>c.method==='session.create').length,0);
   assert.equal(app.calls.find(c=>c.method==='prompt.submit').params.session_id,'runtime-chat');
  }finally{await app.close();}
 });
 test(target+': Ask Hermes prepares the plugin composer without navigating, submitting or losing the library search draft',async()=>{
  const app=await mount(target);try{
   const capture=document.querySelector('input[name="query"]');await require('./helpers/emitted-client.cjs').typeField(app,'Search bookmarks','https://example.org/unsaved');
   await click(byText('Ask Hermes'),app.dom);
   const draft=document.querySelector('textarea[aria-label="Message Hermes"]');
   assert.ok(draft,'Chat must be inside the open Bookmarks plugin');
   assert.match(document.querySelector('[aria-label="Selected bookmark context"]').textContent,/A synthetic article/);
   assert.equal(app.calls.filter(c=>['session.create','prompt.submit'].includes(c.method)).length,0);
   assert.equal(app.navigations,0);assert.equal(capture.value,'https://example.org/unsaved');
   await type(draft,'Compare this bookmark',app.dom);
   await React.act(async()=>draft.form.dispatchEvent(new app.dom.window.Event('submit',{bubbles:true,cancelable:true})));
   assert.equal(app.calls.filter(c=>c.method==='prompt.submit').length,1);
   assert.match(app.calls.find(c=>c.method==='prompt.submit').params.text,/bookmark-a/);
   assert.equal(app.bindings[0].session_id,'stored-chat');
   assert.equal(document.querySelector('textarea[aria-label="Message Hermes"]').value,'');
   assert.equal(app.navigations,0);assert.equal(capture.value,'https://example.org/unsaved');
   const before=app.reads;
   await React.act(async()=>app.emit('tool.complete',{tool_id:'t1',name:'bookmark_save',summary:'Saved one bookmark',result:{ok:true}}));
   assert.ok(app.reads>before,'Native-tool changes refresh the library');
   assert.equal(capture.value,'https://example.org/unsaved');
   await click(byText('Stop'),app.dom);
   assert.equal(app.calls.filter(c=>c.method==='session.interrupt').length,1);
  }finally{await app.close();}
 });
 test(target+': streamed Markdown is readable without executing HTML, images, or unsafe links',async()=>{
  const app=await mount(target);try{
   await click(byText('Ask Hermes'),app.dom);
   const draft=document.querySelector('textarea[aria-label="Message Hermes"]');assert.ok(draft);
   await type(draft,'Show a table',app.dom);
   await React.act(async()=>draft.form.dispatchEvent(new app.dom.window.Event('submit',{bubbles:true,cancelable:true})));
   await React.act(async()=>app.emit('message.delta',{text:'## Result\n\n| Link | State |\n| --- | --- |\n| Article | Saved |\n\n```js\nconst x = 1;\n```\n\n[unsafe](javascript:alert(1))\n\n<img src=x onerror="alert(1)">\n\n![remote](https://example.org/tracker.png)'}));
   const log=document.querySelector('[role="log"]');
   assert.equal(log.querySelector('h2').textContent,'Result');assert.match(log.querySelector('table').textContent,/Article/);
   assert.match(log.querySelector('pre code').textContent,/const x = 1/);
   assert.equal(log.querySelectorAll('img,script,iframe,[onerror],a[href^="javascript:"]').length,0);
   await React.act(async()=>app.emit('approval',{id:'permission-1',description:'Allow saving?',choices:['once','deny']}));
   assert.match(document.querySelector('[aria-label="Hermes decision"]').textContent,/Allow saving/);
   assert.equal(app.calls.filter(c=>c.method==='request.answer').length,0);
   await click(byText('Deny'),app.dom);
   assert.equal(app.calls.find(c=>c.method==='request.answer').params.result.choice,'deny');
  }finally{await app.close();}
 });
}
