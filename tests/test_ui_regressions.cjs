'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const React = require('react');
const {JSDOM} = require('jsdom');

async function mount(target, request) {
  const dom = new JSDOM('<div id="root"></div>', {url:'https://fixture.invalid'});
  global.window=dom.window; global.document=dom.window.document;
  global.HTMLElement=dom.window.HTMLElement; global.IS_REACT_ACT_ENVIRONMENT=true;
  const {createRoot}=require('react-dom/client');
  let renderPage;
  const ctx={rest:request,register:entry=>{if (entry.render) renderPage=entry.render;}};
  const sdk={React,hooks:React,components:{},fetchJSON:request};
  const scope={React,ctx,host:{state:{},navigate(){}},ROUTES_AREA:'routes',SIDEBAR_NAV_AREA:'nav',Button:'button',Input:'input',
    console,setTimeout,clearTimeout,URL,btoa,Uint8Array,
    window:{__HERMES_PLUGIN_SDK__:sdk,__HERMES_PLUGINS__:{register:(_id,Page)=>{renderPage=()=>React.createElement(Page);}}}};
  let source=fs.readFileSync(target==='desktop'?'desktop/plugin.js':'dashboard/dist/index.js','utf8');
  if (target==='desktop') source=source.replace(/^import .*;\n/gm,'').replace('export default','const plugin =')+'\nplugin.register(ctx);';
  vm.runInNewContext(source,scope);
  const root=createRoot(document.getElementById('root'));
  return {dom,root,renderPage,async close(){await React.act(async()=>root.unmount());dom.window.close();delete global.window;delete global.document;}};
}

function legacyPayload() {
  // Real SQLite readback of a row accepted by the old capture validator.
  // Direct insertion recreates that historical database after validation tightens.
  const code=`import json,tempfile
from pathlib import Path
from bookmarks.service import BookmarkService
with tempfile.TemporaryDirectory() as root:
 service=BookmarkService(Path(root))
 service.save_link('https://example.org/healthy','Healthy bookmark')
 with service._storage._transaction(write=True) as c:
  c.execute('INSERT INTO items(id,url,title) VALUES(?,?,?)',('legacy','https://256.256.256.256/','Legacy bookmark'))
 print(json.dumps({'ok':True,'result':service.search('')}))
`;
  return JSON.parse(execFileSync(process.env.BOOKMARKS_TEST_PYTHON || 'python3',['-B','-c',code],{encoding:'utf8'}));
}

for (const target of ['desktop','dashboard']) {
  test(`${target}: finishing a save refreshes the current search instead of its old query`,async()=>{
    const items=[
      {id:'alpha',url:'https://example.org/alpha',title:'Alpha',revision:1,enrichment_status:'pending',summary:'',tags:[],enrichment_job_id:'job-alpha'},
      {id:'beta',url:'https://example.org/beta',title:'Beta',revision:1,enrichment_status:'pending',summary:'',tags:[],enrichment_job_id:'job-beta'}
    ];
    let finishSave; const queries=[];
    async function request(route,init) {
      if (init?.method==='POST') return await new Promise(resolve=>{finishSave=resolve;});
      const query=new URL(route,'https://fixture.invalid').searchParams.get('query') || '';
      queries.push(query);
      const filtered=items.filter(item=>item.title.includes(query));
      return {ok:true,result:{items:filtered,total:filtered.length,offset:0,limit:50}};
    }
    const app=await mount(target,request);
    try {
      await React.act(async()=>app.root.render(app.renderPage()));
      const url=document.querySelector('input[name="url"]');
      url.value='https://example.org/alpha';
      await React.act(async()=>url.form.dispatchEvent(new app.dom.window.Event('submit',{bubbles:true,cancelable:true})));
      const search=document.querySelector('input[name="query"]');
      assert.equal(search.disabled,false,'Saving must not disable unrelated search');
      search.value='Beta';
      await React.act(async()=>search.form.dispatchEvent(new app.dom.window.Event('submit',{bubbles:true,cancelable:true})));
      assert.deepEqual([...document.querySelectorAll('.hb-items a')].map(a=>a.textContent),['Beta']);
      await React.act(async()=>finishSave({ok:true,result:items[0]}));
      assert.equal(search.value,'Beta');
      assert.equal(document.querySelector('.hb-toolbar h2').textContent,'Search results');
      assert.deepEqual([...document.querySelectorAll('.hb-items a')].map(a=>a.textContent),['Beta']);
      assert.equal(queries.at(-1),'Beta');
    } finally {
      await React.act(async()=>finishSave?.({ok:true,result:items[0]}));
      await app.close();
    }
  });

  test(`${target}: an unreadable legacy URL cannot crash persisted library results`,async()=>{
    const payload=legacyPayload();
    assert.equal(payload.result.total,2);
    const app=await mount(target,async()=>payload);
    try {
      await assert.doesNotReject(async()=>{await React.act(async()=>app.root.render(app.renderPage()));});
      const links=[...document.querySelectorAll('.hb-items a')].map(a=>a.textContent);
      assert.deepEqual(links,['Healthy bookmark','Legacy bookmark']);
      assert.match(document.querySelector('.hb-items').textContent,/Hostname unavailable/);
      assert.equal(document.querySelector('input[name="url"]').disabled,false);
    } finally {await app.close();}
  });
}
