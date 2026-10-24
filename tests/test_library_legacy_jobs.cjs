'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {mount,click,button}=require('./helpers/emitted-client.cjs');
const ok=result=>({ok:true,result});
const record=()=>({id:'bookmark-a',title:'A synthetic article',kind:'link',url:'https://example.org',revision:7,notes:'',summary:'Old saved summary',summary_source:'legacy',summary_revision:0,tags:[],attachments:[],enrichment_job_id:'legacy-job',enrichment_status:'pending'});
const work=state=>({id:'legacy-job',item_id:'bookmark-a',revision:1,generation:1,state,attempts:0,settings_revision:null,fields:['summary','tags'],error_code:null,provider:null,model:null,coverage:null,applied_fields:[],conflicted_fields:[]});
const config=()=>({revision:5,route_ready:true,restored_intent:null,settings:{provider:'fixture',model:'synthetic',owner_profile:'owner',automatic_tags:false,automatic_summary:false,image_analysis:false,summary_language:'auto',summary_length:'medium',preferred_tags:[],guidance:'',retain_extracted_text:false,paused:true}});
for(const target of ['desktop','dashboard']){
 for(const state of ['pending','running','cancelled','succeeded','failed'])test(`${target}: migrated ${state} status has an explicit unknown settings revision and usable controls`,async()=>{
  const app=await mount(target,{overrideApi:route=>{
   if(route==='/items/bookmark-a')return ok({...record(),enrichment_status:state});
   if(route==='/enrichment/jobs/legacy-job')return ok(work(state));
   if(route==='/enrichment/jobs/legacy-job/cancel')return ok(work('cancelled'));
  }});
  try{await click(button(app,'Open details A synthetic article'),app);assert.match(app.element.textContent,new RegExp('Processing '+state));assert.match(app.element.textContent,/settings revision legacy \/ unknown/);assert.doesNotMatch(app.element.textContent,/status is unverified|identity or fields are invalid/);
   if(['pending','running'].includes(state)){assert.ok(button(app,'Cancel processing'));await click(button(app,'Cancel processing'),app);assert.match(app.element.textContent,/Processing cancelled/);assert.ok(button(app,'Retry enrichment'));}
   else assert.ok(button(app,state==='succeeded'?'Regenerate enrichment':'Retry enrichment'));
  }finally{await app.close();}
 });
 test(`${target}: a NEW admission cannot masquerade as a legacy null-revision receipt`,async()=>{
  const app=await mount(target,{overrideApi:(route,init)=>{
   if(route==='/items/bookmark-a')return ok({...record(),enrichment_job_id:null,enrichment_status:'not_started'});
   if(route==='/settings')return ok(config());
   if(route==='/items/bookmark-a/enrich')return ok({receipt:{request_id:init.body.request_id,item_id:'bookmark-a',accepted_revision:7,job_id:'legacy-job',generation:1,fields:init.body.fields,settings_revision:null},job:{...work('pending'),revision:7}});
  }});
  try{await click(button(app,'Open details A synthetic article'),app);await click(button(app,'Review enrichment'),app);await click(app.field('Confirm enrichment replacement and costs'),app);await click(button(app,'Start enrichment'),app);assert.match(app.element.textContent,/admission is uncertain/);assert.equal(!!button(app,'Cancel processing'),false);assert.equal(!!button(app,'Retry enrichment'),false);}finally{await app.close();}
 });
}
