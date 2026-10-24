'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {webcrypto}=require('node:crypto');

function harness(options={}) {
  const path='ui/chat-session.js';
  const scope={crypto:webcrypto,console,setInterval,clearInterval};
  if(fs.existsSync(path))vm.runInNewContext(fs.readFileSync(path,'utf8')+'\nglobalThis.Controller=BookmarkChat;',scope);
  assert.equal(typeof scope.Controller,'function','Bookmarks needs its own Hermes-backed conversation controller');
  const calls=[],bindings=[],listeners=new Set();
  const identity={library_id:'library-A',profile:'work'};
  let running=true,history=[];
  const transport={
    onEvent(type,fn){assert.equal(type,'*');listeners.add(fn);return()=>listeners.delete(fn);},
    setSession(id){this.selected=id;},dispose(){this.disposed=true;listeners.clear();},async reconnect(){},
    async request(method,params){
      calls.push({method,params:JSON.parse(JSON.stringify(params))});
      assert.equal(params.profile,'work','Every RPC captures its owning profile');
      if(options.rpc){const result=options.rpc(method,params);if(result!==undefined)return await result;}
      if(method==='session.create')return {session_id:'runtime-one',stored_session_id:'stored-one'};
      if(method==='prompt.submit'){running=true;history=[{role:'user',text:params.text}];return {status:'streaming',user_row_id:1};}
      if(method==='session.resume')return {session_id:'runtime-resumed',stored_session_id:'stored-one',messages:history,running,open_requests:[]};
      if(method==='session.activate')return {session_id:params.session_id,running,open_requests:[],todo_state:null};
      if(method==='session.history')return {messages:history};
      if(method==='session.interrupt'){running=false;return {status:'interrupted'};}
      if(method==='request.answer')return {status:'ok'};
      if(method==='clarify.lock')return {status:'ok',remaining:[]};
      assert.fail('Unexpected RPC: '+method);
    }
  };
  async function api(path,body){
    if(options.api){const result=options.api(path,body);if(result!==undefined)return await result;}
    if(path==='/chat/identity')return {ok:true,result:{...identity}};
    if(path==='/chat/threads'&&body){const binding={...body,profile:identity.profile,created_at:0};bindings.push(binding);return {ok:true,result:binding};}
    throw Error('Unexpected API: '+path);
  }
  let changes=0;
  const chat=new scope.Controller({transport,api,identity:{...identity},pollMs:0,onChange:()=>{changes++;}});
  return {chat,transport,calls,bindings,identity,get changes(){return changes;},
    emit(type,payload={},extra={}){for(const fn of listeners)fn({type,session_id:'runtime-one',profile:'work',payload,...extra});},
    finish(messages){running=false;history=messages;},accept(messages){running=true;history=messages;},get backendRunning(){return running;},listeners};
}
const turns=()=>new Promise(resolve=>setImmediate(resolve));

test('explicit Send creates and durably binds its own session, never the focused ordinary chat',async()=>{
 const h=harness();try{
  assert.equal(h.calls.length,0);
  await h.chat.send('Compare my links',['bookmark-a']);
  assert.deepEqual(h.calls.map(c=>c.method),['session.create','prompt.submit']);
  assert.equal(h.calls[0].params.close_on_disconnect,false);
  assert.match(h.calls[0].params.idempotency_key,/bookmarks/);
  assert.equal(h.bindings[0].session_id,'stored-one');
  assert.equal(h.calls[1].params.session_id,'runtime-one');
  assert.match(h.calls[1].params.text,/bookmark-a/);
  assert.ok(h.calls[1].params.text.endsWith('Compare my links'));
  assert.equal(h.chat.state.messages[0].text,'Compare my links');
  assert.equal(h.chat.state.busy,true);
 }finally{h.chat.dispose();}
});

