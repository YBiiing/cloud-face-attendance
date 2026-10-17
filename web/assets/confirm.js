let opened=false,sequence=0;

export function confirmAction({title,message,confirmText}){
  if(opened)return Promise.resolve(false);
  opened=true;
  return new Promise(resolve=>{
    const previous=document.activeElement,dialog=document.createElement('dialog');
    dialog.className='confirm-dialog';
    const heading=document.createElement('h2'),description=document.createElement('p');
    const id='confirm-'+(++sequence);heading.id=id;description.id=id+'-description';
    heading.textContent=title;description.textContent=message;
    dialog.setAttribute('aria-labelledby',heading.id);dialog.setAttribute('aria-describedby',description.id);
    const actions=document.createElement('div');actions.className='confirm-actions';
    const cancel=document.createElement('button'),confirm=document.createElement('button');
    cancel.type=confirm.type='button';cancel.textContent='取消';cancel.className='secondary';
    confirm.textContent=confirmText;confirm.className='danger';
    actions.append(cancel,confirm);dialog.append(heading,description,actions);document.body.append(dialog);
    let finished=false;
    function finish(accepted){
      if(finished)return;finished=true;
      window.removeEventListener('pagehide',leave);
      if(dialog.open)dialog.close();dialog.remove();opened=false;
      if(previous?.isConnected)previous.focus({preventScroll:true});
      resolve(accepted);
    }
    const leave=()=>finish(false);window.addEventListener('pagehide',leave);
    cancel.onclick=()=>finish(false);confirm.onclick=()=>finish(true);
    dialog.addEventListener('cancel',event=>{event.preventDefault();finish(false);});
    dialog.addEventListener('close',()=>finish(false));
    dialog.showModal();cancel.focus();
  });
}
