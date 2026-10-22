'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),React=require('react');
const {mount,click,typeField,button,flush}=require('./helpers/emitted-client.cjs');
const base=(id)=>({id,title:'Fixture '+id,url:'https://example.org/'+id,kind:'link',revision:3,notes:'Personal '+id,tags:['Keep'],tag_details:[],attachments:[],favorite:false,read_later:false,deleted_at:null});
async function select(app){await click(button(app,'Select visible items'),app);await click(button(app,'Edit selection'),app);await flush();}
for(const target of ['desktop','dashboard']){
 test(target+': an unavailable selection can be refreshed read-only before Apply',async()=>{
  let available=false,writes=0;const a=base('a'),app=await mount(target,{overrideApi:(route,init)=>{
   if(route.startsWith('/items?'))return {ok:true,result:{items:[a],total:1,offset:0,limit:50}};
   if(route==='/items/a')return available?{ok:true,result:a}:{ok:false,error:{code:'not_found',message:'Temporarily unavailable'}};
   if(init?.method==='POST')writes++;
  }});
  try{await select(app);assert.equal(button(app,'Apply to 1 items').disabled,true);available=true;await click(button(app,'Review current selection'),app);assert.equal(button(app,'Apply to 1 items').disabled,false);assert.equal(writes,0);}finally{await app.close();}
 });
 test(target+': loading selection can be stopped and no unreviewed item is mutated',async()=>{
  let release;const a=base('a');let writes=0;const app=await mount(target,{overrideApi:(route,init)=>{
   if(route.startsWith('/items?'))return {ok:true,result:{items:[a],total:1,offset:0,limit:50}};
   if(route==='/items/a')return new Promise(resolve=>release=resolve);if(init?.method==='POST')writes++;
  }});
  try{await click(button(app,'Select visible items'),app);await click(button(app,'Edit selection'),app);assert.ok(button(app,'Stop remaining changes'));await click(button(app,'Stop remaining changes'),app);await React.act(async()=>release({ok:true,result:a}));assert.equal(writes,0);assert.ok(button(app,'Close bulk actions'));}finally{release?.({ok:true,result:a});await app.close();}
 });
 test(target+': selection collection lookup is paged and move preserves reviewed revision',async()=>{
  const a=base('a'),writes=[];const app=await mount(target,{overrideApi:(route,init)=>{
   if(route.startsWith('/items?'))return {ok:true,result:{items:[a],total:1,offset:0,limit:50}};if(route==='/items/a')return {ok:true,result:a};
   if(route.startsWith('/collections?')){const offset=Number(new URL(route,'https://fixture.invalid').searchParams.get('offset')||0);return {ok:true,result:{collections:Array.from({length:offset?1:50},(_,n)=>({id:'collection-'+(n+offset),name:'Folder '+(n+offset),path:[{name:'Root'},{name:'Folder '+(n+offset)}]})),total:51,offset,limit:50}};}
   if(route.endsWith('/update')){writes.push(init.body);return {ok:true,result:{...a,collection_id:'collection-50',revision:4}};}
  }});
  try{await select(app);await typeField(app,'Bulk action','move');await flush();await click(button(app,'More selection collections'),app);await typeField(app,'Selection collection','collection-50');await click(button(app,'Apply to 1 items'),app);assert.deepEqual(writes,[{expected_revision:3,changes:{collection_id:'collection-50'}}]);}finally{await app.close();}
 });
 test(target+': incomplete item hydration is reported without any write',async()=>{
  const rows=['a','b'].map(base);let writes=0;
  const app=await mount(target,{overrideApi:(route,init)=>{
   if(route.startsWith('/items?'))return {ok:true,result:{items:rows,total:2,offset:0,limit:50}};if(route==='/items/a')return {ok:false,error:{code:'not_found',message:'Removed'}};if(route==='/items/b')return {ok:true,result:rows[1]};
   if(route.endsWith('/update')){writes++;return {ok:true,result:{...rows[1],revision:4}};}
  }});
  try{await select(app);assert.equal(writes,0);assert.match(app.element.textContent,/Item no longer exists/);await click(button(app,'Apply to 2 items'),app);assert.equal(writes,1);assert.match(app.element.textContent,/Failed: 1/);assert.match(app.element.textContent,/Applied: 1/);}finally{await app.close();}
 });
 test(target+': selection caps at 100 and never silently selects an unbounded library',async()=>{
  let offset=0;const rows=Array.from({length:120},(_,n)=>base('item-'+n));const app=await mount(target,{overrideApi:route=>{
   if(route.startsWith('/items?')){offset=Number(new URL(route,'https://fixture.invalid').searchParams.get('offset')||0);return {ok:true,result:{items:rows.slice(offset,offset+50),total:120,offset,limit:50}};}
  }});
  try{await click(button(app,'Select visible items'),app);await click(button(app,'Next page'),app);await click(button(app,'Select visible items'),app);await click(button(app,'Next page'),app);await click(button(app,'Select visible items'),app);assert.match(app.element.textContent,/100 selected/);assert.match(app.element.textContent,/limited to 100/);assert.equal(app.apiCalls.filter(x=>x.init?.method==='POST').length,0);}finally{await app.close();}
 });
 test(target+': bulk preview is read-only and explicit Apply uses reviewed revisions, no double apply',async()=>{
  const a=base('a'),b=base('b');let release;const writes=[];
  const app=await mount(target,{overrideApi:(route,init)=>{
   if(route.startsWith('/items?'))return {ok:true,result:{items:[a,b],total:2,offset:0,limit:50}};
   if(route==='/items/a')return {ok:true,result:a};if(route==='/items/b')return {ok:true,result:b};
   if(route.endsWith('/update')){writes.push(init.body);if(route==='/items/a/update')return new Promise(resolve=>release=resolve);return {ok:true,result:{...b,revision:4,favorite:true}};}
  }});
  try{await select(app);assert.equal(writes.length,0);assert.match(app.element.textContent,/2 items reviewed/);
   const applyButton=button(app,'Apply to 2 items');await React.act(async()=>{for(let i=0;i<2;i++)applyButton.dispatchEvent(new app.dom.window.MouseEvent('click',{bubbles:true}));});assert.equal(writes.length,1);
   await React.act(async()=>release({ok:true,result:{...a,revision:4,favorite:true}}));assert.equal(writes.length,2);assert.deepEqual(writes,[{expected_revision:3,changes:{favorite:true}},{expected_revision:3,changes:{favorite:true}}]);
   assert.match(app.element.textContent,/Applied: 2/);assert.equal(app.calls.filter(x=>x.method==='prompt.submit').length,0);
  }finally{release?.({ok:true,result:{...a,revision:4}});await app.close();}
 });
 test(target+': partial conflict is reported without rebase; unknown acknowledgement stops remaining writes',async()=>{
  const rows=['a','b','c'].map(base);let writes=0;
  const app=await mount(target,{overrideApi:(route,init)=>{
   if(route.startsWith('/items?'))return {ok:true,result:{items:rows,total:3,offset:0,limit:50}};
   if(/^\/items\/[abc]$/.test(route))return {ok:true,result:rows.find(r=>r.id===route.split('/').at(-1))};
   if(route.endsWith('/update')){writes++;if(writes===1)return {ok:false,error:{code:'conflict',message:'Changed elsewhere'}};throw Error('Lost ack');}
  }});
  try{await select(app);await click(button(app,'Apply to 3 items'),app);assert.equal(writes,2);assert.match(app.element.textContent,/Conflicts: 1/);assert.match(app.element.textContent,/Uncertain: 1/);assert.match(app.element.textContent,/Not processed: 1/);
   assert.equal(!!button(app,'Retry bulk action'),false);assert.match(app.element.textContent,/inspect the saved item/i);
  }finally{await app.close();}
 });
 test(target+': quoted Unicode tag is kept whole and notes never included in bulk update',async()=>{
  const a=base('a'),writes=[];
  const app=await mount(target,{overrideApi:(route,init)=>{
   if(route.startsWith('/items?'))return {ok:true,result:{items:[a],total:1,offset:0,limit:50}};if(route==='/items/a')return {ok:true,result:a};
   if(route.endsWith('/update')){writes.push(init.body);return {ok:true,result:{...a,revision:4,tags:['Keep','AI, 中文']}};}
  }});
  try{await select(app);await typeField(app,'Bulk action','add_tags');await typeField(app,'Selection tags','"AI, 中文"');await click(button(app,'Apply to 1 items'),app);assert.deepEqual(writes,[{expected_revision:3,changes:{add_tags:['AI, 中文']}}]);}
  finally{await app.close();}
 });
 test(target+': Trash needs explicit review, skips incompatible records and Restore is separate',async()=>{
  const a=base('a'),b={...base('b'),deleted_at:1};const routes=[];
  const app=await mount(target,{overrideApi:(route,init)=>{
   if(route.startsWith('/items?'))return {ok:true,result:{items:[a,b],total:2,offset:0,limit:50}};
   if(route==='/items/a')return {ok:true,result:a};if(route==='/items/b')return {ok:true,result:b};
   if(route.endsWith('/trash')||route.endsWith('/restore')){routes.push(route);return {ok:true,result:{...a,revision:4,deleted_at:1}};}
  }});
  try{await select(app);await typeField(app,'Bulk action','trash');assert.equal(routes.length,0);assert.match(app.element.textContent,/kept in Trash/i);await click(button(app,'Apply to 2 items'),app);assert.deepEqual(routes,['/items/a/trash']);assert.match(app.element.textContent,/Skipped: 1/);}
  finally{await app.close();}
 });
 test(target+': Stop keeps admitted write but never dispatches the next one',async()=>{
  const rows=['a','b'].map(base);let release,writes=0;
  const app=await mount(target,{overrideApi:(route,init)=>{
   if(route.startsWith('/items?'))return {ok:true,result:{items:rows,total:2,offset:0,limit:50}};
   if(/^\/items\/[ab]$/.test(route))return {ok:true,result:rows.find(r=>r.id===route.split('/').at(-1))};
   if(route.endsWith('/update')){writes++;return new Promise(resolve=>release=resolve);}
  }});
  try{await select(app);await click(button(app,'Apply to 2 items'),app);await click(button(app,'Stop remaining changes'),app);await React.act(async()=>release({ok:true,result:{...rows[0],revision:4}}));assert.equal(writes,1);assert.match(app.element.textContent,/Not processed: 1/);}
  finally{release?.({ok:true,result:{...rows[0],revision:4}});await app.close();}
 });
 test(target+': successful save outside filter offers View item without altering filter',async()=>{
  const app=await mount(target);
  try{await typeField(app,'Search bookmarks','nonmatching');await click(button(app,'Search'),app);await click(button(app,'Add'),app);await typeField(app,'Bookmark URL','https://example.org/new');await click(button(app,'Save'),app);
   assert.ok(button(app,'View item'));await click(button(app,'View item'),app);assert.equal(app.field('Search bookmarks').value,'nonmatching');assert.ok(button(app,'Close details'));}
  finally{await app.close();}
 });
}
test('Desktop: switching backend during a batch stops dispatch and cannot refresh replacement library',async()=>{
 const rows=['a','b'].map(base);let release,writes=0;
 const app=await mount('desktop',{overrideApi:(route,init)=>{
  if(route.startsWith('/items?'))return {ok:true,result:{items:rows,total:2,offset:0,limit:50}};
  if(/^\/items\/[ab]$/.test(route))return {ok:true,result:rows.find(r=>r.id===route.split('/').at(-1))};
  if(route.endsWith('/update')){writes++;return new Promise(resolve=>release=resolve);}
 }});
 try{await select(app);await click(button(app,'Apply to 2 items'),app);await app.setScope({connection:'replacement'});const reads=app.apiCalls.length;
  await React.act(async()=>release({ok:true,result:{...rows[0],revision:4}}));assert.equal(writes,1);assert.equal(app.apiCalls.length,reads);assert.equal(!!app.field('Bulk action'),false);
 }finally{release?.({ok:true,result:{...rows[0],revision:4}});await app.close();}
});
