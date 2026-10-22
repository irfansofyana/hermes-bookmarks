'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),React=require('react');
const {mount,click,typeField,button,flush}=require('./helpers/emitted-client.cjs');
const preview={preview_id:'preview-a',input_digest:'a'.repeat(64),total:1,valid:1,invalid:0,existing:0,duplicate_in_batch:0,rows:[]};
const job=(state='running')=>({id:'job-a',state,total:2,processed:state==='succeeded'?2:1,remaining:state==='succeeded'?0:1,imported:state==='succeeded'?2:1,skipped:0,failed:0,offset:0,limit:50,rows:[{index:0,outcome:'imported'}]});
function clock(){let id=0;const tasks=new Map();return {setInterval(fn,ms){const key=++id;tasks.set(key,{fn,ms});return key;},clearInterval(key){tasks.delete(key);},get count(){return [...tasks.values()].filter(x=>x.ms===1500).length;},async tick(){await React.act(async()=>{for(const task of [...tasks.values()])if(task.ms===1500)task.fn();await new Promise(resolve=>setImmediate(resolve));});}};}
async function stage(app){await click(button(app,'Import'),app);await typeField(app,'Import source','[{"url":"https://example.org/synthetic-a"}]');await click(button(app,'Preview import'),app);}
for(const target of ['desktop','dashboard']){
 test(target+': late preview cannot repopulate a discarded source draft',async()=>{
  let release;const app=await mount(target,{overrideApi:route=>route==='/imports/preview'?new Promise(resolve=>release=resolve):undefined});
  try{await stage(app);await click(button(app,'Close import'),app);await click(button(app,'Discard import'),app);await click(button(app,'Import'),app);await typeField(app,'Import source','replacement');
   await React.act(async()=>release({ok:true,result:preview}));assert.equal(app.field('Import source').value,'replacement');assert.equal(!!button(app,'Start import'),false);
  }finally{release?.({ok:true,result:preview});await app.close();}
 });
 test(target+': close/reopen during Start and polling keeps one job and one Start',async()=>{
  const timer=clock();let releaseStart,releasePoll,polls=0;
  const app=await mount(target,{intervalClock:timer,overrideApi:route=>{
   if(route==='/imports/preview')return {ok:true,result:preview};
   if(route==='/imports/start')return new Promise(resolve=>releaseStart=resolve);
   if(route.startsWith('/imports/job-a')){polls++;return new Promise(resolve=>releasePoll=resolve);}
  }});
  try{await stage(app);await click(button(app,'Start import'),app);await click(button(app,'Close import'),app);await click(button(app,'Import'),app);assert.equal(button(app,'Start import').disabled,true);
   await React.act(async()=>releaseStart({ok:true,result:job()}));assert.match(app.element.textContent,/Job job-a/);assert.equal(timer.count,1);
   await timer.tick();assert.equal(polls,1);await timer.tick();assert.equal(polls,1,'An in-flight poll is not duplicated');
   await click(button(app,'Close import'),app);await click(button(app,'Import'),app);await React.act(async()=>releasePoll({ok:true,result:job('succeeded')}));
   assert.match(app.element.textContent,/Import succeeded/);assert.equal(timer.count,0);assert.equal(app.apiCalls.filter(x=>x.route==='/imports/start').length,1);
  }finally{releaseStart?.({ok:true,result:job('succeeded')});releasePoll?.({ok:true,result:job('succeeded')});await app.close();assert.equal(timer.count,0);}
 });
 test(target+': unmount during polling prevents late refresh and clears timer',async()=>{
  const timer=clock();let release;
  const app=await mount(target,{intervalClock:timer,overrideApi:route=>{
   if(route==='/imports/preview')return {ok:true,result:preview};if(route==='/imports/start')return {ok:true,result:job()};if(route.startsWith('/imports/job-a'))return new Promise(resolve=>release=resolve);
  }});
  await stage(app);await click(button(app,'Start import'),app);await timer.tick();await app.close();const reads=app.apiCalls.length;
  await React.act(async()=>release({ok:true,result:job('succeeded')}));assert.equal(app.apiCalls.length,reads);assert.equal(timer.count,0);
 });
}
// Desktop exposes live profile/connection switching. Dashboard has one mounted
// authenticated SDK scope; its ownership boundary is unmount, exercised above.
for(const mode of ['profile','connection'])for(const operation of ['file','preview','start','lookup','inspect','cancel','poll']){
 test('Desktop: '+mode+' switch during '+operation+' cannot alter a new library draft or refresh it',async()=>{
  const timer=clock();let release,waiting=false,library='a'.repeat(32),writes=0;
  const app=await mount('desktop',{intervalClock:timer,overrideApi:(route)=>{
   if(route==='/library/identity')return {ok:true,result:{library_id:library}};
   if(route==='/imports/preview')return operation==='preview'?new Promise(resolve=>release=resolve):{ok:true,result:preview};
   if(route==='/imports/start'){writes++;if(operation==='start')return new Promise(resolve=>release=resolve);if(operation==='lookup')throw Error('Lost ack');return {ok:true,result:job()};}
   if(route.startsWith('/imports/requests/'))return new Promise(resolve=>release=resolve);
   if(route.startsWith('/imports/job-a')){
    if(route.endsWith('/cancel')||waiting)return new Promise(resolve=>release=resolve);
    return {ok:true,result:job()};
   }
  }});
  try{
   if(operation==='file'){
    await click(button(app,'Import'),app);const input=app.field('Import file');Object.defineProperty(input,'files',{value:[{name:'a.html',size:20,text:()=>new Promise(resolve=>release=resolve)}]});await React.act(async()=>input.dispatchEvent(new app.dom.window.Event('change',{bubbles:true})));
   }else{
    await stage(app);
    if(operation!=='preview')await click(button(app,'Start import'),app);
    if(operation==='lookup')await click(button(app,'Check accepted import'),app);
    if(operation==='inspect'){waiting=true;await click(button(app,'Refresh import'),app);}
    if(operation==='poll'){waiting=true;await timer.tick();}
    if(operation==='cancel')await click(button(app,'Cancel remaining import'),app);
   }
   assert.equal(typeof release,'function');if(mode==='connection')library='b'.repeat(32);
   await app.setScope(mode==='profile'?{profile:'personal'}:{connection:'backend-b'});assert.equal(timer.count,0);
   await click(button(app,'Import'),app);await typeField(app,'Import source','New scope draft');const reads=app.apiCalls.filter(x=>x.route.startsWith('/items?')).length;
   await React.act(async()=>release(operation==='file'?'old source':{ok:true,result:operation==='preview'?preview:job(operation==='cancel'?'cancelled':'succeeded')}));await flush();
   assert.equal(app.field('Import source').value,'New scope draft');assert.equal(!!app.field('Import progress'),false);assert.equal(!!button(app,'Start import'),false);
   assert.equal(app.apiCalls.filter(x=>x.route.startsWith('/items?')).length,reads,'Old completion must not refresh new scope');assert.equal(timer.count,0);assert.equal(writes,operation==='preview'||operation==='file'?0:1);
  }finally{release?.({ok:true,result:job('succeeded')});await app.close();}
 });
}