test('double Send cannot create or submit a second turn',async()=>{
 let resolve;const h=harness({rpc:method=>method==='session.create'?new Promise(r=>resolve=r):undefined});
 try{
  const first=h.chat.send('Read this',[]);await turns();
  await assert.rejects(h.chat.send('Duplicate',[]),/wait|working|progress/i);
  resolve({session_id:'runtime-one',stored_session_id:'stored-one'});await first;
  assert.equal(h.calls.filter(c=>c.method==='prompt.submit').length,1);
 }finally{resolve?.({session_id:'runtime-one',stored_session_id:'stored-one'});h.chat.dispose();}
});

test('bookmark selection is bounded before any RPC or binding write',async()=>{
 const h=harness();try{
  for(const ids of [Array.from({length:21},(_,i)=>'id-'+i),['../invalid']])await assert.rejects(h.chat.send('Read',ids),/context|bookmark|selection/i);
  assert.equal(h.calls.length,0);assert.equal(h.bindings.length,0);
 }finally{h.chat.dispose();}
});

test('streaming, tool summaries and monotonic plans reject foreign session/profile events',async()=>{
 const h=harness();try{
  await h.chat.send('Read',['a']);
  h.emit('message.delta',{text:'foreign'},{session_id:'other'});
  h.emit('message.delta',{text:'foreign'},{profile:'other'});
  h.emit('message.delta',{text:'Hello '});h.emit('message.delta',{text:'world'});
  h.emit('tool.start',{tool_id:'t1',name:'bookmark_get',summary:'Reading your selection'});
  h.emit('tool.complete',{tool_id:'t1',name:'bookmark_get',summary:'Read one bookmark',result:{api_key:'must-not-render'}});
  h.emit('todo.updated',{revision:2,todos:[{id:'x',content:'Compare links',status:'completed'}]});
  h.emit('todo.updated',{revision:1,todos:[{id:'x',content:'Stale plan',status:'pending'}]});
  assert.equal(h.chat.state.messages.find(m=>m.role==='assistant').text,'Hello world');
  assert.equal(h.chat.state.messages.find(m=>m.kind==='tool').status,'complete');
  assert.doesNotMatch(JSON.stringify(h.chat.state),/foreign|must-not-render/);
  assert.equal(h.chat.state.plan.todos[0].content,'Compare links');
  assert.equal(h.changes,1);
  h.finish([{role:'user',text:'Read'},{role:'assistant',text:'Confirmed result'}]);
  h.emit('message.complete',{status:'completed'});await turns();await turns();
  assert.equal(h.chat.state.busy,false);
  assert.equal(h.chat.state.messages.at(-1).text,'Confirmed result');
 }finally{h.chat.dispose();}
});

test('lost prompt acknowledgement blocks replay until explicit restore reads host history',async()=>{
 let failed=false;const h=harness({rpc:method=>{if(method==='prompt.submit'&&!failed){failed=true;throw Error('Connection lost');}}});
 try{
  await assert.rejects(h.chat.send('Only once',[]),/Connection lost/);
  await assert.rejects(h.chat.send('Do not replay',[]),/reconnect|restore|uncertain/i);
  const count=h.calls.filter(c=>c.method==='prompt.submit').length;
  h.finish([{role:'user',text:'Only once'},{role:'assistant',text:'Already delivered'}]);
  await h.chat.restore(h.chat.binding);
  assert.equal(h.chat.state.messages.at(-1).text,'Already delivered');
  assert.equal(h.calls.filter(c=>c.method==='prompt.submit').length,count);
  await h.chat.send('Follow up',[]);
  assert.equal(h.calls.filter(c=>c.method==='session.create').length,1);
  assert.equal(h.calls.at(-1).params.session_id,'runtime-resumed');
 }finally{h.chat.dispose();}
});

test('Stop during session creation invalidates the pending continuation without submitting',async()=>{
 let resolve;const h=harness({rpc:method=>method==='session.create'?new Promise(r=>resolve=r):undefined});
 try{
  const sending=h.chat.send('Never submit',[]);await turns();await h.chat.stop();
  resolve({session_id:'runtime-one',stored_session_id:'stored-one'});await sending;
  assert.equal(h.calls.filter(c=>c.method==='prompt.submit').length,0);
  assert.equal(h.bindings.length,0);
  assert.equal(h.chat.state.busy,false);
 }finally{resolve?.({session_id:'runtime-one',stored_session_id:'stored-one'});h.chat.dispose();}
});

