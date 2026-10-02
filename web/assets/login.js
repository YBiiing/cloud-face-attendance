import {api,session,showMessage} from './api.js';
const form=document.querySelector('#login-form'),message=document.querySelector('#message');
session().then(()=>location.replace('/dashboard.html')).catch(error=>{if(error.status!==401)showMessage(message,error.message,true);});
form.addEventListener('submit',async event=>{
  event.preventDefault();const button=form.querySelector('button[type=submit]');button.disabled=true;
  try{await api('/auth/login',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(form)))});form.reset();location.replace('/dashboard.html');}
  catch(error){showMessage(message,error.message,true);}finally{button.disabled=false;}
});
document.querySelector('#show-password').onchange=event=>{form.elements.password.type=event.target.checked?'text':'password';};
