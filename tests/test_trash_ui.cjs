'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {mount,click,typeField,button}=require('./helpers/emitted-client.cjs');
for(const target of ['desktop','dashboard'])test(target+': trashed duplicate keeps unsaved personal notes and does not claim saved',async()=>{
 const app=await mount(target,{overrideApi:async(route,init)=>{
  if(route==='/items'&&init?.method==='POST')return {ok:true,result:{id:'trashed',url:init.body.url,deleted_at:1,notes:'original',revision:2},receipt:{outcome:'trashed_duplicate',item_id:'trashed'}};
  if(route==='/items/trashed')return {ok:true,result:{id:'trashed',title:'Existing trash',url:'https://example.org',deleted_at:1,notes:'original',revision:2,tags:[],attachments:[]}};
 }});
 try{await click(button(app,'Add'),app);await typeField(app,'Bookmark URL','https://example.org');await typeField(app,'Personal notes','Unsaved personal notes');await click(button(app,'Save'),app);
  assert.equal(app.field('Personal notes')?.value,'Unsaved personal notes');assert.match(app.element.textContent,/in Trash/);assert.doesNotMatch(app.element.textContent,/Saved to your library/);assert.ok(button(app,'Open existing'));
  await click(button(app,'Open existing'),app);assert.doesNotMatch(app.element.textContent,/Saved to your library/);
  await click(button(app,'Close details'),app);await click(button(app,'Add'),app);assert.equal(app.field('Personal notes').value,'Unsaved personal notes');
 }finally{await app.close();}
});
for(const target of ['desktop','dashboard'])test(target+': trash cards expose restore but not impossible flag edits',async()=>{
 const row={id:'trashed',title:'Trashed',kind:'link',url:'https://example.org',deleted_at:1,revision:2,notes:'',description:'',tags:[],attachments:[],summary:'',enrichment_status:'not_started'};
 const app=await mount(target,{overrideApi:async(route)=>{if(new URL(route,'https://fixture.invalid').pathname==='/items')return {ok:true,result:{items:[row],total:1,offset:0,limit:50}};}});
 try{assert.ok(button(app,'Restore Trashed'));assert.equal(!!button(app,'Read later Trashed'),false);assert.equal(!!button(app,'Mark favorite Trashed'),false);}finally{await app.close();}
});
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
