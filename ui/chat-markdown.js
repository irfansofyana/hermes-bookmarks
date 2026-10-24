/* Marked supplies parsing. React allowlisting supplies the rendering boundary. */
function bookmarkMarkdown(React,text){
  const h=React.createElement,source=String(text||'').slice(0,100000);
  function render(tokens,depth=0){
    if(depth>20)return '[Nested content omitted]';
    return (tokens||[]).map((t,i)=>{
      const children=()=>t.tokens?render(t.tokens,depth+1):t.text||'';
      let node;
      if(t.type==='space')return null;
      if(t.type==='html')node=h('span',{className:'hb-literal-html'},t.raw||t.text||'');
      else if(t.type==='code')node=h('pre',null,h('code',{'data-language':String(t.lang||'').slice(0,50)},t.text));
      else if(t.type==='codespan')node=h('code',null,t.text);
      else if(t.type==='heading')node=h('h'+Math.max(1,Math.min(6,t.depth)),null,children());
      else if(t.type==='paragraph')node=h('p',null,children());
      else if(['strong','em','del'].includes(t.type))node=h(t.type,null,children());
      else if(t.type==='br'||t.type==='hr')node=h(t.type);
      else if(t.type==='blockquote')node=h('blockquote',null,children());
      else if(t.type==='list')node=h(t.ordered?'ol':'ul',t.ordered?{start:t.start}:null,t.items.map((item,j)=>h('li',{key:j},item.task?h('input',{type:'checkbox',disabled:true,checked:!!item.checked,'aria-label':item.checked?'Completed task':'Incomplete task'}):null,render(item.tokens,depth+1))));
      else if(t.type==='table')node=h('div',{className:'hb-table-scroll'},h('table',null,h('thead',null,h('tr',null,t.header.map((cell,j)=>h('th',{key:j},render(cell.tokens,depth+1))))),h('tbody',null,t.rows.map((row,j)=>h('tr',{key:j},row.map((cell,k)=>h('td',{key:k},render(cell.tokens,depth+1))))))));
      else if(t.type==='link'){
        let href=null;try{const url=new URL(t.href);if(['https:','http:','mailto:'].includes(url.protocol))href=url.href;}catch{/* Do not interpret relative or executable destinations. */}
        node=href?h('a',{href,target:'_blank',rel:'noopener noreferrer'},children()):h('span',null,children());
      }else if(t.type==='image')node=h('span',{className:'hb-image-placeholder'},(t.text||'Image')+' [image not loaded]');
      else node=children();
      return h(React.Fragment,{key:i},node);
    });
  }
  try{return h('div',{className:'hb-markdown'},render(HBMarkdown.lexer(source,{gfm:true})),String(text||'').length>source.length?h('p',null,'Display truncated. Full content remains in Hermes history.'):null);}
  catch{return h('pre',{className:'hb-markdown'},source);}
}
