'use strict';
// Actual emitted UI + real Dashboard/backend. No simulated provider responses.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
async function run({chromium,baseURL,outputDir,allowWrite=false,imagePath}){
 const url=new URL(baseURL);assert.ok(['http:','https:'].includes(url.protocol)&&url.hostname==='127.0.0.1'&&!url.username&&!url.password&&url.pathname==='/'&&!url.search&&!url.hash,'Select a credential-free loopback origin');
 fs.mkdirSync(outputDir,{recursive:true});const browser=await chromium.launch({headless:true,executablePath:process.env.BOOKMARKS_CHROME||'/usr/bin/google-chrome',args:['--no-sandbox']});
 const errors=[],rows=[],methods=[];
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1100}});page.on('pageerror',error=>errors.push(error.message));
  page.on('websocket',socket=>socket.on('framesent',event=>{try{const frame=JSON.parse(event.payload);if(frame.method)methods.push(frame.method);}catch{}}));
  await page.goto(baseURL.replace(/\/$/,'')+'/bookmarks');await page.locator('.hb-library').waitFor({timeout:60000});await page.getByRole('button',{name:'Add',exact:true}).waitFor();
  const noThanks=page.getByRole('button',{name:'No thanks',exact:true});if(await noThanks.isVisible())await noThanks.click();
  const color=await page.locator('.hb-workspace').evaluate(el=>({actual:getComputedStyle(el).color,expected:getComputedStyle(document.documentElement).getPropertyValue('--midground').trim()}));
  assert.notEqual(color.actual,'rgb(0, 0, 0)','Library text must inherit the readable host text token in dark mode');
  rows.push({check:'actual_dashboard_text_color',...color});
  const titleStyle=await page.locator('.hb-title-button').first().evaluate(el=>({spacing:getComputedStyle(el).letterSpacing,shadow:getComputedStyle(el).boxShadow}));assert.ok(titleStyle.spacing==='normal'||parseFloat(titleStyle.spacing)<1,'Card titles must not inherit wide action-button letter spacing');assert.equal(titleStyle.shadow,'none','Card headlines must not inherit an action-button bevel');
  const add=page.getByRole('button',{name:'Add',exact:true}),dialog=page.getByRole('dialog');
  await add.click();await page.getByLabel('Bookmark URL',{exact:true}).fill('https://example.org/unsaved-browser');await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Keep editing',exact:true}).click();assert.equal(await page.getByLabel('Bookmark URL',{exact:true}).inputValue(),'https://example.org/unsaved-browser');
  // Native modal must keep both forward and reverse keyboard traversal inside.
  for(const key of ['Tab','Shift+Tab'])for(let i=0;i<12;i++){await page.keyboard.press(key);assert.equal(await dialog.evaluate(el=>el.contains(document.activeElement)),true);}
  await page.keyboard.press('Escape');await page.getByRole('button',{name:'Discard',exact:true}).click();await dialog.waitFor({state:'hidden'});assert.equal(await add.evaluate(el=>document.activeElement===el),true);
  rows.push({check:'dirty_escape_keep_discard_focus_containment_return',ok:true});
  let savedId=null,title;
  if(allowWrite){
   assert.ok(imagePath&&fs.existsSync(imagePath),'Choose an explicit synthetic image file');
   await add.click();await page.getByLabel('Bookmark URL',{exact:true}).fill('file:///not-authorized');await page.getByRole('button',{name:'Save',exact:true}).click();await dialog.getByRole('alert').waitFor();assert.equal(await page.getByRole('button',{name:'Verify save',exact:true}).count(),0);assert.equal(await page.getByLabel('Personal notes',{exact:true}).isEnabled(),true);await page.getByRole('button',{name:'Cancel',exact:true}).click();await page.getByRole('button',{name:'Discard',exact:true}).click();
   // Explicit transport fault: abort before dispatch. Receipt 404 and retry are
   // real HTTP/SDK responses, never synthesized successful API/model output.
   const pattern='**/api/plugins/hermes-bookmarks/items',abort=route=>route.request().method()==='POST'?route.abort('connectionreset'):route.continue();await page.route(pattern,abort);
   await add.click();await page.getByLabel('Bookmark URL',{exact:true}).fill('https://example.org/recovered-'+Date.now());await page.getByRole('button',{name:'Save',exact:true}).click();await page.getByRole('button',{name:'Verify save',exact:true}).waitFor();await page.unroute(pattern,abort);await page.getByRole('button',{name:'Verify save',exact:true}).click();await page.getByRole('button',{name:'Retry original save',exact:true}).click();await dialog.waitFor({state:'hidden'});rows.push({check:'real_sdk_400_and_receipt_404_with_explicit_transport_fault',ok:true});
   await page.getByRole('button',{name:'New collection',exact:true}).click();const collectionName='Synthetic resized collection '+Date.now();await page.getByLabel('Collection name',{exact:true}).fill(collectionName);await page.setViewportSize({width:480,height:1100});assert.equal(await page.getByLabel('Collection name',{exact:true}).inputValue(),collectionName);await page.getByRole('button',{name:'Save collection',exact:true}).click();await dialog.waitFor({state:'hidden'});await page.setViewportSize({width:1440,height:1100});rows.push({check:'actual_collection_draft_survives_resize_and_saves',ok:true});
   title='Synthetic browser bookmark '+Date.now();await add.click();await page.getByLabel('Bookmark URL',{exact:true}).fill('https://example.org/browser-'+Date.now());await page.getByLabel('Title',{exact:true}).fill(title);
   await dialog.locator('summary').filter({hasText:/^Notes/}).click();await page.getByLabel('Personal notes',{exact:true}).fill('## Synthetic note\n\nSaved from the actual browser. <script>window.BOOKMARKS_UNSAFE=true</script>');await page.getByRole('button',{name:'Preview notes',exact:true}).click();
   assert.equal(await page.evaluate(()=>window.BOOKMARKS_UNSAFE),undefined);
   await dialog.locator('summary').filter({hasText:/^Tags/}).click();await page.getByLabel('Tags',{exact:true}).fill('BrowserQA, Reading, "Research, AI"');
   await dialog.locator('summary').filter({hasText:/^Description/}).click();await page.getByLabel('Description',{exact:true}).fill('A synthetic saved description');
   await dialog.locator('summary').filter({hasText:/^Image attachments/}).click();await page.getByLabel('Attachment images',{exact:true}).setInputFiles(imagePath);await dialog.locator('[data-asset-id]').waitFor();
   await page.getByRole('button',{name:'Save',exact:true}).click();await dialog.waitFor({state:'hidden'});
   await page.getByRole('button',{name:'Open details '+title,exact:true}).click();await page.getByRole('button',{name:'Edit',exact:true}).waitFor();assert.match(await dialog.innerText(),/Synthetic note/);await dialog.locator('img').waitFor({timeout:15000});assert.equal(await dialog.locator('img').count(),1);
   await page.getByRole('button',{name:'Edit',exact:true}).click();await page.getByLabel('Personal notes',{exact:true}).fill('Synthetic edited browser note');
   await page.evaluate(async title=>{const sdk=window.__HERMES_PLUGIN_SDK__,page=await sdk.fetchJSON('/api/plugins/hermes-bookmarks/items?query='+encodeURIComponent(title)),item=page.result.items.find(item=>item.title===title);await sdk.fetchJSON('/api/plugins/hermes-bookmarks/items/'+item.id+'/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_revision:item.revision,changes:{description:'Synthetic concurrent description'}})});},title);
   await page.getByRole('button',{name:'Save',exact:true}).click();await page.getByRole('button',{name:'Keep editing',exact:true}).click();await page.getByRole('button',{name:'Use reviewed revision',exact:true}).click();assert.equal(await page.getByLabel('Personal notes',{exact:true}).inputValue(),'Synthetic edited browser note');await page.getByRole('button',{name:'Save',exact:true}).click();await dialog.waitFor({state:'hidden'});
   const record=await page.evaluate(async title=>{const result=await window.__HERMES_PLUGIN_SDK__.fetchJSON('/api/plugins/hermes-bookmarks/items?query='+encodeURIComponent(title));return result.result.items.find(item=>item.title===title);},title);
   assert.equal(record.notes,'Synthetic edited browser note');assert.equal(record.description,'Synthetic concurrent description');assert.ok(record.tags.includes('Research, AI'));assert.equal(record.attachments.length,1);savedId=record.id;rows.push({check:'real_sdk_409_explicit_compare_rebase_and_comma_tag_preservation',ok:true});
   rows.push({check:'actual_form_capture_upload_edit_authenticated_readback',ok:true,item_id:savedId});
   await page.getByRole('button',{name:'Tag BrowserQA',exact:true}).click();await page.waitForFunction(()=>document.querySelector('[aria-label="Remove tag filter BrowserQA"]'));
   await page.getByRole('button',{name:'List view',exact:true}).click();assert.equal(await page.locator('.hb-items-grid').getAttribute('data-mode'),'list');await page.getByRole('button',{name:'Remove tag filter BrowserQA',exact:true}).click();
   await page.getByRole('button',{name:'Grid view',exact:true}).click();
  }
  // Ask prepares a real Hermes chat with a visible reference but never sends.
  await page.getByRole('button',{name:'Ask Hermes',exact:true}).first().click();await page.getByLabel('Message Hermes',{exact:true}).waitFor({timeout:30000});await page.getByLabel('Message Hermes',{exact:true}).fill('An unsent synthetic draft');
  assert.equal(methods.includes('prompt.submit')||methods.includes('session.create'),false);await page.getByRole('button',{name:'Close chat',exact:true}).click();
  for(const theme of ['dark','light']){
   await page.setViewportSize({width:1440,height:1100});
   const picker=page.getByText(/^(Hermes Teal|Nous Blue)$/i).last(),desired=theme==='dark'?'Hermes Teal':'Nous Blue';
   if((await picker.innerText()).toLowerCase()!==desired.toLowerCase()){await picker.click();await page.getByText(new RegExp('^'+desired+'$','i')).click();}
   for(const width of [1440,390]){
    await page.setViewportSize({width,height:1100});
    const facts=await page.locator('.hb-workspace').evaluate(el=>({viewport:innerWidth,width:el.clientWidth,document_overflow:document.documentElement.scrollWidth>innerWidth,workspace_overflow:el.scrollWidth>el.clientWidth,library_visible:!!el.querySelector('.hb-library').getClientRects().length,color:getComputedStyle(el).color}));
    assert.equal(facts.document_overflow||facts.workspace_overflow,false,'Responsive library overflow');assert.equal(facts.library_visible,true);
    const file='bookmarks-library-dashboard-'+theme+'-'+width+'.png';await page.screenshot({path:path.join(outputDir,file)});rows.push({check:'visual',theme,file,...facts});
    if(width===390){await page.getByRole('button',{name:'Toggle library navigation',exact:true}).click();assert.equal(await page.getByRole('navigation',{name:'Library navigation',exact:true}).isVisible(),true);await page.keyboard.press('Escape');assert.equal(await page.getByRole('navigation',{name:'Library navigation',exact:true}).isVisible(),false,'Escape must dismiss narrow navigation');await page.getByRole('button',{name:'Toggle library navigation',exact:true}).click();await page.getByRole('button',{name:'Inbox',exact:true}).click();assert.equal(await page.getByRole('navigation',{name:'Library navigation',exact:true}).isVisible(),false);await page.getByRole('button',{name:'Toggle library navigation',exact:true}).click();await page.getByRole('button',{name:'All items',exact:true}).click();}
    await page.getByRole('button',{name:'Add',exact:true}).click();await page.getByLabel('Title',{exact:true}).fill('Synthetic draft for UI verification');await dialog.locator('summary').filter({hasText:/^Notes/}).click();await page.getByLabel('Personal notes',{exact:true}).fill('A personal note, separate from the AI summary.');
    const formFacts=await dialog.evaluate(el=>({dialog_overflow:el.scrollWidth>el.clientWidth,width:el.clientWidth,height:el.clientHeight}));assert.equal(formFacts.dialog_overflow,false,'Modal form horizontal overflow');const formFile='bookmarks-library-form-'+theme+'-'+width+'.png';await page.screenshot({path:path.join(outputDir,formFile)});rows.push({check:'form_visual',theme,file:formFile,...formFacts});await page.getByRole('button',{name:'Cancel',exact:true}).click();await page.getByRole('button',{name:'Discard',exact:true}).click();
    await page.getByRole('button',{name:'Chat',exact:true}).click();assert.equal(await page.getByLabel('Message Hermes',{exact:true}).inputValue(),'An unsent synthetic draft');await page.getByRole('button',{name:'Close chat',exact:true}).click();
   }
  }
  await page.setViewportSize({width:1440,height:1100});await page.locator('.hb-workspace-frame').evaluate(el=>el.style.width='480px');
  await page.getByRole('button',{name:'Chat',exact:true}).click();assert.equal(await page.locator('.hb-library').isVisible(),false);assert.equal(await page.getByLabel('Message Hermes',{exact:true}).isVisible(),true);await page.getByRole('button',{name:'Close chat',exact:true}).click();await page.locator('.hb-workspace-frame').evaluate(el=>el.style.removeProperty('width'));
  rows.push({check:'container_resize_and_theme_preserve_library_chat',ok:true});
  if(savedId){await page.reload();await page.getByRole('button',{name:'Open details '+title,exact:true}).click();await page.getByRole('button',{name:'Edit',exact:true}).waitFor();assert.match(await dialog.innerText(),/Synthetic edited browser note/);await page.getByRole('button',{name:'Close details',exact:true}).click();rows.push({check:'reopened_persistence',ok:true});}
  assert.equal(methods.includes('prompt.submit')||methods.includes('session.create'),false);assert.deepEqual(errors,[]);
  const result={ok:true,actual_host:true,synthetic_writes:allowWrite,rows,page_errors:errors,rpc_methods:[...new Set(methods)],provider_inference:false};fs.writeFileSync(path.join(outputDir,'browser-evidence.json'),JSON.stringify(result,null,2));return result;
 }finally{await browser.close();}
}
module.exports={run};
if(require.main===module){const [baseURL,outputDir,imagePath,writeFlag]=process.argv.slice(2);const {chromium}=require(process.env.BOOKMARKS_PLAYWRIGHT||'playwright');run({chromium,baseURL,outputDir,imagePath,allowWrite:writeFlag==='--allow-write'}).then(report=>console.log(JSON.stringify(report,null,2))).catch(error=>{console.error(error.stack);process.exitCode=1;});}
