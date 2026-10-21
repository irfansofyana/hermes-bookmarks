'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function load(){
 const scope={console,setTimeout,clearTimeout,setInterval,clearInterval,queueMicrotask};
 if(fs.existsSync('ui/chat-transport.js'))vm.runInNewContext(fs.readFileSync('ui/chat-transport.js','utf8')+'\nglobalThis.factories={desktop:createDesktopChatTransport,dashboard:createDashboardChatTransport};',scope);
 assert.ok(scope.factories,'Bookmarks needs scoped public Hermes transports');return scope.factories;
}
function sockets(){
 const instances=[];let reply=true;
 class Socket extends EventTarget{
  constructor(url){super();this.url=url;this.readyState=0;this.frames=[];instances.push(this);queueMicrotask(()=>{if(this.readyState!==0)return;this.readyState=1;this.emit('open');});}
  emit(type,properties={}){const event=new Event(type);Object.assign(event,properties);this.dispatchEvent(event);}
  frame(frame){this.emit('message',{data:JSON.stringify(frame)});}
  send(raw){const frame=JSON.parse(raw);this.frames.push(frame);if(frame.id&&frame.method&&reply)queueMicrotask(()=>this.frame({jsonrpc:'2.0',id:frame.id,result:frame.method==='client.capabilities'?{ok:true}:{method:frame.method}}));}
  close(){if(this.readyState===3)return;this.readyState=3;this.emit('close',{code:1006});}
 }
 return {Socket,instances,set reply(value){reply=value;}};
}

test('Dashboard uses SDK authentication, correlates parallel RPCs and declares interactive capability',async()=>{
 const f=load(),wire=sockets();let tickets=0;
 const transport=f.dashboard({buildWsUrl:async path=>{assert.equal(path,'/api/ws');return 'wss://fixture.invalid/api/ws?ticket=synthetic-'+(++tickets);}},{WebSocket:wire.Socket,heartbeatIntervalMs:0});
 try{
  const result=await Promise.all([transport.request('session.create',{profile:'work'}),transport.request('session.history',{profile:'work',session_id:'s'})]);
  assert.deepEqual(JSON.parse(JSON.stringify(result)),[{method:'session.create'},{method:'session.history'}]);
  assert.equal(tickets,1);assert.equal(wire.instances.length,1);
  assert.equal(wire.instances[0].frames[0].method,'client.capabilities');
  assert.equal(wire.instances[0].frames[0].params.server_requests,true);
 }finally{transport.dispose();}
});

test('Dashboard routes only selected-session decisions and rejects unsupported server requests',async()=>{
 const f=load(),wire=sockets(),transport=f.dashboard({buildWsUrl:async()=> 'wss://fixture.invalid/ws'},{WebSocket:wire.Socket,heartbeatIntervalMs:0});
 const events=[];transport.onEvent('*',e=>events.push(e));
 try{
  await transport.request('gateway.ping');transport.setSession('owned');const socket=wire.instances[0];
  socket.frame({jsonrpc:'2.0',id:'foreign',method:'approval',params:{session_id:'other',description:'Do not show'}});
  socket.frame({jsonrpc:'2.0',id:'own',method:'approval',params:{session_id:'owned',description:'Show decision'}});
  socket.frame({jsonrpc:'2.0',id:'unsupported',method:'vault.fill',params:{session_id:'owned'}});
  assert.equal(events.length,1);assert.equal(events[0].session_id,'owned');assert.equal(events[0].payload.id,'own');
  assert.equal(socket.frames.find(frame=>frame.id==='foreign').error.code,4404);
  assert.equal(socket.frames.find(frame=>frame.id==='unsupported').error.code,-32601);
 }finally{transport.dispose();}
});

test('disconnect rejects outstanding calls, never replays prompts, and reconnect obtains fresh SDK auth',async()=>{
 const f=load(),wire=sockets();let tickets=0;
 const transport=f.dashboard({buildWsUrl:async()=> 'wss://fixture.invalid/ws?ticket='+ ++tickets},{WebSocket:wire.Socket,heartbeatIntervalMs:0});
 try{
  await transport.request('gateway.ping');wire.reply=false;
  const pending=transport.request('prompt.submit',{session_id:'owned',text:'Only once'});await new Promise(r=>setImmediate(r));
  const rejected=assert.rejects(pending,/disconnect|unknown|reconnect/i);wire.instances[0].close();await rejected;
  await assert.rejects(transport.request('prompt.submit',{text:'No automatic retry'}),/disconnect|reconnect/i);
  assert.equal(wire.instances.length,1);
  wire.reply=true;await transport.reconnect();
  assert.equal(tickets,2);
  assert.equal(wire.instances[1].frames.filter(f=>f.method==='prompt.submit').length,0);
 }finally{transport.dispose();}
});

test('request timeout terminates the connection and does not allow replay on the same socket',async()=>{
 const f=load(),wire=sockets(),transport=f.dashboard({buildWsUrl:async()=> 'wss://fixture.invalid/ws'},{WebSocket:wire.Socket,requestTimeoutMs:15,heartbeatIntervalMs:0});
 try{
  await transport.request('gateway.ping');wire.reply=false;
  await assert.rejects(transport.request('prompt.submit',{text:'Uncertain'}),/timed out|uncertain|unknown/i);
  assert.equal(wire.instances[0].readyState,3);
  await assert.rejects(transport.request('session.history'),/timed out|reconnect/i);
 }finally{transport.dispose();}
});

test('Desktop rejects profile/connection drift and disposes only its own subscriptions',async()=>{
 const f=load();let profile='work',connection='backend-A',off=0,close=0,handler;
 const host={state:{profile:{get:()=>profile},connectionId:{get:()=>connection}},request:async(method,params)=>({method,params}),onEvent:(_type,fn)=>{handler=fn;return()=>off++;},close:()=>close++};
 const transport=f.desktop(host,{profile:'work',connection:'backend-A'}),events=[];transport.onEvent('*',e=>events.push(e));
 await transport.request('session.history',{profile:'work',session_id:'owned'});
 handler({type:'message.delta',session_id:'owned',profile:'other',payload:{text:'foreign'}});
 handler({type:'message.delta',session_id:'owned',profile:'work',connectionId:'backend-B',payload:{text:'foreign'}});
 handler({type:'message.delta',session_id:'owned',profile:'work',connectionId:'backend-A',payload:{text:'own'}});
 assert.equal(events.length,1);
 profile='other';await assert.rejects(transport.request('prompt.submit',{profile:'work'}),/profile|connection|changed/i);
 profile='work';connection='backend-B';await assert.rejects(transport.request('session.history',{profile:'work'}),/connection|changed/i);
 transport.dispose();assert.equal(off,1);assert.equal(close,0);
});
