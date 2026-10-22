'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {mount,click,typeField,button,flush}=require('./helpers/emitted-client.cjs');
for(const target of ['desktop','dashboard']){
 test(target+': imports require preview and explicit Start, default no AI, retained dirty source',async()=>{
  let started=0;const preview={preview_id:'preview',input_digest:'a'.repeat(64),total:2,valid:1,invalid:1,existing:0,duplicate_in_batch:0,rows:[{index:0,status:'valid',warnings:['unsupported_field:extra']},{index:1,status:'invalid',warnings:[],error_code:'invalid_url'}]};
  const job={id:'job',kind:'import',state:'succeeded',total:2,processed:2,remaining:0,imported:1,skipped:0,failed:1,rows:[]};
  const app=await mount(target,{overrideApi:async(route,init)=>{
   if(route==='/imports/preview'){assert.equal(init.body.options.enrich,false);assert.equal(init.body.records[0].notes,'Keep');return {ok:true,result:preview};}
   if(route==='/imports/start'){started++;assert.equal(init.body.preview_id,'preview');assert.equal(init.body.input_digest,'a'.repeat(64));assert.equal(init.body.records,undefined);return {ok:true,result:job};}
  }});
  try{
   await click(button(app,'Import'),app);assert.equal(button(app,'Start import'),undefined);
   await typeField(app,'Import source','[{"url":"https://example.org","notes":"Keep"}]');
   await click(button(app,'Close import'),app);await click(button(app,'Keep editing'),app);
   assert.match(app.field('Import source').value,/Keep/);
   await click(button(app,'Preview import'),app);assert.equal(started,0);
   assert.match(app.element.textContent,/unsupported_field:extra/);assert.match(app.element.textContent,/Invalid: 1/);
   await click(button(app,'Start import'),app);assert.equal(started,1);
   assert.match(app.element.textContent,/Imported: 1/);assert.match(app.element.textContent,/Failed: 1/);
   assert.equal(app.calls.filter(c=>c.method==='prompt.submit').length,0);
  }finally{await app.close();}
 });
 test(target+': lost Start is reconciled read-only with the same request identity',async()=>{
  let writes=0,key;const job={id:'job',state:'cancelled',total:1,processed:0,remaining:1,imported:0,skipped:0,failed:0,rows:[]};
  const app=await mount(target,{overrideApi:async(route,init)=>{
   if(route==='/imports/preview')return {ok:true,result:{preview_id:'p',input_digest:'a'.repeat(64),total:1,valid:1,invalid:0,existing:0,duplicate_in_batch:0,rows:[]}};
   if(route==='/imports/start'){writes++;key=init.body.request_id;throw Error('Lost acknowledgement');}
   if(route.startsWith('/imports/requests/')){assert.equal(route.split('/').at(-1),key);return {ok:true,result:job};}
  }});
  try{await click(button(app,'Import'),app);await typeField(app,'Import source','[{"url":"https://example.org"}]');await click(button(app,'Preview import'),app);await click(button(app,'Start import'),app);
   assert.match(app.element.textContent,/uncertain/i);assert.equal(button(app,'Start import')?.disabled,true);
   await click(button(app,'Check accepted import'),app);assert.equal(writes,1);assert.match(app.element.textContent,/Remaining: 1/);
  }finally{await app.close();}
 });
}
