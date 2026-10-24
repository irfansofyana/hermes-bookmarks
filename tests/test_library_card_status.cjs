'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {mount}=require('./helpers/emitted-client.cjs');
for(const target of ['desktop','dashboard']){
 for(const [kind,status,expected] of [['image','not_started','Image saved'],['link','succeeded','Generated fields applied']]){
  test(`${target}: ${kind}/${status} card does not invent unavailable vision or generated summary`,async()=>{
   const app=await mount(target,{overrideApi:route=>route.startsWith('/items?')?{ok:true,result:{items:[{id:'copy-check',title:'Synthetic status',kind,url:kind==='link'?'https://example.org':null,revision:1,tags:[],enrichment_status:status}],total:1,offset:0,limit:50}}:undefined});
   try{const text=app.element.querySelector('.hb-processing')?.textContent;assert.equal(text,expected);assert.doesNotMatch(text,/visual AI unavailable|Summary saved/);}finally{await app.close();}
  });
 }
}
