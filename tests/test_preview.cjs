'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');

test('declared Dashboard entry registers an honest foundation preview', () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'dashboard/manifest.json'), 'utf8'));
  assert.equal(manifest.name, 'hermes-bookmarks');
  assert.equal(manifest.version, '0.1.0');
  assert.equal(manifest.tab.path, '/bookmarks');
  assert.equal(manifest.api, 'plugin_api.py');
  const source = fs.readFileSync(path.join(root, 'dashboard', manifest.entry), 'utf8');
  const registered = [];
  // Public-shaped SDK double only; not a rendered/installed-host UI claim.
  const sdk = { React: { createElement: (tag, props, ...children) => ({ tag, props, children }) } };
  vm.runInNewContext(source, { window: {
    __HERMES_PLUGIN_SDK__: sdk,
    __HERMES_PLUGINS__: { register: (id, render) => registered.push({ id, render }) },
  } });
  assert.equal(registered.length, 1);
  assert.equal(registered[0].id, manifest.name);
  const tree = registered[0].render();
  assert.match(JSON.stringify(tree), /Bookmarks/);
  assert.match(JSON.stringify(tree), /Foundation preview/);
  assert.match(JSON.stringify(tree), /not yet available/);
  assert.throws(() => vm.runInNewContext(source, { window: {} }), /Dashboard SDK is unavailable/);
});
