'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict');
async function main(origin,output){
 assert.equal(new URL(origin).hostname,'127.0.0.1');
 const {chromium}=require(process.env.BOOKMARKS_PLAYWRIGHT||'playwright');const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1100}}),rows=[];
 try{
  await page.goto(origin+'/bookmarks');await page.getByRole('button',{name:'AI settings',exact:true}).waitFor({timeout:60000});const dismiss=page.getByRole('button',{name:'No thanks',exact:true});if(await dismiss.isVisible())await dismiss.click();
  for(const theme of ['dark','light']){
   const desired=theme==='dark'?'Hermes Teal':'Nous Blue',picker=page.getByText(/^(Hermes Teal|Nous Blue)$/i).last();if((await picker.innerText()).toLowerCase()!==desired.toLowerCase()){await picker.click();await page.getByText(new RegExp('^'+desired+'$','i')).click();}
   await page.getByRole('button',{name:'AI settings',exact:true}).click();const dialog=page.getByRole('dialog');await dialog.getByRole('button',{name:'Save AI settings',exact:true}).waitFor();
   for(const width of [1440,390]){
    await page.setViewportSize({width,height:1100});await dialog.getByRole('button',{name:'Save AI settings',exact:true}).hover();
    const facts=await dialog.evaluate(el=>{
     const canvas=document.createElement('canvas');canvas.width=canvas.height=1;const ctx=canvas.getContext('2d');
     function rgba(color){ctx.clearRect(0,0,1,1);ctx.fillStyle=color;ctx.fillRect(0,0,1,1);return [...ctx.getImageData(0,0,1,1).data].map((v,i)=>i===3?v/255:v);}
     function blend(a,b){return a.slice(0,3).map((v,i)=>v*a[3]+b[i]*(1-a[3]));}
     function background(node){const stack=[];for(let n=node;n;n=n.parentElement)stack.unshift(n);return stack.reduce((bg,n)=>blend(rgba(getComputedStyle(n).backgroundColor),bg),[255,255,255]);}
     function lum(rgb){return rgb.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);}
     function measured(node){const style=getComputedStyle(node),bg=background(node),fg=blend(rgba(style.color),bg),a=lum(fg),b=lum(bg);return {foreground:style.color,background:style.backgroundColor,contrast:(Math.max(a,b)+.05)/(Math.min(a,b)+.05),font_size:style.fontSize,letter_spacing:style.letterSpacing};}
     const description=[...el.querySelectorAll('p')].find(p=>p.textContent.startsWith('Shared-library processing'));
     return {body:measured(el),description:description?measured(description):null,primary_hover:measured(el.querySelector('[aria-label="Save AI settings"]'))};
    });
    for(const [role,value] of Object.entries(facts))if(value)rows.push({theme,width,role,...value,normal_text_4_5:value.contrast>=4.5});
   }
   await dialog.getByRole('button',{name:'Cancel AI settings',exact:true}).click();await page.setViewportSize({width:1440,height:1100});
  }
  const report={actual_dashboard:true,synthetic:true,provider_calls:false,rows,all_normal_text_4_5:rows.every(row=>row.normal_text_4_5)};fs.writeFileSync(output,JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
 }finally{await browser.close();}
}
if(require.main===module){main(...process.argv.slice(2)).catch(error=>{console.error(error.stack);process.exitCode=1;});}
