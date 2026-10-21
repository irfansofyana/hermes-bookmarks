/* Public gateway adapters; no provider credentials or replacement agent loop. */
function bookmarkEvents(){
  const listeners=new Map();
  return {
    on(type,callback){const set=listeners.get(type)||new Set();set.add(callback);listeners.set(type,set);return()=>{set.delete(callback);if(!set.size)listeners.delete(type);};},
    emit(event){for(const key of new Set([event.type,'*']))for(const callback of [...(listeners.get(key)||[])]){try{callback(event);}catch(error){console.error('Bookmarks event listener failed',error);}}},
    clear(){listeners.clear();}
  };
}
function bookmarkEvent(value,type){const event=value?.method==='event'?value.params:value;return {...event,type:event?.type||type,session_id:event?.session_id??null,payload:event?.payload||{}};}
function createDesktopChatTransport(host,{profile,connection}){
  const events=bookmarkEvents(),pending=new Set(),removers=[];let disposed=false;
  const matches=()=>host.state.profile?.get()===profile&&(!host.state.connectionId||host.state.connectionId.get()===connection);
  const check=()=>{if(disposed)throw Error('Bookmarks connection is closed.');if(!matches())throw Error('The Hermes profile or connection changed. Reopen Bookmarks.');};
  removers.push(host.onEvent('*',value=>{
    if(disposed||!matches()||(value.profile&&value.profile!==profile)||(value.connectionId&&value.connectionId!==connection))return;
    events.emit(bookmarkEvent(value));
  }));
  for(const atom of [host.state.profile,host.state.connectionId,host.state.gateway]){
    if(!atom?.listen)continue;
    removers.push(atom.listen(()=>{
      if(!disposed&&(!matches()||(host.state.gateway&&host.state.gateway.get()!=='open')))
        events.emit({type:'transport.disconnected',session_id:null,payload:{}});
    }));
  }
  return {
    request(method,params={}){
      return new Promise((resolve,reject)=>{
        const cancel=()=>reject(Error('Bookmarks connection is closed; a request outcome may be unknown.'));pending.add(cancel);
        Promise.resolve().then(()=>{check();return host.request(method,params);}).then(value=>{check();resolve(value);},reject).catch(reject).finally(()=>pending.delete(cancel));
      });
    },
    onEvent:(type,callback)=>events.on(type,callback),setSession(){},
    async reconnect(){check();if(host.state.gateway&&host.state.gateway.get()!=='open')throw Error('Reconnect the Hermes backend before restoring this conversation.');},
    dispose(){if(disposed)return;disposed=true;for(const remove of removers)remove();for(const cancel of pending)cancel();pending.clear();events.clear();}
  };
}
function createDashboardChatTransport(SDK,options={}){
  const Socket=options.WebSocket||globalThis.WebSocket,events=bookmarkEvents(),pending=new Map();
  const connectMs=options.connectTimeoutMs??15000,requestMs=options.requestTimeoutMs??120000;
  const heartbeatMs=options.heartbeatIntervalMs??15000,heartbeatDeadlineMs=options.heartbeatDeadlineMs??45000;
  let socket=null,connecting=null,terminal=null,disposed=false,sequence=0,selected=null,generation=0;
  let rejectConnect=null,connectTimer=null,heartbeatTimer=null,pinging=false,removers=[];
  function terminate(error,announce=true){
    if(terminal)return;terminal=error;clearTimeout(connectTimer);clearInterval(heartbeatTimer);
    rejectConnect?.(error);rejectConnect=null;
    for(const entry of pending.values()){clearTimeout(entry.timer);entry.reject(error);}pending.clear();
    for(const remove of removers)remove();removers=[];
    const old=socket;socket=null;try{old?.close();}catch{/* Already closed. */}
    if(announce)events.emit({type:'transport.disconnected',session_id:null,payload:{message:error.message}});
  }
  function rpc(method,params={},timeout=requestMs){
    if(terminal)return Promise.reject(terminal);
    if(!socket||socket.readyState!==1)return Promise.reject(Error('Bookmarks gateway is not connected.'));
    const id='bookmarks-'+(++sequence),owner=generation;
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{if(owner===generation)terminate(Error('Hermes request timed out. Its outcome may be unknown; reconnect to inspect history.'));},timeout);
      pending.set(id,{resolve,reject,timer});
      try{socket.send(JSON.stringify({jsonrpc:'2.0',id,method,params}));}catch{terminate(Error('Hermes disconnected; the request outcome may be unknown.'));}
    });
  }
  function heartbeat(){
    if(heartbeatTimer||heartbeatMs<=0)return;
    heartbeatTimer=setInterval(()=>{
      if(pinging||terminal)return;pinging=true;
      rpc('gateway.ping',{},heartbeatDeadlineMs).catch(()=>{}).finally(()=>{pinging=false;});
    },heartbeatMs);
  }
  function message(event){
    let frame;try{frame=JSON.parse(event.data);}catch{return;}
    if(!frame||typeof frame!=='object')return;
    if(typeof frame.method==='string'&&frame.method!=='event'&&frame.id!=null){
      if(['approval','clarify'].includes(frame.method)&&selected&&frame.params?.session_id===selected)
        events.emit({type:frame.method,session_id:selected,payload:{...frame.params,id:frame.id}});
      else socket?.send(JSON.stringify({jsonrpc:'2.0',id:frame.id,error:{code:['approval','clarify'].includes(frame.method)?4404:-32601,message:'This Bookmarks panel cannot answer the request.'}}));
      return;
    }
    if(frame.id!=null){
      const entry=pending.get(frame.id);if(!entry)return;pending.delete(frame.id);clearTimeout(entry.timer);
      if(frame.error){const error=Error(frame.error.message||'Hermes rejected the request.');error.code=frame.error.code;entry.reject(error);}else entry.resolve(frame.result);
      return;
    }
    if(frame.method==='event'&&typeof frame.params?.type==='string'){
      if(frame.params.type==='gateway.ready'&&frame.params.payload?.heartbeat)heartbeat();
      events.emit(bookmarkEvent(frame));
    }
  }
  function connect(){
    if(terminal)return Promise.reject(terminal);
    if(connecting)return connecting;
    const current=++generation,owns=()=>!disposed&&!terminal&&current===generation;
    connecting=new Promise((resolve,reject)=>{
      rejectConnect=reject;
      connectTimer=setTimeout(()=>{if(owns())terminate(Error('Bookmarks connection timed out. Reconnect to try again.'));},connectMs);
      Promise.resolve().then(()=>SDK.buildWsUrl('/api/ws')).then(url=>{
        if(!owns())return;
        socket=new Socket(url);
        const listen=(type,callback)=>{const owned=socket,guarded=event=>{if(owns()&&socket===owned)callback(event);};owned.addEventListener(type,guarded);removers.push(()=>owned.removeEventListener(type,guarded));};
        listen('message',message);
        listen('error',()=>terminate(Error('Hermes WebSocket disconnected. Reconnect to inspect history.')));
        listen('close',()=>terminate(Error('Hermes disconnected. A submitted request may still be running; reconnect to inspect history.')));
        listen('open',()=>{
          rpc('client.capabilities',{server_requests:true}).then(()=>{
            if(!owns())return;clearTimeout(connectTimer);rejectConnect=null;resolve();
          }).catch(error=>{if(owns())terminate(error);});
        });
      }).catch(()=>{if(owns())terminate(Error('Could not authenticate the Hermes connection. Reconnect through the Dashboard.'));});
    });
    return connecting;
  }
  return {
    async request(method,params={}){if(disposed)throw Error('Bookmarks connection is closed.');await connect();return rpc(method,params);},
    onEvent:(type,callback)=>events.on(type,callback),
    setSession(session){selected=typeof session==='string'?session:null;},
    async reconnect(){
      if(disposed)throw Error('Bookmarks connection is closed.');
      if(!terminal&&connecting){await connecting;return;}
      terminate(Error('Explicit reconnect; previous request outcomes may be unknown.'),false);
      terminal=null;connecting=null;selected=null;heartbeatTimer=null;pinging=false;await connect();
    },
    dispose(){if(disposed)return;disposed=true;terminate(Error('Bookmarks connection closed.'),false);events.clear();}
  };
}
