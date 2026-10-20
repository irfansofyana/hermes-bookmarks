'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function adapter() {
  const scope = {};
  vm.runInNewContext(fs.readFileSync('ui/native-chat.js', 'utf8') + '\nthis.make = createNativeChat;', scope);
  return scope.make;
}
function fixture() {
  let sid = 'stored-a', owner = {connectionId:'source-a', profile:'personal'}, draft = '';
  const inserts = [], opens = [];
  const host = {state: {focusedStoredSessionId:{get:()=>sid}, focusedSessionOwner:{get:()=>owner}},
    profileRoutes: async () => [{connectionId:'source-a', profile:'local-label', targetProfile:'personal', mode:'remote'}],
    openSession: async (id, options) => {opens.push([id,options]);},
    composer: {getDraft: async () => draft, insertText: async (id,text,options) => {inserts.push([id,text,options]); draft += text; return true;}}};
  return {host, inserts, opens, focus: value => {sid = value;}, owner: value => {owner=value;}, draft: value => {draft=value;}};
}
test('only appends bounded references to exact native target; never submits', async () => {
  const f=fixture(), chat=adapter()(f.host), target=chat.snapshot();
  const result=await chat.prepare({target,itemIds:['bookmark-1'],prompt:'Discuss these',append:true});
  assert.equal(result.ok,true); assert.equal(f.inserts[0][0],'stored-a');
  assert.match(f.inserts[0][1],/bookmark-1/); assert.equal(f.inserts[0][2].mode,'block');
  assert.equal(f.opens[0][1].route.connectionId,'source-a');
});
test('existing draft requires append consent and is never replaced', async () => {
  const f=fixture(); f.draft('unfinished note'); const chat=adapter()(f.host);
  const result=await chat.prepare({target:chat.snapshot(),itemIds:['id'],prompt:'Discuss'});
  assert.equal(result.reason,'draft_not_empty'); assert.equal(f.inserts.length,0);
});
test('changing focus during draft lookup aborts without writing elsewhere', async () => {
  const f=fixture(), chat=adapter()(f.host), target=chat.snapshot();
  f.host.composer.getDraft=async () => {f.focus('stored-b'); return '';};
  const result=await chat.prepare({target,itemIds:['id'],prompt:'Discuss',append:true});
  assert.equal(result.reason,'target_changed'); assert.equal(f.inserts.length,0);
});
test('connection-qualified owner must match, not just profile name', async () => {
  const f=fixture(), chat=adapter()(f.host), target=chat.snapshot();
  f.owner({connectionId:'other-source',profile:'personal'});
  const result=await chat.prepare({target,itemIds:['id'],prompt:'Discuss',append:true});
  assert.equal(result.reason,'target_changed'); assert.equal(f.opens.length,0);
});
test('unsupported, absent target, missing route and unmounted mutation fail visibly', async () => {
  assert.equal((await adapter()(null).prepare({})).reason,'unsupported');
  const f=fixture(), chat=adapter()(f.host), target=chat.snapshot();
  f.host.profileRoutes=async()=>[];
  assert.equal((await chat.prepare({target,itemIds:['id'],prompt:'Discuss',append:true})).reason,'route_unavailable');
  f.host.profileRoutes=async()=>[{connectionId:'source-a',profile:'local-label',targetProfile:'personal'}];
  f.host.composer.getDraft=async()=>'persisted stash';
  f.host.composer.insertText=async()=>false;
  assert.equal((await chat.prepare({target,itemIds:['id'],prompt:'Discuss',append:true})).reason,'composer_unavailable');
});
test('invalid and oversized selections never reach native calls', async()=>{
  const f=fixture(), chat=adapter()(f.host), target=chat.snapshot();
  for (const itemIds of [[],Array(21).fill('id'),['id\nmalicious'],[null]]) {
    assert.equal((await chat.prepare({target,itemIds,prompt:'Discuss',append:true})).reason,'invalid_context');
  }
  assert.equal(f.opens.length,0);
});
