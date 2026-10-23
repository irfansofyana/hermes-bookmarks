'use strict';
// Emitted-host protocol tests. No real SDK/browser/download acceptance claim.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),Module=require('node:module');
const React=require('react'),{createHash}=require('node:crypto');
const root=path.resolve(__dirname,'..');
function fixture(){
 // Exercise the bytes that actually ship. Rebuilding belongs to the separate
 // deterministic build gate, never to a test fixture that can mask stale output.
 const filename=path.join(__dirname,'helpers/emitted-client.cjs'),m=new Module(filename,module);m.filename=filename;m.paths=module.paths;
 m.require=Module.createRequire(filename);
 let source=fs.readFileSync(filename,'utf8');
 source=source.replace("const assert=require", "const urls={created:[],revoked:[],blobs:[]}; class FixtureURL extends URL { static createObjectURL(blob){urls.blobs.push(blob);const id='blob:fixture-'+urls.created.length;urls.created.push(id);return id;} static revokeObjectURL(id){urls.revoked.push(id);} }\nconst assert=require");
 source=source.replace('URL,URLSearchParams,TextEncoder,btoa,Uint8Array','URL:FixtureURL,URLSearchParams,TextEncoder,btoa,atob,Blob,Uint8Array');
 source=source.replace('const app={dom,root,','dom.window.HTMLAnchorElement.prototype.click=function(){};\n const app={urls,dom,root,');
 m._compile(source,filename);return m.exports;
}
const ok=result=>({ok:true,result}),digest=bytes=>createHash('sha256').update(bytes).digest('hex');
const data=Buffer.from('Synthetic portable bytes — 中文');
const artifact=(bytes=data)=>({id:'export-fixture',state:'ready',format:'bundle',filename:'bookmarks.zip',size:bytes.length,digest:digest(bytes),counts:{items:1},limitations:['No jobs or credentials.']});
const read=(bytes=data,offset=0)=>({artifact_id:'export-fixture',offset,next_offset:bytes.length,eof:true,content_base64:bytes.subarray(offset).toString('base64'),size:bytes.length,digest:digest(bytes),filename:'bookmarks.zip',mime_type:'application/zip'});
async function choose(app,bytes=data,custom={}){const file={name:'fixture.zip',size:bytes.length,lastModified:1,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),...custom};const input=app.field('Backup file');assert.ok(input,'Backup file control');Object.defineProperty(input,'files',{configurable:true,value:[file]});await React.act(async()=>input.dispatchEvent(new app.dom.window.Event('change',{bubbles:true})));return file;}
for(const target of ['desktop','dashboard'])test(target+': ready export exposes the exact filename, byte size, format version and integrity digest',async()=>{
 const helpers=fixture(),value={...artifact(),format_version:1};const app=await helpers.mount(target,{overrideApi:route=>route==='/exports'?ok(value):undefined});
 try{await open(app,helpers);await helpers.click(helpers.button(app,'Generate export'),app);const text=app.element.querySelector('.hb-dialog-data').textContent;assert.match(text,/bookmarks\.zip/);assert.ok(text.includes(value.size+' bytes'));assert.ok(text.includes('Backup format version 1'));assert.ok(text.includes(value.digest));assert.equal(app.urls.created.length,0);
 }finally{await app.close();}
});
const preview={preview_id:'preview-fixture',input_digest:digest(data),counts:{items:1,assets:0},format_version:1,empty_target:true,limitations:['No jobs or credentials restored.']};
async function open(app,helpers){await helpers.click(helpers.button(app,'Data'),app);}
async function settle(){for(let n=0;n<4;n++)await React.act(async()=>{await new Promise(resolve=>setImmediate(resolve));});}
async function until(predicate){for(let n=0;n<50&&!predicate();n++)await settle();assert.ok(predicate(),'Expected asynchronous operation to settle');}
for(const target of ['desktop','dashboard'])test(target+': discarding an unrelated file does not release a pending export admission',async()=>{
 const helpers=fixture();let release,requestId;const app=await helpers.mount(target,{overrideApi:(route,init)=>{if(route==='/exports'){requestId=init.body.request_id;return new Promise(resolve=>release=resolve);}}});
 try{await open(app,helpers);await choose(app);await helpers.click(helpers.button(app,'Generate export'),app);await helpers.click(helpers.button(app,'Close data'),app);await helpers.click(helpers.button(app,'Discard file and close'),app);await open(app,helpers);assert.equal(helpers.button(app,'Check export request').disabled,true);assert.equal(helpers.button(app,'Generate export').disabled,true);await React.act(async()=>release(ok(artifact())));assert.match(app.element.querySelector('.hb-dialog-data').textContent,new RegExp(requestId));assert.equal(helpers.button(app,'Download export').disabled,false);
 }finally{release?.(ok(artifact()));await app.close();}
});
for(const target of ['desktop','dashboard'])test(target+': lost chunk acknowledgement resumes at server offset without replaying the chunk',async()=>{
 const bytes=Buffer.alloc(40000,42),helpers=fixture(),requests=[],offsets=[];let offset=0,failed=false;const app=await helpers.mount(target,{overrideApi:(route,init)=>{
 if(route==='/backups/uploads'){requests.push(init.body);return ok({id:'upload-fixture',size:bytes.length,digest:digest(bytes),offset});}
 if(route.endsWith('/chunks')){offsets.push(init.body.offset);offset=init.body.offset+Buffer.from(init.body.content_base64,'base64').length;if(!failed){failed=true;throw Error('lost ack');}return ok({id:'upload-fixture',size:bytes.length,digest:digest(bytes),offset});}
 if(route==='/backups/preview')return ok({...preview,input_digest:digest(bytes)});
 }});
 try{await open(app,helpers);await choose(app,bytes);await helpers.click(helpers.button(app,'Upload and preview backup'),app);await until(()=>failed&&!helpers.button(app,'Resume upload and preview').disabled);await settle();assert.deepEqual(offsets,[0]);await helpers.click(helpers.button(app,'Resume upload and preview'),app);await until(()=>!!helpers.button(app,'Restore backup'));assert.deepEqual(offsets,[0,32768]);assert.deepEqual(requests[0],requests[1]);
 }finally{await app.close();}
});
test('desktop: delayed download response after scope loss cannot publish a URL',async()=>{
 const helpers=fixture();let release;const app=await helpers.mount('desktop',{overrideApi:route=>route==='/exports'?ok(artifact()):route.startsWith('/exports/export-fixture?')?new Promise(resolve=>release=resolve):undefined});
 try{await open(app,helpers);await helpers.click(helpers.button(app,'Generate export'),app);await helpers.click(helpers.button(app,'Download export'),app);await app.setScope({connection:'replacement'});const reads=app.apiCalls.length;await React.act(async()=>release(ok(read())));await settle();assert.equal(app.urls.created.length,0);assert.equal(app.apiCalls.length,reads);await open(app,helpers);assert.equal(helpers.button(app,'Download export').disabled,true);await app.setScope({connection:'fixture-backend'});await open(app,helpers);assert.equal(helpers.button(app,'Download export').disabled,false);
 }finally{release?.(ok(read()));await app.close();}
});
test('desktop: late export admission stays with its original scope and request identity',async()=>{
 const helpers=fixture();let release,requestId;const app=await helpers.mount('desktop',{overrideApi:(route,init)=>{if(route==='/exports'){requestId=init.body.request_id;return new Promise(resolve=>release=resolve);}}});
 try{await open(app,helpers);await helpers.click(helpers.button(app,'Generate export'),app);await app.setScope({connection:'replacement'});await open(app,helpers);const reads=app.apiCalls.length;await React.act(async()=>release(ok(artifact())));await settle();assert.equal(app.apiCalls.length,reads);assert.doesNotMatch(app.element.querySelector('.hb-dialog-data').textContent,new RegExp(requestId));assert.equal(helpers.button(app,'Download export').disabled,true);await app.setScope({connection:'fixture-backend'});await open(app,helpers);assert.match(app.element.querySelector('.hb-dialog-data').textContent,new RegExp(requestId));assert.equal(helpers.button(app,'Download export').disabled,false);assert.equal(app.apiCalls.filter(c=>c.route==='/exports').length,1);
 }finally{release?.(ok(artifact()));await app.close();}
});
for(const target of ['desktop','dashboard'])test(target+': multichunk export is assembled and hashed as one complete file',async()=>{
 const bytes=Buffer.alloc(70000,37),helpers=fixture(),offsets=[];const app=await helpers.mount(target,{overrideApi:route=>{
 if(route==='/exports')return ok(artifact(bytes));if(route.startsWith('/exports/export-fixture?')){const offset=Number(new URL(route,'https://fixture.invalid').searchParams.get('offset')),end=Math.min(offset+32768,bytes.length);offsets.push(offset);return ok({...read(bytes,offset),next_offset:end,eof:end===bytes.length,content_base64:bytes.subarray(offset,end).toString('base64')});}
 }});
 try{await open(app,helpers);await helpers.click(helpers.button(app,'Generate export'),app);await helpers.click(helpers.button(app,'Download export'),app);await until(()=>app.urls.created.length===1);assert.deepEqual(offsets,[0,32768,65536]);assert.equal(Buffer.from(await app.urls.blobs[0].arrayBuffer()).equals(bytes),true);assert.deepEqual(app.urls.revoked,app.urls.created);
 }finally{await app.close();}
});
for(const target of ['desktop','dashboard'])test(target+': discarding a file never erases an uncertain upload request identity',async()=>{
 const helpers=fixture();let requestId;const app=await helpers.mount(target,{overrideApi:(route,init)=>{if(route==='/backups/uploads'){requestId=init.body.request_id;throw Error('lost upload acknowledgement');}}});
 try{await open(app,helpers);await choose(app);await helpers.click(helpers.button(app,'Upload and preview backup'),app);await until(()=>!!requestId&&!helpers.button(app,'Resume upload and preview').disabled);await helpers.click(helpers.button(app,'Close data'),app);await helpers.click(helpers.button(app,'Discard file and close'),app);await open(app,helpers);assert.match(app.element.querySelector('.hb-dialog-data').textContent,new RegExp(requestId));assert.equal(helpers.button(app,'Upload and preview backup').disabled,true);
 }finally{await app.close();}
});
for(const target of ['desktop','dashboard'])test(target+': restore uncertainty freezes the preview and only read-only reconciliation is offered',async()=>{
 const helpers=fixture();let requestId,checks=0;const app=await helpers.mount(target,{overrideApi:(route,init)=>{
 if(route==='/backups/uploads')return ok({id:'upload-fixture',size:data.length,digest:digest(data),offset:0});
 if(route.endsWith('/chunks'))return ok({id:'upload-fixture',size:data.length,digest:digest(data),offset:data.length});
 if(route==='/backups/preview')return ok(preview);if(route==='/backups/restore'){requestId=init.body.request_id;throw Error('lost ack');}
 if(route.startsWith('/backups/requests/')){assert.equal(route,'/backups/requests/'+requestId);if(!checks++)return {ok:false,error:{code:'not_found',message:'Not found yet'}};return ok({id:'restore-fixture',state:'succeeded',counts:{items:1}});}
 }});
 try{await open(app,helpers);await choose(app);await helpers.click(helpers.button(app,'Upload and preview backup'),app);await until(()=>!!helpers.button(app,'Restore backup'));await helpers.click(app.field('Confirm empty-library restore'),app);await helpers.click(helpers.button(app,'Restore backup'),app);assert.match(app.element.textContent,new RegExp(requestId));assert.equal(helpers.button(app,'Restore backup').disabled,true);assert.equal(app.field('Backup file').disabled,true);await helpers.click(helpers.button(app,'Check restore request'),app);assert.match(app.element.textContent,/No accepted operation found yet/);assert.equal(helpers.button(app,'Restore backup').disabled,true);await helpers.click(helpers.button(app,'Check restore request'),app);assert.match(app.element.textContent,/Restore succeeded/);assert.equal(app.apiCalls.filter(c=>c.route==='/backups/restore').length,1);assert.equal(!!helpers.button(app,'Retry restore'),false);
 }finally{await app.close();}
});
for(const target of ['desktop','dashboard'])test(target+': file bounds and nonempty preview refuse restore without a write',async()=>{
 const helpers=fixture();let reads=0;const app=await helpers.mount(target,{overrideApi:route=>route==='/backups/uploads'?ok({id:'upload-fixture',size:data.length,digest:digest(data),offset:data.length}):route==='/backups/preview'?ok({...preview,empty_target:false}):undefined});
 try{await open(app,helpers);await choose(app,data,{size:536870913,arrayBuffer:async()=>{reads++;return new ArrayBuffer(0);}});assert.equal(reads,0);assert.equal(helpers.button(app,'Upload and preview backup').disabled,true);await choose(app);await helpers.click(helpers.button(app,'Upload and preview backup'),app);await until(()=>!!helpers.button(app,'Restore backup'));assert.equal(helpers.button(app,'Restore backup').disabled,true);assert.equal(app.field('Confirm empty-library restore').disabled,true);assert.equal(app.apiCalls.some(c=>c.route==='/backups/restore'),false);
 }finally{await app.close();}
});
for(const target of ['desktop','dashboard'])for(const fault of ['hash','offset','chunk_limit','file_limit'])test(target+': malformed download '+fault+' never creates a Blob URL',async()=>{
 const helpers=fixture(),app=await helpers.mount(target,{overrideApi:route=>{
 if(route==='/exports')return ok(fault==='file_limit'?{...artifact(),size:536870913}:artifact());
 if(route.startsWith('/exports/export-fixture?')){const part=read();if(fault==='hash')part.content_base64=Buffer.alloc(data.length,1).toString('base64');if(fault==='offset')part.next_offset++;if(fault==='chunk_limit')part.content_base64=Buffer.alloc(32769).toString('base64');return ok(part);}
 }});
 try{await open(app,helpers);await helpers.click(helpers.button(app,'Generate export'),app);await helpers.click(helpers.button(app,'Download export'),app);await until(()=>!!app.element.querySelector('[role=alert]'));assert.equal(app.urls.created.length,0);assert.equal(app.urls.revoked.length,0);
 }finally{await app.close();}
});
for(const target of ['desktop','dashboard'])test(target+': Blob URL is revoked even if the download control fails',async()=>{
 const helpers=fixture(),app=await helpers.mount(target,{overrideApi:route=>route==='/exports'?ok(artifact()):route.startsWith('/exports/export-fixture?')?ok(read()):undefined});
 try{await open(app,helpers);app.dom.window.HTMLAnchorElement.prototype.click=()=>{throw Error('download blocked');};await helpers.click(helpers.button(app,'Generate export'),app);await helpers.click(helpers.button(app,'Download export'),app);await until(()=>app.urls.revoked.length===1);assert.deepEqual(app.urls.revoked,app.urls.created);
 }finally{await app.close();}
});
for(const boundary of ['profile','connection'])test('desktop: delayed file read after '+boundary+' switch cannot start uploads, but its file draft remains scoped',async()=>{
 const helpers=fixture();let release;const app=await helpers.mount('desktop');
 try{await open(app,helpers);await choose(app,data,{name:'original.zip',arrayBuffer:()=>new Promise(resolve=>release=resolve)});await helpers.click(helpers.button(app,'Upload and preview backup'),app);await app.setScope(boundary==='profile'?{profile:'other'}:{connection:'other'});await open(app,helpers);assert.doesNotMatch(app.element.querySelector('.hb-dialog-data').textContent,/original.zip/);await React.act(async()=>release(data.buffer.slice(data.byteOffset,data.byteOffset+data.byteLength)));await settle();assert.equal(app.apiCalls.some(c=>c.route.startsWith('/backups')),false);await app.setScope(boundary==='profile'?{profile:'work'}:{connection:'fixture-backend'});await open(app,helpers);assert.match(app.element.querySelector('.hb-dialog-data').textContent,/original.zip/);assert.equal(helpers.button(app,'Upload and preview backup').disabled,false);
 }finally{release?.(new ArrayBuffer(0));await app.close();}
});
for(const boundary of ['profile','connection'])test('desktop: admitted restore after returning to '+boundary+' refreshes only the matching owner, without replay',async()=>{
 const helpers=fixture();let release;const app=await helpers.mount('desktop',{overrideApi:(route)=>{
 if(route==='/backups/uploads')return ok({id:'upload-fixture',size:data.length,digest:digest(data),offset:data.length});if(route==='/backups/preview')return ok(preview);if(route==='/backups/restore')return new Promise(resolve=>release=resolve);
 }});
 try{await open(app,helpers);await choose(app);await helpers.click(helpers.button(app,'Upload and preview backup'),app);await until(()=>!!helpers.button(app,'Restore backup'));await helpers.click(app.field('Confirm empty-library restore'),app);await helpers.click(helpers.button(app,'Restore backup'),app);const request=app.apiCalls.find(c=>c.route==='/backups/restore').init.body;
 await app.setScope(boundary==='profile'?{profile:'other'}:{connection:'other'});await open(app,helpers);assert.doesNotMatch(app.element.querySelector('.hb-dialog-data').textContent,new RegExp(request.request_id));await app.setScope(boundary==='profile'?{profile:'work'}:{connection:'fixture-backend'});await open(app,helpers);const reads=app.apiCalls.filter(c=>c.route.startsWith('/items?')).length;await React.act(async()=>release(ok({id:'restore-fixture',state:'succeeded',counts:{items:1}})));await settle();assert.match(app.element.querySelector('.hb-dialog-data').textContent,/Restore succeeded/);assert.ok(app.apiCalls.filter(c=>c.route.startsWith('/items?')).length>reads);assert.equal(app.apiCalls.filter(c=>c.route==='/backups/restore').length,1);
 }finally{release?.(ok({id:'restore-fixture',state:'succeeded',counts:{items:1}}));await app.close();}
});
for(const target of ['desktop','dashboard'])test(target+': pending export keeps its request identity until read-only status completes',async()=>{
 const helpers=fixture();let creates=0;const app=await helpers.mount(target,{overrideApi:(route)=>{if(route==='/exports'){creates++;return ok({...artifact(),state:'pending'});}if(route.startsWith('/exports/requests/'))return ok(artifact());}});
 try{await open(app,helpers);await helpers.click(helpers.button(app,'Generate export'),app);assert.equal(helpers.button(app,'Generate export').disabled,true);await helpers.click(helpers.button(app,'Check export request'),app);assert.equal(creates,1);assert.equal(helpers.button(app,'Download export').disabled,false);
 }finally{await app.close();}
});
for(const target of ['desktop','dashboard'])test(target+': HTML Trash choice does not leak into a portable bundle request',async()=>{
 const helpers=fixture(),app=await helpers.mount(target,{overrideApi:route=>route==='/exports'?ok(artifact()):undefined});
 try{await open(app,helpers);await helpers.typeField(app,'Export format','html');await helpers.click(app.field('Include Trash in HTML'),app);await helpers.typeField(app,'Export format','bundle');await helpers.click(helpers.button(app,'Generate export'),app);assert.equal(app.apiCalls.find(c=>c.route==='/exports').init.body.include_trash,false);
 }finally{await app.close();}
});
for(const target of ['desktop','dashboard'])test(target+': Stop keeps the admitted chunk, then explicit resume reuses identity and authoritative offset',async()=>{
 const bytes=Buffer.alloc(70000,83),helpers=fixture(),creates=[],chunks=[];let release,offset=0;const app=await helpers.mount(target,{overrideApi:(route,init)=>{
 if(route==='/backups/uploads'){creates.push(init.body);return ok({id:'upload-fixture',size:bytes.length,digest:digest(bytes),offset});}
 if(route.endsWith('/chunks')){chunks.push(init.body);if(chunks.length===1)return new Promise(resolve=>release=()=>{offset=32768;resolve(ok({id:'upload-fixture',size:bytes.length,digest:digest(bytes),offset}));});offset=init.body.offset+Buffer.from(init.body.content_base64,'base64').length;return ok({id:'upload-fixture',size:bytes.length,digest:digest(bytes),offset});}
 if(route==='/backups/preview')return ok({...preview,input_digest:digest(bytes)});
 }});
 try{await open(app,helpers);await choose(app,bytes);await helpers.click(helpers.button(app,'Upload and preview backup'),app);await until(()=>!!release);await helpers.click(helpers.button(app,'Stop transfer'),app);await React.act(async()=>release());await settle();assert.equal(chunks.length,1);assert.equal(app.apiCalls.some(c=>c.route==='/backups/preview'),false);
 await helpers.click(helpers.button(app,'Resume upload and preview'),app);await until(()=>!!helpers.button(app,'Restore backup'));assert.deepEqual(creates[0],creates[1]);assert.deepEqual(chunks.map(c=>c.offset),[0,32768,65536]);assert.ok(chunks.every(c=>Buffer.from(c.content_base64,'base64').length<=32768));
 }finally{release?.();await app.close();}
});
for(const target of ['desktop','dashboard'])test(target+': dirty-file close guard preserves its file and discard invalidates delayed reads',async()=>{
 const helpers=fixture();let release;const app=await helpers.mount(target);
 try{await open(app,helpers);await choose(app,data,{name:'pending.zip',arrayBuffer:()=>new Promise(resolve=>release=resolve)});await helpers.click(helpers.button(app,'Upload and preview backup'),app);await helpers.click(helpers.button(app,'Close data'),app);assert.match(app.element.textContent,/Keep this selected backup/);await helpers.click(helpers.button(app,'Keep editing data'),app);assert.match(app.element.textContent,/pending.zip/);
 await helpers.click(helpers.button(app,'Close data'),app);await helpers.click(helpers.button(app,'Discard file and close'),app);await open(app,helpers);await React.act(async()=>release(data.buffer.slice(data.byteOffset,data.byteOffset+data.byteLength)));await settle();assert.doesNotMatch(app.element.textContent,/pending.zip/);assert.equal(app.apiCalls.some(c=>c.route.startsWith('/backups')),false);assert.equal(helpers.button(app,'Upload and preview backup').disabled,true);
 }finally{release?.(new ArrayBuffer(0));await app.close();}
});
for(const target of ['desktop','dashboard'])test(target+': lost export acknowledgement is resolved only by exact read-only request lookup',async()=>{
 const helpers=fixture();let requestId,writes=0;const app=await helpers.mount(target,{overrideApi:(route,init)=>{
 if(route==='/exports'){writes++;requestId=init.body.request_id;throw Error('lost acknowledgement');}
 if(route.startsWith('/exports/requests/')){assert.equal(route,'/exports/requests/'+requestId);return ok(artifact());}
 }});
 try{await open(app,helpers);await helpers.click(helpers.button(app,'Generate export'),app);assert.equal(helpers.button(app,'Generate export').disabled,true);assert.match(app.element.textContent,new RegExp(requestId));
 await helpers.click(helpers.button(app,'Check export request'),app);assert.equal(writes,1);assert.equal(helpers.button(app,'Download export').disabled,false);assert.equal(app.apiCalls.at(-1).init,undefined);
 }finally{await app.close();}
});
for(const target of ['desktop','dashboard'])test(target+': a reloaded page can inspect an operation ID without submitting any mutation',async()=>{
 const helpers=fixture(),app=await helpers.mount(target,{overrideApi:route=>route==='/backups/requests/existing-request'?ok({id:'restore-fixture',state:'succeeded',counts:{items:1}}):undefined});
 try{await open(app,helpers);await helpers.typeField(app,'Operation kind','restore');await helpers.typeField(app,'Operation request ID','existing-request');await helpers.click(helpers.button(app,'Inspect operation'),app);assert.match(app.element.textContent,/succeeded/);assert.equal(app.apiCalls.filter(c=>c.init?.method==='POST').length,0);assert.equal(!!helpers.button(app,'Restore backup'),false);
 }finally{await app.close();}
});
for(const target of ['desktop','dashboard'])test(target+': Generate is separate from integrity-checked Download and revokes its URL',async()=>{
 const helpers=fixture(),app=await helpers.mount(target,{overrideApi:(route)=>route==='/exports'?ok(artifact()):route.startsWith('/exports/export-fixture?')?ok(read()):undefined});
 try{await open(app,helpers);assert.equal(app.apiCalls.some(c=>c.route.startsWith('/exports')),false);assert.equal(helpers.button(app,'Download export').disabled,true);
 await helpers.click(helpers.button(app,'Generate export'),app);assert.equal(app.apiCalls.filter(c=>c.route.startsWith('/exports/export-fixture?')).length,0);
 await helpers.click(helpers.button(app,'Download export'),app);await until(()=>app.urls.created.length===1);assert.deepEqual(app.urls.revoked,app.urls.created);assert.equal(Buffer.from(await app.urls.blobs[0].arrayBuffer()).equals(data),true);
 assert.equal(app.calls.some(c=>c.method==='prompt.submit'),false);assert.deepEqual(app.apiCalls.find(c=>c.route==='/exports').init.body.format,'bundle');
 }finally{await app.close();}
});
for(const target of ['desktop','dashboard'])test(target+': read-only inspected export downloads that exact snapshot without generation',async()=>{
 const helpers=fixture(),app=await helpers.mount(target,{overrideApi:route=>route==='/exports/requests/saved-export'?ok(artifact()):route.startsWith('/exports/export-fixture?')?ok(read()):undefined});
 try{await open(app,helpers);await helpers.typeField(app,'Operation request ID','saved-export');await helpers.click(helpers.button(app,'Inspect operation'),app);assert.equal(app.apiCalls.filter(c=>c.init?.method==='POST').length,0);assert.match(app.element.textContent,new RegExp(digest(data)));await helpers.click(helpers.button(app,'Download inspected export'),app);await until(()=>app.urls.created.length===1);assert.equal(Buffer.from(await app.urls.blobs[0].arrayBuffer()).equals(data),true);assert.deepEqual(app.urls.created,app.urls.revoked);assert.equal(app.apiCalls.some(c=>c.route==='/exports'),false);
 }finally{await app.close();}
});
for(const target of ['desktop','dashboard'])test(target+': confirmed failed restore permits only explicit same-request recovery',async()=>{
 const helpers=fixture(),requests=[];let release,lookups=0;const app=await helpers.mount(target,{overrideApi:(route,init)=>{
  if(route==='/backups/uploads')return ok({id:'upload-fixture',size:data.length,digest:digest(data),offset:data.length});
  if(route==='/backups/preview')return ok(preview);
  if(route==='/backups/restore'){requests.push({...init.body});if(requests.length===1)throw Error('Lost failed-commit response');return new Promise(resolve=>release=resolve);}
  if(route.startsWith('/backups/requests/')){lookups++;return lookups===1?{ok:false,error:{code:'not_found',message:'Unknown'}}:ok({id:'restore-fixture',state:'failed',counts:{}});}
 }});
 try{await open(app,helpers);await choose(app);await helpers.click(helpers.button(app,'Upload and preview backup'),app);await until(()=>!!helpers.button(app,'Restore backup'));await helpers.click(app.field('Confirm empty-library restore'),app);await helpers.click(helpers.button(app,'Restore backup'),app);
  assert.equal(!!helpers.button(app,'Retry failed restore'),false);await helpers.click(helpers.button(app,'Check restore request'),app);assert.equal(!!helpers.button(app,'Retry failed restore'),false);assert.equal(requests.length,1);
  await helpers.click(helpers.button(app,'Check restore request'),app);assert.equal(helpers.button(app,'Retry failed restore')?.disabled,false,'Exact failed receipt must enable deliberate recovery');assert.equal(requests.length,1);assert.equal(app.field('Backup file').disabled,true);
  await helpers.click(helpers.button(app,'Close data'),app);await open(app,helpers);assert.match(app.element.textContent,/fixture.zip/);await helpers.click(helpers.button(app,'Retry failed restore'),app);assert.deepEqual(requests[1],requests[0]);assert.equal(helpers.button(app,'Check restore request').disabled,true);assert.equal(!!helpers.button(app,'Retry failed restore'),false);
  await React.act(async()=>release(ok({id:'restore-fixture',state:'succeeded',counts:{items:1}})));assert.match(app.element.textContent,/Restore succeeded/);assert.equal(requests.length,2);
 }finally{release?.(ok({id:'restore-fixture',state:'succeeded',counts:{items:1}}));await app.close();}
});
for(const target of ['desktop','dashboard'])test(target+': bounded upload verifies full file and previews before an explicitly confirmed restore',async()=>{
 const helpers=fixture(),posts=[];let uploadDigest;const app=await helpers.mount(target,{overrideApi:(route,init)=>{
 if(init?.method==='POST')posts.push({route,body:init.body});
 if(route==='/backups/uploads'){uploadDigest=init.body.digest;return ok({id:'upload-fixture',size:data.length,offset:0,digest:uploadDigest});}
 if(route.endsWith('/chunks'))return ok({id:'upload-fixture',size:data.length,offset:data.length,digest:uploadDigest});
 if(route==='/backups/preview')return ok(preview);if(route==='/backups/restore')return ok({id:'restore-fixture',state:'succeeded',counts:{items:1}});
 }});
 try{await open(app,helpers);await choose(app);assert.equal(posts.length,0);await helpers.click(helpers.button(app,'Upload and preview backup'),app);await until(()=>!!helpers.button(app,'Restore backup'));
 assert.equal(uploadDigest,digest(data));assert.deepEqual(posts.map(p=>p.route),['/backups/uploads','/backups/uploads/upload-fixture/chunks','/backups/preview']);assert.equal(Buffer.from(posts[1].body.content_base64,'base64').equals(data),true);
 assert.equal(helpers.button(app,'Restore backup').disabled,true);await helpers.click(app.field('Confirm empty-library restore'),app);await helpers.click(helpers.button(app,'Restore backup'),app);assert.equal(posts.at(-1).body.preview_id,preview.preview_id);assert.equal(posts.at(-1).body.input_digest,preview.input_digest);assert.match(app.element.textContent,/Restore succeeded/);assert.equal(app.calls.some(c=>c.method==='prompt.submit'),false);
 }finally{await app.close();}
});
