'use strict';
// Actual Dashboard/public SDK over a disposable, credential-free backend.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
async function run({chromium,baseURL,outputDir,allowWrite=false}){
 const origin=new URL(baseURL);assert.equal(origin.hostname,'127.0.0.1');assert.equal(origin.username+origin.password,'');assert.equal(allowWrite,true,'Explicit --allow-write required for synthetic browser import');
 fs.mkdirSync(outputDir,{recursive:true});const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
 const rows=[],errors=[];
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1100}});page.on('pageerror',e=>errors.push(e.message));
  await page.goto(baseURL+'/bookmarks');await page.getByRole('button',{name:'Import',exact:true}).waitFor({timeout:60000});
  const dismiss=page.getByRole('button',{name:'No thanks',exact:true});if(await dismiss.isVisible())await dismiss.click();
  await page.getByRole('button',{name:'Import',exact:true}).click();
  const dialog=page.getByRole('dialog');const button=name=>dialog.getByRole('button',{name,exact:true});
  assert.equal(await page.getByLabel('Enrich imported links',{exact:true}).isChecked(),false);
  const title='Synthetic browser import '+Date.now(),url='https://example.org/browser-import-'+Date.now();
  await page.getByLabel('Import source',{exact:true}).fill(JSON.stringify([{url,title,notes:'Browser imported **note**',tags:['BrowserImport'],collection_path:['Browser import fixtures'],source_id:'browser-source'}]));
  await page.keyboard.press('Escape');await button('Keep editing').click();assert.match(await page.getByLabel('Import source',{exact:true}).inputValue(),/Browser imported/);
  await button('Preview import').click();await page.getByRole('region',{name:'Import preview'}).waitFor().catch(()=>{});
  await button('Start import').waitFor();assert.match(await dialog.innerText(),/New: 1/);
  for(const theme of ['dark','light']){
   // Close without losing the source draft, then switch the real host theme.
   await button('Close import').click();await button('Discard import').click();
   await page.setViewportSize({width:1440,height:1100});
   const picker=page.getByText(/^(Hermes Teal|Nous Blue)$/i).last(),desired=theme==='dark'?'Hermes Teal':'Nous Blue';
   if((await picker.innerText()).toLowerCase()!==desired.toLowerCase()){await picker.click();await page.getByText(new RegExp('^'+desired+'$','i')).click();}
   await page.getByRole('button',{name:'Import',exact:true}).click();
   await page.getByLabel('Import source',{exact:true}).fill(JSON.stringify([{url,title,notes:'Browser imported **note**',tags:['BrowserImport'],collection_path:['Browser import fixtures'],source_id:'browser-source'}]));
   await button('Preview import').click();await button('Start import').waitFor();
   for(const width of [1440,390]){
    await page.setViewportSize({width,height:1100});
    // Wait for the host's responsive layout/portal transition, not just viewport acknowledgement.
    await page.waitForFunction(()=>{const el=document.querySelector('[role="dialog"]');if(!el)return false;const r=el.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth;},null,{timeout:5000});
    const facts=await dialog.evaluate(el=>({width:el.clientWidth,visible_left:el.getBoundingClientRect().left,visible_right:el.getBoundingClientRect().right,overflow:el.scrollWidth>el.clientWidth,document_overflow:document.documentElement.scrollWidth>innerWidth}));assert.equal(facts.overflow||facts.document_overflow,false);assert.ok(facts.visible_left>=0&&facts.visible_right<=width,'Dialog must fit viewport');
    for(const key of ['Tab','Shift+Tab'])for(let i=0;i<5;i++){await page.keyboard.press(key);assert.equal(await dialog.evaluate(el=>el.contains(document.activeElement)),true);}
    const file=`bookmarks-import-${theme}-${width}.png`;await page.screenshot({path:path.join(outputDir,file)});rows.push({check:'import_preview_visual_focus',theme,viewport:width,file,...facts});
   }
  }
  await button('Start import').click();await page.waitForFunction(()=>document.querySelector('[aria-label="Import progress"]')?.textContent.includes('Import succeeded'),{timeout:30000});
  assert.match(await dialog.innerText(),/Imported: 1/);const text=await dialog.innerText();const match=text.match(/Job ([a-f0-9]+)/);assert.ok(match);const jobId=match[1];
  await button('Close import').click();await page.setViewportSize({width:1440,height:1100});
  const saved=await page.evaluate(async title=>{const p=await window.__HERMES_PLUGIN_SDK__.fetchJSON('/api/plugins/hermes-bookmarks/items?query='+encodeURIComponent(title));return p.result.items[0];},title);
  assert.equal(saved.notes,'Browser imported **note**');assert.equal(saved.imported_sources[0].source_id,'browser-source');assert.equal(saved.tags.includes('BrowserImport'),true);
  await page.getByRole('button',{name:'Move to trash '+title,exact:true}).click();await page.getByRole('button',{name:'Move to trash',exact:true}).click();await page.getByRole('button',{name:'Undo trash',exact:true}).waitFor();
  await page.getByRole('button',{name:'Add',exact:true}).click();await page.getByLabel('Bookmark URL',{exact:true}).fill(url);await dialog.locator('summary').filter({hasText:/^Notes/}).click();await page.getByLabel('Personal notes',{exact:true}).fill('Unsaved browser draft on trashed duplicate');await button('Save').click();
  await page.getByRole('alert').filter({hasText:'This URL is in Trash'}).waitFor();assert.equal(await page.getByLabel('Personal notes',{exact:true}).inputValue(),'Unsaved browser draft on trashed duplicate');assert.equal(await page.getByText('Saved to your library.',{exact:true}).count(),0);
  await button('Open existing').click();await button('Close details').click();await page.getByRole('button',{name:'Add',exact:true}).click();assert.equal(await page.getByLabel('Personal notes',{exact:true}).inputValue(),'Unsaved browser draft on trashed duplicate');await button('Cancel').click();await button('Discard').click();
  const unchanged=await page.evaluate(async id=>(await window.__HERMES_PLUGIN_SDK__.fetchJSON('/api/plugins/hermes-bookmarks/items/'+id)).result,saved.id);assert.ok(unchanged.deleted_at);assert.equal(unchanged.notes,'Browser imported **note**');
  rows.push({check:'trashed_duplicate_retains_add_draft_without_overwrite_or_implicit_restore',ok:true});
  await page.getByRole('button',{name:'Undo trash',exact:true}).click();
  await page.reload();await page.getByRole('button',{name:'Import',exact:true}).click();await page.getByLabel('Import job ID',{exact:true}).fill(jobId);await button('Open import job').click();await page.waitForFunction(()=>document.querySelector('[aria-label="Import progress"]')?.textContent.includes('Import succeeded'));
  rows.push({check:'actual_preview_start_poll_notes_provenance_trash_undo_and_reload_job_inspection',ok:true,job_id:jobId,item_id:saved.id});
  assert.deepEqual(errors,[]);const report={ok:true,actual_dashboard:true,provider_calls:false,rows,page_errors:errors};fs.writeFileSync(path.join(outputDir,'import-browser.json'),JSON.stringify(report,null,2));return report;
 }finally{await browser.close();}
}
module.exports={run};
if(require.main===module){const [baseURL,outputDir,flag]=process.argv.slice(2);const {chromium}=require(process.env.BOOKMARKS_PLAYWRIGHT||'playwright');run({chromium,baseURL,outputDir,allowWrite:flag==='--allow-write'}).then(r=>console.log(JSON.stringify(r,null,2))).catch(e=>{console.error(e.stack);process.exitCode=1;});}
