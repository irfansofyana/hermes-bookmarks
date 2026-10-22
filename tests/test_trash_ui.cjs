'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {mount,click,button}=require('./helpers/emitted-client.cjs');
for(const target of ['desktop','dashboard'])test(target+': trash is confirmed, revision-bound, reversible and scoped to current view',async()=>{
 let deleted=false,revision=1,conflict=false;const row=()=>({id:'bookmark-a',title:'Trash fixture',url:'https://example.org',kind:'link',revision,notes:'Keep',tags:[],attachments:[],deleted_at:deleted?1:null});
 const app=await mount(target,{overrideApi:async(route,init)=>{
  const url=new URL(route,'https://fixture.invalid');
  if(url.pathname==='/items'&&!init){const match=(url.searchParams.get('view')==='trash')===deleted;return {ok:true,result:{items:match?[row()]:[],total:match?1:0,offset:0,limit:50}};}
  if(route==='/items/bookmark-a/trash'||route==='/items/bookmark-a/restore'){
   assert.equal(init.body.expected_revision,revision);if(conflict)return {ok:false,error:{code:'conflict',message:'Changed elsewhere'}};
   deleted=route.endsWith('/trash');revision++;return {ok:true,result:row()};
  }
 }});
 try{
  await app.resize(390);
  await click(button(app,'Move to trash Trash fixture'),app);
  assert.equal(app.apiCalls.filter(c=>c.route.endsWith('/trash')).length,0);
  await click(button(app,'Cancel'),app);assert.equal(deleted,false);
  await click(button(app,'Move to trash Trash fixture'),app);
  await click(button(app,'Move to trash'),app);assert.equal(deleted,true);
  assert.match(app.element.textContent,/Moved to trash/);
  await click(button(app,'Undo trash'),app);assert.equal(deleted,false);
  await click(button(app,'Move to trash Trash fixture'),app);conflict=true;
  await click(button(app,'Move to trash'),app);assert.equal(deleted,false);
  assert.match(app.element.textContent,/changed|Changed/);
 }finally{await app.close();}
});