test('scope change after creation prevents binding and sending to another profile',async()=>{
 const h=harness({rpc:method=>{if(method==='session.create'){h.identity.profile='other';return {session_id:'runtime-one',stored_session_id:'stored-one'};}}});
 try{
  await assert.rejects(h.chat.send('Keep scoped',[]),/profile|connection|library|scope/i);
  assert.equal(h.bindings.length,0);assert.equal(h.calls.filter(c=>c.method==='prompt.submit').length,0);
 }finally{h.chat.dispose();}
});

test('restoring a foreign library/profile binding never touches Hermes',async()=>{
 const h=harness();try{
  for(const binding of [{id:'x',session_id:'foreign',profile:'other',library_id:'library-A'},{id:'x',session_id:'foreign',profile:'work',library_id:'other-library'}])
   await assert.rejects(h.chat.restore(binding),/profile|connection|library|scope/i);
  assert.equal(h.calls.length,0);
 }finally{h.chat.dispose();}
});

test('only explicit human choices answer the selected session approval/clarification',async()=>{
 const h=harness();try{
  await h.chat.send('Help',[]);
  h.emit('approval',{id:'foreign-request',choices:['once','deny']},{session_id:'other'});
  assert.equal(h.chat.state.pending,null);
  h.emit('approval',{id:'approval-1',description:'Run command?',command:'echo synthetic',choices:['once','always','deny']});
  assert.equal(h.calls.filter(c=>c.method==='request.answer').length,0);
  await assert.rejects(h.chat.respond('always',h.chat.state.pending),/choice|permission/i);
  await h.chat.respond('deny',h.chat.state.pending);
  assert.deepEqual(h.calls.at(-1).params,{profile:'work',id:'approval-1',result:{choice:'deny'}});
  h.emit('clarify',{id:'question-1',questions:[{qid:'q1',question:'Which link?',choices:['A','B']}]});
  await h.chat.respond('A',h.chat.state.pending,'q1');
  assert.deepEqual(h.calls.at(-1).params,{profile:'work',request_id:'question-1',question_id:'q1',answer:'A'});
 }finally{h.chat.dispose();}
});

test('retired decision replies cannot leave or clear a newer conversation decision latch',async()=>{
 const replies={};let first,second;
 const h=harness({rpc:(method,params)=>method==='request.answer'?new Promise(resolve=>replies[params.id]=resolve):undefined});
 try{
  await h.chat.send('Turn A',[]);h.emit('approval',{id:'approval-A',choices:['once','deny']});
  first=h.chat.respond('once',h.chat.state.pending);await turns();
  await h.chat.stop();
  assert.equal(h.chat.state.answering,false,'Stopping retires the previous decision latch');
  await h.chat.send('Turn B',[]);h.emit('approval',{id:'approval-B',choices:['once','deny']});
  second=h.chat.respond('deny',h.chat.state.pending);await turns();
  assert.equal(typeof replies['approval-B'],'function');
  replies['approval-A']({status:'ok'});await first;
  assert.equal(h.chat.state.answering,true,'A late A reply cannot clear B’s pending decision');
  assert.equal(h.chat.state.pending.requestId,'approval-B');
  replies['approval-B']({status:'ok'});await second;assert.equal(h.chat.state.answering,false);
 }finally{for(const reply of Object.values(replies))reply({status:'ok'});h.chat.dispose();await Promise.all([first,second]);}
});

