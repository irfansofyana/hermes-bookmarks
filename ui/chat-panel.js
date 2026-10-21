function createBookmarksWorkspace(React,adapter,components,styles){
  const {createElement:h,useState,useEffect,useMemo,useRef}=React,Button=components.Button||'button';
  const libraryViews=new Map(),conversationViews=new Map();
  function ChatPanel({identity,api,scope,selection,onRemove,onChange}){
    const key=JSON.stringify([scope,identity.library_id,identity.profile]);
    if(!conversationViews.has(key))conversationViews.set(key,{draft:'',drafts:{},active:undefined});
    const view=conversationViews.get(key),controller=useRef(null),log=useRef(null),follow=useRef(true),live=useRef(false);
    const [state,setState]=useState({messages:[],busy:false,status:'Connecting',pending:null,error:'',plan:null}),[draft,changeDraft]=useState(view.draft);
    const [threads,setThreads]=useState([]),[total,setTotal]=useState(0),[opening,setOpening]=useState(true),[models,setModels]=useState([]),[model,setModel]=useState(''),[modelError,setModelError]=useState('');
    const [answer,setAnswer]=useState(''),[choices,setChoices]=useState([]),[away,setAway]=useState(false),[contextError,setContextError]=useState('');
    const draftRef=useRef(null);
    function setDraft(value){view.draft=value;changeDraft(value);}
    async function refreshThreads(offset=0){
      const result=await api('/chat/threads?limit=50&offset='+offset);
      if(!result?.ok)throw Error(result?.error?.message||'Could not read conversation bindings.');
      if(live.current){setThreads(previous=>offset?[...previous,...result.result.threads]:result.result.threads);setTotal(result.result.total);}
      return result.result.threads;
    }
    useEffect(()=>{
      live.current=true;
      const transport=adapter.createTransport(identity,scope);
      const chat=new BookmarkChat({transport,api,identity,onState:next=>{if(live.current){if(next.binding)view.active=next.binding.id;setState(next);}},onChange});
      controller.current=chat;setState(chat.state);
      (async()=>{
        try{
          const rows=await refreshThreads();if(!live.current)return;
          const row=view.active===undefined?rows[0]:rows.find(row=>row.id===view.active);
          if(row)await chat.restore({...row,library_id:identity.library_id});
        }catch(error){if(live.current)setState(previous=>({...previous,error:error.message}));}
        finally{if(live.current)setOpening(false);}
      })();
      transport.request('model.options',{profile:identity.profile,explicit_only:true,include_unconfigured:false}).then(payload=>{
        const options=[];
        for(const provider of payload.providers||[]){if(!provider.authenticated||!Array.isArray(provider.models))continue;for(const name of provider.models){try{const value=bookmarkModel({provider:provider.slug,model:name});options.push({value:JSON.stringify(value),label:(provider.name||provider.slug)+' · '+name});}catch{/* Unsupported identity is not a selectable model. */}}}
        if(live.current)setModels(options);
      }).catch(()=>{if(live.current)setModelError('Configured models could not be loaded. Your profile default remains available.');});
      return()=>{live.current=false;chat.dispose();controller.current=null;};
    },[]);
    useEffect(()=>{if(selection.length&&!view.draft)setDraft('Help me explore this saved bookmark.');if(selection.length)draftRef.current?.focus();},[selection]);
    useEffect(()=>{setAnswer('');setChoices([]);},[state.pending?.requestId,state.pending?.questions?.[0]?.qid]);
    useEffect(()=>{if(follow.current&&log.current)log.current.scrollTop=log.current.scrollHeight;},[state.messages,state.plan,state.status]);
    async function send(){
      if(!controller.current||opening||state.busy||state.pending||!view.draft.trim())return;
      const text=view.draft;follow.current=true;setAway(false);setContextError('');
      try{
        const sent=await controller.current.send(text,selection.map(item=>item.id),state.binding?controller.current.model:model?JSON.parse(model):null);
        if(sent&&live.current){if(view.draft===text)setDraft('');await refreshThreads();}
      }catch(error){if(live.current)setContextError(error.message);}
    }
    async function selectThread(id){
      const chat=controller.current;if(!chat||opening)return;
      view.drafts[view.active||'new']=view.draft;
      try{
        if(!id){chat.fresh();view.active=null;setModel('');}
        else{const binding=threads.find(row=>row.id===id);if(!binding)return;setOpening(true);await chat.restore({...binding,library_id:identity.library_id});}
        if(live.current)setDraft(view.drafts[id||'new']||'');
      }catch(error){if(live.current)setContextError(error.message);}
      finally{if(live.current)setOpening(false);}
    }
    const pending=state.pending,question=pending?.questions?.[0],options=question?.choices||question?.options||[],multi=!!question?.multi_select;
    const locked=opening||state.busy||state.uncertain,selectedModel=state.binding?state.binding.model?JSON.stringify(state.binding.model):'':model;
    const modelChoices=models.some(item=>item.value===selectedModel)||!selectedModel?models:[{value:selectedModel,label:state.binding.model.provider+' · '+state.binding.model.model},...models];
    return h('aside',{className:'hb-chat','aria-label':'Bookmarks conversation'},
      h('header',{className:'hb-chat-header'},h('p',{className:'hb-eyebrow'},'HERMES / CONVERSATION'),h('h2',null,'Think with your library.'),h('p',null,identity.profile+' profile · dedicated Hermes session')),
      h('div',{className:'hb-chat-controls'},
        h('label',null,'Conversation history',h('select',{'aria-label':'Conversation history',value:state.binding?.id||'',disabled:locked,onChange:event=>selectThread(event.target.value)},h('option',{value:''},'New conversation'),threads.map(row=>h('option',{key:row.id,value:row.id},row.title)))),
        h(Button,{type:'button',disabled:locked,onClick:()=>selectThread('')},'New conversation'),
        threads.length<total&&h(Button,{type:'button',disabled:opening,onClick:()=>refreshThreads(threads.length).catch(error=>setContextError(error.message))},'Load older conversations'),
        h('label',null,'Chat model',h('select',{'aria-label':'Chat model',value:selectedModel,disabled:!!state.binding||locked,onChange:event=>setModel(event.target.value)},h('option',{value:''},'Hermes profile default'),modelChoices.map(option=>h('option',{key:option.value,value:option.value},option.label)))),
        h('p',{className:'hb-chat-hint'},state.binding?'Start a new conversation to change its model.':'Separate from the background enrichment model.'),modelError&&h('p',{className:'hb-chat-hint'},modelError)),
      h('div',{'aria-label':'Selected bookmark context',className:'hb-chat-context'},selection.length?h(React.Fragment,null,h('span',null,'Selected context · '+selection.length+'/20'),selection.map(item=>h('div',{key:item.id},h('span',null,item.title||item.url||item.id),h(Button,{type:'button','aria-label':'Remove context '+(item.title||item.id),onClick:()=>onRemove(item.id)},'Remove')))):h('p',null,'Ask about your library, or select Ask Hermes on a saved link. Only selected references are attached.')),
      h('div',{ref:log,role:'log','aria-label':'Bookmarks conversation messages','aria-live':'polite','aria-relevant':'additions',className:'hb-chat-log',onScroll:event=>{const el=event.currentTarget;follow.current=el.scrollHeight-el.scrollTop-el.clientHeight<60;setAway(!follow.current);}},
        !state.messages.length&&h('div',{className:'hb-chat-welcome'},h('h3',null,'Make the connection.'),h('p',null,'Compare ideas, find a saved detail, or turn a reading list into a next step. Nothing is sent until you choose Send.')),
        state.messages.map(message=>message.kind?h('details',{key:message.id,className:'hb-chat-activity'},h('summary',null,message.kind==='reasoning'?'Thinking':String(message.name||'Tool').replaceAll('_',' '),message.status?' · '+message.status:''),h('pre',null,message.text||'Activity reported by Hermes.')):h('article',{key:message.id,className:'hb-chat-message is-'+message.role},h('span',{className:'hb-chat-role'},message.role==='user'?'You':'Hermes'),bookmarkMarkdown(React,message.text))),
        state.plan?.todos.length?h('details',{className:'hb-chat-plan',open:true},h('summary',null,'Hermes plan'),h('ol',null,state.plan.todos.map(todo=>h('li',{key:todo.id},h('span',{'data-status':todo.status},todo.status.replaceAll('_',' ')),todo.content)))):null),
      away&&h(Button,{type:'button',onClick:()=>{follow.current=true;setAway(false);if(log.current)log.current.scrollTop=log.current.scrollHeight;}},'Jump to latest'),
      h('div',{className:'hb-chat-status',role:'status'},opening?'Opening conversation…':state.status,state.busy&&h(Button,{type:'button',onClick:()=>controller.current?.stop().catch(()=>{})},'Stop')),
      (state.error||contextError)&&h('div',{className:'hb-chat-error',role:'alert'},h('p',null,state.error||contextError),h(Button,{type:'button',disabled:opening||state.busy,onClick:async()=>{setContextError('');setOpening(true);try{await controller.current?.restore();}catch(error){if(live.current)setContextError(error.message);}finally{if(live.current)setOpening(false);}}},'Reconnect conversation')),
      pending&&h('section',{className:'hb-chat-decision','aria-label':'Hermes decision'},h('h3',null,pending.kind==='approval'?'Your permission is needed':question?.question||question?.prompt||'Your answer is needed'),pending.kind==='approval'?h(React.Fragment,null,h('p',null,pending.question),pending.details&&h('pre',null,pending.details),h('div',null,h(Button,{type:'button',disabled:state.answering||!pending.options.includes('deny'),onClick:()=>controller.current.respond('deny').catch(()=>{})},'Deny'),h(Button,{type:'button',disabled:state.answering||!pending.options.includes('once'),onClick:()=>controller.current.respond('once').catch(()=>{})},'Allow once'))):h('form',{onSubmit:event=>{event.preventDefault();const value=multi?[...choices,...(answer.trim()?[answer.trim()]:[])]:answer.trim();if(value.length)controller.current.respond(value).catch(()=>{});}},options.map((option,i)=>{const value=typeof option==='string'?option:option.value||option.label;return h(Button,{key:i,type:'button',disabled:state.answering,'aria-pressed':multi?choices.includes(value):undefined,onClick:()=>multi?setChoices(current=>current.includes(value)?current.filter(v=>v!==value):[...current,value]):controller.current.respond(value).catch(()=>{})},typeof option==='string'?option:option.label||option.value);}),h('input',{'aria-label':'Clarification response',value:answer,onChange:event=>setAnswer(event.target.value)}),h(Button,{type:'submit',disabled:state.answering||(!answer.trim()&&!choices.length)},'Send response'))),
      h('form',{className:'hb-chat-composer',onSubmit:event=>{event.preventDefault();send();}},h('label',{htmlFor:'hb-chat-draft'},'Message Hermes'),h('textarea',{id:'hb-chat-draft',ref:draftRef,'aria-label':'Message Hermes',placeholder:'Ask about what you saved…',value:draft,maxLength:8000,rows:3,onChange:event=>setDraft(event.target.value),onInput:event=>setDraft(event.currentTarget.value),onKeyDown:event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.nativeEvent.isComposing){event.preventDefault();send();}}}),h('div',null,h('span',null,'Enter to send · Shift + Enter for a new line'),h(Button,{type:'submit',disabled:locked||!!pending||!draft.trim()},'Send'))),
      h('p',{className:'hb-chat-hint hb-chat-disclosure'},'Hermes runs this conversation with your profile’s tools and permissions. Provider charges and host retries may apply. Closing this view does not stop a running turn.'));
  }
  return function Workspace({ctx,scope='dashboard'}={}){
    if(!libraryViews.has(scope))libraryViews.set(scope,{query:'',url:'',scroll:0});
    const Library=useMemo(()=>createLibrary(React,adapter,components,styles,libraryViews.get(scope)),[scope]);
    const [identity,setIdentity]=useState(null),[error,setError]=useState(''),[selection,setSelection]=useState([]),[tab,setTab]=useState('library');
    const refresh=useRef(null);
    const api=useMemo(()=>async(path,body)=>{
      const check=()=>{if(adapter.currentScope&&adapter.currentScope()!==scope)throw Error('The Hermes profile or connection changed. Reopen Bookmarks.');};
      check();const result=await adapter.request(ctx,path,body===undefined?undefined:{method:'POST',body});check();return result;
    },[ctx,scope]);
    useEffect(()=>{let active=true;(async()=>{try{const result=await api('/chat/identity');if(!result?.ok||!result.result?.library_id||!result.result.profile)throw Error('Could not resolve the conversation library and profile.');if(active)setIdentity(result.result);}catch{if(active)setError('Chat is unavailable. Enable the native Bookmarks plugin and configure its shared library. Your library remains available.');}})();return()=>{active=false;};},[api]);
    function ask(item){setSelection(previous=>previous.some(row=>row.id===item.id)?previous:previous.length<20?[...previous,item]:previous);setTab('chat');}
    return h('div',{className:'hb-workspace','data-view':tab},h('style',null,styles),
      h('nav',{className:'hb-view-tabs','aria-label':'Bookmarks views'},['library','chat'].map(value=>h(Button,{key:value,type:'button','aria-pressed':tab===value,onClick:()=>setTab(value)},value==='library'?'Library':'Chat'))),
      h(Library,{ctx,onAsk:ask,onReady:handler=>{refresh.current=handler;}}),
      identity?h(ChatPanel,{key:JSON.stringify([scope,identity]),identity,scope,api,selection,onRemove:id=>setSelection(current=>current.filter(row=>row.id!==id)),onChange:()=>refresh.current?.()}):h('aside',{className:'hb-chat hb-chat-unavailable'},h('h2',null,'Your library conversation'),h('p',null,error||'Connecting to Hermes…')));
  };
}
