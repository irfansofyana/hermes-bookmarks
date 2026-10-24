'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {mount,click,typeField,button}=require('./helpers/emitted-client.cjs');
for(const target of ['desktop','dashboard']){
 test(target+': collection create and rename use shared API payloads and preserve revisions',async()=>{
  const app=await mount(target,{overrideApi:(route,init)=>route.startsWith('/collections')&&init?.method==='POST'?{ok:true,result:{id:'new-collection',name:init.body.name||init.body.changes?.name,revision:2,parent_id:null}}:undefined});
  try{
   await click(button(app,'New collection'),app);await typeField(app,'Collection name','Research');await click(button(app,'Save collection'),app);
   const create=app.apiCalls.find(row=>row.route==='/collections'&&row.init?.method==='POST');assert.deepEqual(create.init.body,{name:'Research',parent_id:null});
   await click(button(app,'Manage collection Engineering'),app);await typeField(app,'Collection name','Engineering notes');await click(button(app,'Save collection'),app);
   const edit=app.apiCalls.find(row=>row.route==='/collections/engineering/update');assert.equal(edit.init.body.expected_revision,1);assert.equal(edit.init.body.changes.name,'Engineering notes');
   assert.equal(app.calls.length,0);
  }finally{await app.close();}
 });
 test(target+': collection deletion requires an explicit non-destructive contents policy',async()=>{
  const app=await mount(target,{overrideApi:(route,init)=>route.endsWith('/delete')&&init?.method==='POST'?{ok:true,result:{deleted_id:'engineering'}}:undefined});
  try{
   await click(button(app,'Manage collection Engineering'),app);await click(button(app,'Delete collection'),app);
   assert.equal(button(app,'Confirm delete').disabled,true);assert.equal(app.apiCalls.filter(row=>row.route.endsWith('/delete')).length,0);
   await typeField(app,'Collection contents policy','move_to_parent');await click(button(app,'Confirm delete'),app);
   const deletion=app.apiCalls.find(row=>row.route==='/collections/engineering/delete');assert.deepEqual(deletion.init.body,{expected_revision:1,contents_policy:'move_to_parent'});
  }finally{await app.close();}
 });
}
