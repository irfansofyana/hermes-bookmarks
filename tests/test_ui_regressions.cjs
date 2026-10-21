'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),{execFileSync}=require('node:child_process'),React=require('react');
const {mount,click,typeField,button}=require('./helpers/emitted-client.cjs');
function legacyPayload(){
 const code=`import json,tempfile\nfrom pathlib import Path\nfrom bookmarks.service import BookmarkService\nwith tempfile.TemporaryDirectory() as root:\n service=BookmarkService(Path(root))\n service.save_link('https://example.org/healthy','Healthy bookmark')\n with service._storage._transaction(write=True) as c:\n  c.execute('INSERT INTO items(id,url,title) VALUES(?,?,?)',('legacy','https://256.256.256.256/','Legacy bookmark'))\n print(json.dumps({'ok':True,'result':service.search('')}))\n`;
 return JSON.parse(execFileSync(process.env.BOOKMARKS_TEST_PYTHON||'python3',['-B','-c',code],{encoding:'utf8'}));
}
for(const target of ['desktop','dashboard']){
 test(target+': a late Save result cannot revert a newer query intent',async()=>{
  const items=[{id:'alpha',url:'https://example.org/alpha',title:'Alpha',revision:1,tags:[],attachments:[],kind:'link'},{id:'beta',url:'https://example.org/beta',title:'Beta',revision:1,tags:[],attachments:[],kind:'link'}];
  let finish;const queries=[];
  const app=await mount(target,{overrideApi:(route,init)=>{
   if(route==='/items'&&init?.method==='POST')return new Promise(resolve=>finish=resolve);
   if(route.startsWith('/items?')){const query=new URL(route,'https://fixture.invalid').searchParams.get('query')||'';queries.push(query);const filtered=items.filter(item=>item.title.includes(query));return {ok:true,result:{items:filtered,total:filtered.length,offset:0,limit:50}};}
  }});
  try{
   await click(button(app,'Add'),app);await typeField(app,'Bookmark URL','https://example.org/alpha');await click(button(app,'Save'),app);
   // Unit-level newer-intent injection, not proof that an inert modal background
   // can be clicked. Actual dialog focus containment is a browser acceptance gate.
   await typeField(app,'Search bookmarks','Beta');await click(button(app,'Search'),app);
   assert.deepEqual([...app.element.querySelectorAll('.hb-title-button')].map(node=>node.textContent),['Beta']);
   await React.act(async()=>finish({ok:true,result:items[0]}));
   assert.equal(app.field('Search bookmarks').value,'Beta');assert.equal(queries.at(-1),'Beta');
   assert.deepEqual([...app.element.querySelectorAll('.hb-title-button')].map(node=>node.textContent),['Beta']);
  }finally{finish?.({ok:true,result:items[0]});await app.close();}
 });
 test(target+': unreadable legacy URLs cannot crash real persisted library results',async()=>{
  const payload=legacyPayload();assert.equal(payload.result.total,2);
  const app=await mount(target,{overrideApi:route=>route.startsWith('/items?')?payload:undefined});
  try{
   assert.deepEqual([...app.element.querySelectorAll('.hb-title-button')].map(node=>node.textContent),['Healthy bookmark','Legacy bookmark']);
   assert.match(app.element.querySelector('[aria-label="Saved items"]').textContent,/Source unavailable/);
   assert.equal(button(app,'Add').disabled,false);
  }finally{await app.close();}
 });
}
