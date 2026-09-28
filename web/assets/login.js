import {api,session,protectedWrite,showMessage} from './api.js';
const form=document.querySelector('#login-form'),message=document.querySelector('#message'),account=document.querySelector('#account');
function display(me) { form.hidden=true;account.hidden=false;document.querySelector('#account-name').textContent=`${me.user.name}，已登录`; }
session().then(display).catch(error=>{if(error.status!==401) showMessage(message,error.message,true);});
form.addEventListener('submit',async event=>{
  event.preventDefault();const button=form.querySelector('button');button.disabled=true;
  try { const me=await api('/auth/login',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(form)))});form.reset();display(me);showMessage(message,'登录成功'); }
  catch(error){showMessage(message,error.message,true);} finally {button.disabled=false;}
});
document.querySelector('#logout').addEventListener('click',async()=>{
  try {await protectedWrite('/auth/logout',{method:'POST'});account.hidden=true;form.hidden=false;showMessage(message,'已退出登录');}
  catch(error){showMessage(message,error.message,true);}
});
