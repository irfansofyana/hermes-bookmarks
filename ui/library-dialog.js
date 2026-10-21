function createLibraryDialog(React,components){
 const {createElement:h,useEffect,useRef,useId}=React;
 return function LibraryDialog({title,description,children,onCloseRequest}){
  const ref=useRef(null),previous=useRef(null),titleId='hb-dialog-'+useId();
  useEffect(()=>{previous.current=typeof document!=='undefined'?document.activeElement:null;if(!components.Dialog)ref.current?.showModal?.();return()=>{if(!components.Dialog&&ref.current?.open)ref.current.close?.();if(previous.current?.isConnected)previous.current.focus?.();};},[]);
  if(components.Dialog&&components.DialogContent&&components.DialogTitle){
   return h(components.Dialog,{open:true,onOpenChange:open=>{if(!open)onCloseRequest();}},h(components.DialogContent,{className:'hb-dialog',onEscapeKeyDown:event=>{event.preventDefault();onCloseRequest();},onPointerDownOutside:event=>{event.preventDefault();onCloseRequest();}},h(components.DialogTitle,null,title),components.DialogDescription?h(components.DialogDescription,null,description||'Manage this saved item.'):null,children));
  }
  return h('dialog',{ref,className:'hb-dialog',role:'dialog','aria-labelledby':titleId,onCancel:event=>{event.preventDefault();onCloseRequest();},onClick:event=>{if(event.target===event.currentTarget)onCloseRequest();}},h('div',{className:'hb-dialog-body'},h('h2',{id:titleId},title),description&&h('p',{className:'hb-muted'},description),children));
 };
}
