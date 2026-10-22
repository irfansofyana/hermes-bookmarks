'use strict';
// Actual public Dashboard SDK with explicitly authorized synthetic writes only.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
async function run({chromium,baseURL,outputDir,allowWrite}){
 const origin=new URL(baseURL);assert.equal(origin.hostname,'127.0.0.1');assert.equal(allowWrite,true);
 fs.mkdirSync(outputDir,{recursive:true});const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
 const rows=[],errors=[];let page;
 try{
  page=await browser.newPage({viewport:{width:1440,height:1100}});page.on('pageerror',error=>errors.push(error.message));
  await page.goto(baseURL+'/bookmarks');await page.getByRole('button',{name:'Add',exact:true}).waitFor({timeout:60000});
  const dismiss=page.getByRole('button',{name:'No thanks',exact:true});if(await dismiss.isVisible())await dismiss.click();
  const prefix='Synthetic UX '+Date.now();
  const seed=await page.evaluate(async prefix=>{
   const api=async(route,body)=>{const payload=await window.__HERMES_PLUGIN_SDK__.fetchJSON('/api/plugins/hermes-bookmarks'+route,body===undefined?undefined:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!payload.ok)throw Error(payload.error?.code||'API failed');return payload.result;};
   const records=Array.from({length:3},(_,i)=>({url:'https://example.org/ux-'+crypto.randomUUID()+'/'+i,title:prefix+' · '+['Building a smaller, more reliable service','A reading list with useful context','Notes, sources and a long title that should wrap without hiding actions'][i],notes:'## Why I saved this\n\nA synthetic personal note with **useful context** and a checklist.\n\n- [ ] Read carefully\n- [ ] Try the example',tags:['Engineering','Read next'],description:'Synthetic bookmark for UI verification. No real personal content.',source_id:'ux-'+i,imported_summary:'An imported source summary, distinct from generated AI output.'}));
   const p=await api('/imports/preview',{records});const j=await api('/imports/start',{preview_id:p.preview_id,input_digest:p.input_digest,request_id:crypto.randomUUID()});return {job:j.id,titles:records.map(x=>x.title)};
  },prefix);
  const deadline=Date.now()+30000;let imported;
  while(Date.now()<deadline){imported=await page.evaluate(async id=>(await window.__HERMES_PLUGIN_SDK__.fetchJSON('/api/plugins/hermes-bookmarks/imports/'+id)).result,seed.job);if(imported.state==='succeeded')break;await new Promise(resolve=>setTimeout(resolve,150));}
  assert.equal(imported.state,'succeeded');assert.equal(imported.imported,3);console.log('seed_terminal',imported.state,imported.imported);
  const search=page.getByLabel('Search bookmarks',{exact:true});await search.fill(prefix);await page.getByRole('button',{name:'Search',exact:true}).click();await page.getByRole('button',{name:'Open details '+seed.titles[0],exact:true}).waitFor();
  const dialog=page.getByRole('dialog'),button=name=>dialog.getByRole('button',{name,exact:true});
  async function screenshot(name){const file=name+'.png';await page.screenshot({path:path.join(outputDir,file)});return file;}
  async function facts(kind,width,theme){
   await page.waitForFunction(()=>{const el=document.querySelector('[role=dialog]');if(!el)return false;const r=el.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth;},null,{timeout:5000});
   const layout=await dialog.evaluate(el=>{const r=el.getBoundingClientRect();return {left:r.left,right:r.right,width:r.width,height:r.height,overflow:el.scrollWidth>el.clientWidth,document_overflow:document.documentElement.scrollWidth>innerWidth};});assert.equal(layout.overflow||layout.document_overflow,false);assert.ok(layout.width>0&&layout.right<=width);
   for(const key of ['Tab','Shift+Tab'])for(let i=0;i<8;i++){await page.keyboard.press(key);assert.equal(await dialog.evaluate(el=>el.contains(document.activeElement)),true);}
   const file=await screenshot('bookmarks-polish-'+kind+'-'+theme+'-'+width);rows.push({check:kind,theme,viewport:width,file,...layout});
  }
  for(const theme of ['dark','light']){
   await page.setViewportSize({width:1440,height:1100});const desired=theme==='dark'?'Hermes Teal':'Nous Blue',picker=page.getByText(/^(Hermes Teal|Nous Blue)$/i).last();
   if((await picker.innerText()).toLowerCase()!==desired.toLowerCase()){await picker.click();await page.getByText(new RegExp('^'+desired+'$','i')).click();}
   rows.push({check:'library',theme,file:await screenshot('bookmarks-polish-library-'+theme+'-1440')});
   await page.getByRole('button',{name:'Add',exact:true}).click();await page.getByLabel('Bookmark URL',{exact:true}).fill('https://example.org/unsaved-ux');await page.getByLabel('Title',{exact:true}).fill('A bookmark with a little personal context');
   await dialog.locator('summary').filter({hasText:/^Notes/}).click();await page.getByLabel('Personal notes',{exact:true}).fill('A retained synthetic draft.\n\n**Markdown** stays separate from generated summaries.');
   for(const width of [1440,390]){
    await page.setViewportSize({width,height:1100});await button('Save').scrollIntoViewIfNeeded();
    const footer=await button('Save').boundingBox();assert.ok(footer.y>=0&&footer.y+footer.height<=1100);await facts('form',width,theme);
    assert.equal(await page.getByLabel('Personal notes',{exact:true}).inputValue(),'A retained synthetic draft.\n\n**Markdown** stays separate from generated summaries.');
   }
   await page.keyboard.press('Escape');await button('Keep editing').click();assert.match(await page.getByLabel('Personal notes',{exact:true}).inputValue(),/retained synthetic draft/);await button('Cancel').click();await button('Discard').click();
   await page.setViewportSize({width:1440,height:1100});await page.getByRole('button',{name:'Open details '+seed.titles[0],exact:true}).click();await page.getByRole('heading',{name:'Personal notes',exact:true}).waitFor();await facts('detail',1440,theme);await page.setViewportSize({width:390,height:1100});await facts('detail',390,theme);await button('Close details').click();await page.setViewportSize({width:1440,height:1100});
  }
  // A narrow plugin tile in a wide host must preserve form ownership.
  await page.locator('.hb-workspace-frame').evaluate(el=>el.style.width='480px');await page.getByRole('button',{name:'Add',exact:true}).click();await page.getByLabel('Title',{exact:true}).fill('Retained pane-resize draft');await page.locator('.hb-workspace-frame').evaluate(el=>el.style.width='');assert.equal(await page.getByLabel('Title',{exact:true}).inputValue(),'Retained pane-resize draft');await button('Cancel').click();await button('Discard').click();
  // Genuine service validation error retains edited fields and permits correction.
  await page.getByRole('button',{name:'Add',exact:true}).click();await page.getByLabel('Bookmark URL',{exact:true}).fill('file:///not-authorized');await page.getByLabel('Title',{exact:true}).fill('Retained rejected draft');await button('Save').click();await dialog.getByRole('alert').waitFor();assert.equal(await page.getByLabel('Title',{exact:true}).inputValue(),'Retained rejected draft');assert.equal(await button('Save').isEnabled(),true);await button('Cancel').click();await button('Discard').click();
  // Save outside the active filter still has an inspectable success action.
  const outsideTitle='Outside current filter '+Date.now();await page.getByRole('button',{name:'Add',exact:true}).click();await page.getByLabel('Bookmark URL',{exact:true}).fill('https://example.org/'+await page.evaluate(()=>crypto.randomUUID()));await page.getByLabel('Title',{exact:true}).fill(outsideTitle);await button('Save').click();await page.getByRole('button',{name:'View item',exact:true}).click();await page.getByRole('heading',{name:outsideTitle,exact:true}).waitFor();assert.equal(await search.inputValue(),prefix);await button('Close details').click();
  rows.push({check:'pane_resize_validation_retention_and_save_view_outside_filter',ok:true});
  await page.getByRole('button',{name:'Select visible items',exact:true}).click();await page.getByRole('button',{name:'Edit selection',exact:true}).click();await page.getByText('3 items reviewed',{exact:true}).waitFor();await page.setViewportSize({width:390,height:1100});await facts('bulk',390,'light');await page.setViewportSize({width:1440,height:1100});await button('Apply to 3 items').click();await page.getByText(/Applied: 3/).waitFor();
  let saved=await page.evaluate(async prefix=>(await window.__HERMES_PLUGIN_SDK__.fetchJSON('/api/plugins/hermes-bookmarks/items?query='+encodeURIComponent(prefix))).result.items,prefix);assert.equal(saved.every(x=>x.favorite),true);
  await button('Review a new action').click();await page.getByText('3 items reviewed',{exact:true}).waitFor();await page.getByLabel('Bulk action',{exact:true}).selectOption('read_later_on');
  // A real concurrent metadata edit after review must reject only that row.
  await page.evaluate(async item=>{const p=await window.__HERMES_PLUGIN_SDK__.fetchJSON('/api/plugins/hermes-bookmarks/items/'+item.id+'/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_revision:item.revision,changes:{notes:'Concurrent synthetic note'}})});if(!p.ok)throw Error('Concurrent fixture edit failed');},saved[0]);
  await button('Apply to 3 items').click();await page.getByText(/Applied: 2 · Conflicts: 1/).waitFor();rows.push({check:'real_bulk_conflict',ok:true,file:await screenshot('bookmarks-polish-bulk-results')});
  await button('Review a new action').click();await page.getByText('3 items reviewed',{exact:true}).waitFor();await page.getByLabel('Bulk action',{exact:true}).selectOption('trash');await button('Apply to 3 items').click();await page.getByText(/Applied: 3/).waitFor();
  await button('Review a new action').click();await page.getByText('3 items reviewed',{exact:true}).waitFor();await page.getByLabel('Bulk action',{exact:true}).selectOption('restore');await button('Apply to 3 items').click();await page.getByText(/Applied: 3/).waitFor();await button('Close bulk actions').click();
  saved=await page.evaluate(async prefix=>(await window.__HERMES_PLUGIN_SDK__.fetchJSON('/api/plugins/hermes-bookmarks/items?query='+encodeURIComponent(prefix))).result.items,prefix);assert.equal(saved.length,3);assert.equal(saved.every(x=>!x.deleted_at),true);assert.equal(saved.some(x=>x.notes==='Concurrent synthetic note'),true);
  rows.push({check:'real_bulk_favorite_conflict_trash_restore_notes_preserved',ok:true});
  assert.deepEqual(errors,[]);const report={ok:true,actual_dashboard:true,provider_calls:false,rows,page_errors:errors};fs.writeFileSync(path.join(outputDir,'polish-browser.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));return report;
 }catch(error){if(page){console.error((await page.locator('body').innerText()).slice(-7000));await page.screenshot({path:path.join(outputDir,'failure.png')});}throw error;}finally{await browser.close();}
}
module.exports={run};
if(require.main===module){const [baseURL,outputDir,flag]=process.argv.slice(2);const {chromium}=require(process.env.BOOKMARKS_PLAYWRIGHT||'playwright');run({chromium,baseURL,outputDir,allowWrite:flag==='--allow-write'}).catch(error=>{console.error(error.stack);process.exitCode=1;});}
