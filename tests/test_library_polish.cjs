'use strict';
// Emitted-loader presentation contracts; real SDK/browser acceptance is separate.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {mount,click,button,typeField}=require('./helpers/emitted-client.cjs');

for(const target of ['desktop','dashboard'])test(target+': organized form retains disclosures, all labels and a primary footer after rejection',async()=>{
 const app=await mount(target,{overrideApi:(route,init)=>route==='/items'&&init?.method==='POST'?{ok:false,error:{code:'invalid_argument',message:'Synthetic validation rejection'}}:undefined});
 try{
  await click(button(app,'Add'),app);
  const dialog=app.element.querySelector('.hb-dialog-form');assert.ok(dialog,'Add uses the form dialog variant');
  const essentials=dialog.querySelector('[aria-label="Bookmark essentials"]');assert.ok(essentials);
  for(const label of ['Item type','Bookmark URL','Title','Collection search','Collection'])assert.ok(essentials.querySelector('[aria-label="'+label+'"]'),label);
  const form=dialog.querySelector('form'),footer=form.querySelector('.hb-form-footer');assert.ok(footer);
  assert.equal(footer.contains(button(app,'Save')),true);assert.equal(footer.contains(button(app,'Cancel')),true);
  for(const label of ['Personal notes','Tags','Description','Attachment images']){
   const field=app.field(label),disclosure=field.closest('details');assert.ok(disclosure,label+' is disclosed');
   assert.ok(disclosure.querySelector('summary').textContent.trim());
  }
  await typeField(app,'Bookmark URL','https://example.org/polish');await typeField(app,'Personal notes','### My context\n<script>unsafe()</script>');
  await typeField(app,'Tags','"Research, AI", Café');await click(button(app,'Preview notes'),app);
  assert.ok(form.querySelector('.hb-note-preview'));assert.equal(form.querySelectorAll('script').length,0);
  await click(button(app,'Save'),app);assert.match(form.textContent,/Synthetic validation rejection/);
  assert.equal(app.field('Personal notes').value,'### My context\n<script>unsafe()</script>');assert.equal(app.field('Tags').value,'"Research, AI", Café');
  assert.equal(button(app,'Save').disabled,false);assert.equal(footer.contains(button(app,'Save')),true);
  await click(button(app,'Cancel'),app);assert.ok(button(app,'Keep editing'));await click(button(app,'Keep editing'),app);assert.equal(app.field('Tags').value,'"Research, AI", Café');
 }finally{await app.close();}
});

for(const target of ['desktop','dashboard'])test(target+': detail separates personal, generated and imported content without remote reads',async()=>{
 const saved={id:'bookmark-a',title:'A synthetic article',kind:'link',url:'https://example.org/article',revision:7,notes:'My personal context',summary:'Generated saved summary',enrichment_status:'pending',tags:['AI'],tag_details:[{name:'AI',source:'generated'}],attachments:[{asset_id:'b'.repeat(32),role:'attachment'}],imported_sources:[{source:'Bookmark HTML',locator:'entry 4',source_id:'source-42',imported_summary:'Imported **source** summary <img src=x onerror=unsafe()>',source_text:'Original retained source text'}]};
 const app=await mount(target,{overrideApi:route=>route==='/items/bookmark-a'?{ok:true,result:saved}:undefined});
 try{
  await click(button(app,'Open details A synthetic article'),app);
  const dialog=app.element.querySelector('.hb-dialog-detail');assert.ok(dialog,'Details use the reading variant');
  const sections=[...dialog.querySelectorAll('.hb-detail-section')];
  assert.deepEqual(sections.map(node=>node.querySelector('h3').textContent),['Personal notes','Saved AI summary','Source & import provenance','Images']);
  assert.match(sections[0].textContent,/My personal context/);assert.doesNotMatch(sections[0].textContent,/Generated saved summary/);
  assert.match(sections[1].textContent,/Generated saved summary/);assert.doesNotMatch(sections[1].textContent,/Imported source summary/);
  assert.equal(dialog.querySelector('.hb-detail-processing').textContent,'Enrichment queued');
  const provenance=sections[2];for(const text of ['Bookmark HTML','entry 4','source-42','Imported source summary','Original retained source text'])assert.ok(provenance.textContent.includes(text),text);
  assert.equal(dialog.querySelectorAll('script,[onerror]').length,0);assert.equal(dialog.querySelectorAll('img').length,1,'Only the owned attachment is loaded');
  assert.equal(sections[3].querySelector('img').alt,'Attached image');assert.match(sections[3].querySelector('img').src,/^data:image\/png;base64,/);
  const footer=dialog.querySelector('.hb-detail-footer');for(const label of ['Edit','Ask Hermes','Close details'])assert.equal(footer.contains(button({...app,element:dialog},label)),true);
  assert.equal(app.calls.length,0);assert.equal(app.apiCalls.some(row=>row.init?.method==='POST'),false);
 }finally{await app.close();}
});

test('polish stylesheet is modal-scoped, token-mapped, responsive and keeps primary actions sticky',()=>{
 const filename='ui/library-polish.css';assert.equal(fs.existsSync(filename),true,'Dedicated scoped polish stylesheet exists');
 const css=fs.readFileSync(filename,'utf8');assert.match(css,/--hb-[\w-]+:\s*var\(--ui-bg-elevated,\s*var\(--color-card/);
 assert.doesNotMatch(css,/:root|(?:html|body)\s*\{|#[\da-f]{3,8}\b|rgba?\(/i,'No document theme or invented RGB palette');
 assert.match(css,/\.hb-dialog\.hb-dialog-form[^}]*width:\s*min\(760px/);
 assert.match(css,/@container\s+hb-modal\s*\(min-width:\s*600px\)/);
 assert.match(css,/grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/);
 assert.match(css,/\.hb-dialog[^}]*\.hb-form-footer[^}]*position:\s*sticky[^}]*bottom:\s*0/s);
 assert.match(css,/@media\s*\(max-width:\s*650px\)/);
});

test('dialog variants reach the public SDK content without dropping base styling or close guards',()=>{
 const React={createElement:(type,props,...children)=>({type,props:props||{},children}),useEffect:()=>{},useRef:()=>({current:null}),useId:()=> 'fixture'};
 const context={React,host:{},Button:'button',Input:'input'};
 const source=fs.readFileSync('desktop/plugin.js','utf8').replace(/^import .*;\n/gm,'').replace('export default','const plugin=');
 vm.runInNewContext(source+'\nthis.dialogFactory=createLibraryDialog;',context);
 const components={Dialog:'sdk-dialog',DialogContent:'sdk-content',DialogTitle:'sdk-title',DialogDescription:'sdk-description'};
 let closes=0,prevented=0;
 const Dialog=context.dialogFactory(React,components),tree=Dialog({title:'Edit bookmark',className:'hb-dialog-form',onCloseRequest:()=>closes++});
 const content=tree.children[0];assert.equal(content.props.className,'hb-dialog hb-dialog-form');
 for(const name of ['onEscapeKeyDown','onPointerDownOutside'])content.props[name]({preventDefault:()=>prevented++});
 tree.props.onOpenChange(false);assert.equal(closes,3);assert.equal(prevented,2);
 const fallback=context.dialogFactory(React,{})({title:'Edit bookmark',className:'hb-dialog-form',onCloseRequest:()=>closes++});
 assert.equal(fallback.props.className,'hb-dialog hb-dialog-form');
 fallback.props.onCancel({preventDefault:()=>prevented++});assert.equal(closes,4);
});
