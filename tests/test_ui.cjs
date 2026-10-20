'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('both emitted hosts declare a Bookmarks library and distinct loader contracts', () => {
  const desktop = fs.readFileSync('desktop/plugin.js', 'utf8');
  const dashboard = fs.readFileSync('dashboard/dist/index.js', 'utf8');
  assert.match(desktop, /@hermes\/plugin-sdk/);
  assert.doesNotMatch(dashboard, /from ['"]@hermes\/plugin-sdk/);
  assert.match(desktop, /Bookmarks/);
  assert.match(dashboard, /Bookmarks/);
});

for (const target of ['desktop', 'dashboard']) {
  test(`${target}: real React renders saved data, retains failed input, and blocks duplicate save`, async () => {
    const React = require('react');
    const { JSDOM } = require('jsdom');
    const dom = new JSDOM('<div id="root"></div>', { url: 'https://fixture.invalid' });
    global.window = dom.window;
    global.document = dom.window.document;
    global.HTMLElement = dom.window.HTMLElement;
    global.IS_REACT_ACT_ENVIRONMENT = true;
    const { createRoot } = require('react-dom/client');
    let renderPage;
    let items = [{id: 'fixture', title: 'Existing bookmark', url: 'https://example.org', enrichment_status: 'not_started'}];
    let writes = 0, finish, failSave = true;
    async function request(route, init) {
      if (route.includes('/assets/base64')) return {ok:true,result:{id:'abc123',width:2,height:2,mime_type:'image/png'}};
      if (route.includes('/assets/abc123/preview')) return {ok:true,result:{mime_type:'image/png',content_base64:fs.readFileSync('tests/fixtures/tiny.png').toString('base64')}};
      if (init && init.method === 'POST') {
        writes++;
        if (failSave) {
          await new Promise(resolve => { finish = resolve; });
          throw Error('Fixture save failure');
        }
        items = [{id:'new', title:'Saved through UI', url:'https://example.org/new', enrichment_status:'not_started'}, ...items];
        return {ok:true, result:items[0]};
      }
      const query = new URL(route, 'https://fixture.invalid').searchParams.get('query') || '';
      const filtered = items.filter(i => i.title.toLowerCase().includes(query.toLowerCase()));
      return {ok: true, result: {items:filtered, total:filtered.length, offset:0, limit:50}};
    }
    const sdk = { React, hooks: React, components: {}, fetchJSON: request };
    const ctx = { rest: request, register: entry => { if (entry.render) renderPage = entry.render; } };
    const host = { state: {}, navigate() {} };
    let source = fs.readFileSync(target === 'desktop' ? 'desktop/plugin.js' : 'dashboard/dist/index.js', 'utf8');
    const scope = { React, host, ctx, ROUTES_AREA: 'routes', SIDEBAR_NAV_AREA: 'nav', Button: 'button', Input: 'input', console,
      setTimeout, clearTimeout, URL, btoa, Uint8Array, window: {__HERMES_PLUGIN_SDK__: sdk, __HERMES_PLUGINS__: {register: (_id, page) => { renderPage = () => React.createElement(page); }}} };
    if (target === 'desktop') {
      // Test-only host module linking; the emitted module itself is syntax-checked separately.
      source = source.replace(/^import .*;\n/gm, '').replace('export default', 'const plugin =');
      source += '\nplugin.register(ctx);';
    }
    vm.runInNewContext(source, scope);
    const root = createRoot(document.getElementById('root'));
    try {
      await React.act(async () => { root.render(renderPage()); });
      assert.match(document.body.textContent, /Existing bookmark/);
      const input = document.querySelector('input[name="url"]');
      await React.act(async () => {
        Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, 'value').set.call(input, 'https://example.org/new');
        input.dispatchEvent(new dom.window.Event('input', {bubbles: true}));
        input.dispatchEvent(new dom.window.Event('change', {bubbles: true}));
      });
      const form = document.querySelector('form[data-capture]');
      await React.act(async () => {
        form.dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
        form.dispatchEvent(new dom.window.Event('submit', {bubbles: true, cancelable: true}));
      });
      assert.equal(writes, 1);
      assert.ok(document.querySelector('button[type="submit"]').disabled);
      await React.act(async () => { finish(); });
      assert.equal(input.value, 'https://example.org/new');
      assert.match(document.querySelector('[role="alert"]').textContent, /save|again|failed|failure/i);
      failSave = false;
      await React.act(async () => { form.dispatchEvent(new dom.window.Event('submit', {bubbles:true,cancelable:true})); });
      assert.equal(writes, 2);
      assert.equal(input.value, '');
      assert.match(document.body.textContent, /Saved through UI/);
      const search = document.querySelector('input[name="query"]');
      search.value = 'no-such-title';
      await React.act(async () => {search.form.dispatchEvent(new dom.window.Event('submit', {bubbles:true,cancelable:true}));});
      assert.match(document.body.textContent, /No matches yet/);
      assert.doesNotMatch(document.body.textContent, /Existing bookmark/);
      const upload = document.querySelector('input[type="file"]');
      assert.ok(upload, 'Image capture must be available');
      const bytes=fs.readFileSync('tests/fixtures/tiny.png');
      const file={name:'tiny.png',type:'image/png',size:bytes.length,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};
      Object.defineProperty(upload,'files',{value:[file]});
      await React.act(async()=>upload.dispatchEvent(new dom.window.Event('change',{bubbles:true})));
      assert.match(document.querySelector('img[alt="Uploaded image preview"]').src,/^data:image\/png;base64,/);
      assert.match(document.body.textContent,/abc123/);
    } finally {
      await React.act(async () => root.unmount());
      dom.window.close();
      delete global.window; delete global.document;
    }
  });
}