for(const lostAck of [false,true])test('old reconciliation cannot '+(lostAck?'clear a later uncertain-delivery fence':'erase a later live turn'),async()=>{
 let hold=false,releaseHistory;
 const h=harness({rpc:(method,params)=>{
  if(method==='session.history'&&hold)return new Promise(resolve=>releaseHistory=resolve);
  if(method==='prompt.submit'&&params.text.endsWith('Turn B')&&lostAck){h.accept([{role:'user',text:'Turn B'}]);throw Error('Lost B acknowledgement');}
 }});
 const oldHistory=[{role:'user',text:'Turn A'},{role:'assistant',text:'Answer A'}];
 try{
  await h.chat.send('Turn A',[]);h.finish(oldHistory);await h.chat.reconcile();
  assert.equal(h.chat.state.busy,false);
  hold=true;h.emit('error',{message:'Late terminal event for A'});await turns();
  assert.equal(typeof releaseHistory,'function');
  if(lostAck)await assert.rejects(h.chat.send('Turn B',[]),/Lost B/);else await h.chat.send('Turn B',[]);
  h.emit('message.delta',{text:'Live B response'});
  releaseHistory({messages:oldHistory});await turns();
  assert.equal(h.backendRunning,true);
  assert.ok(h.chat.state.messages.some(message=>message.text==='Live B response'),'Old A history cannot erase B');
  assert.equal(h.chat.state.uncertain,lostAck,'Only reconciliation owned by B can clear B uncertainty');
  if(!lostAck)assert.equal(h.chat.state.busy,true,'B remains running and retains Stop');
  await assert.rejects(h.chat.send('Turn B',[]),lostAck?/restore|reconnect/i:/wait|response|stop/i);
  assert.equal(h.calls.filter(call=>call.method==='prompt.submit').length,2);
 }finally{releaseHistory?.({messages:oldHistory});h.chat.dispose();}
});

for(const snapshotHasPlan of [false,true])test('restoring another conversation '+(snapshotHasPlan?'accepts its lower plan revision':'clears the prior plan before awaiting history'),async()=>{
 let release,restoring;
 const h=harness({rpc:method=>method==='session.resume'?new Promise(resolve=>release=resolve):undefined});
 const nextPlan={revision:1,todos:[{id:'b',content:'Plan for B',status:'pending'}]};
 try{
  await h.chat.send('Turn A',[]);
  h.emit('todo.updated',{revision:50,todos:[{id:'a',content:'Plan for A',status:'completed'}]});
  h.finish([{role:'assistant',text:'Answer A'}]);await h.chat.reconcile();
  restoring=h.chat.restore({id:'thread-b',session_id:'stored-b',profile:'work',library_id:'library-A',model:null});
  await turns();
  assert.equal(h.chat.state.plan,null,'Do not display a different conversation plan while restoring');
  h.emit('todo.updated',{revision:99,todos:[{id:'a',content:'Late A plan',status:'completed'}]});
  assert.equal(h.chat.state.plan,null,'Detach the previous runtime before the first restore await');
  release({session_id:'runtime-b',stored_session_id:'stored-b',running:false,messages:[],open_requests:[],todo_state:snapshotHasPlan?nextPlan:null});
  await restoring;
  if(!snapshotHasPlan)assert.equal(h.chat.state.plan,null);
  h.emit('todo.updated',nextPlan,{session_id:'runtime-b'});
  assert.equal(h.chat.state.plan.revision,1);
  assert.equal(h.chat.state.plan.todos[0].content,'Plan for B');
 }finally{release?.({session_id:'runtime-b',stored_session_id:'stored-b',running:false,messages:[],open_requests:[]});h.chat.dispose();await restoring?.catch(()=>{});}
});

test('disposing drops subscriptions and late creation, but never shuts down Desktop host',async()=>{
 let resolve;const h=harness({rpc:method=>method==='session.create'?new Promise(r=>resolve=r):undefined});
 const sending=h.chat.send('Never after dispose',[]);await turns();h.chat.dispose();
 resolve({session_id:'runtime-one',stored_session_id:'stored-one'});await sending;
 assert.equal(h.calls.filter(c=>c.method==='prompt.submit').length,0);
 assert.equal(h.listeners.size,0);
 assert.equal(h.transport.disposed,true);
});
