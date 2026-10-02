import {session,protectedWrite,showMessage} from './api.js';
export async function workspace(role){
  let me;
  try{me=await session();}catch(error){if(error.status===401){location.replace('/login.html');return null;}throw error;}
  if(role&&me.user.role!==role){location.replace('/dashboard.html');return null;}
  const nav=document.querySelector('[data-workspace-nav]');
  if(nav){
    nav.replaceChildren();
    let header=document.querySelector('.workspace-header');
    if(!header){header=document.createElement('header');header.className='workspace-header';nav.before(header);}
    header.replaceChildren();
    const brand=document.createElement('a');brand.href='/dashboard.html';brand.className='brand';brand.textContent='课程签到';
    const roleLabel=document.createElement('span');roleLabel.className='role-label';roleLabel.textContent=me.user.role==='ADMIN'?'老师':'学生';header.append(brand,roleLabel);
    document.body.classList.add('has-workspace');
    nav.style.setProperty('--nav-items',me.user.role==='ADMIN'?4:3);
    const links=me.user.role==='ADMIN'?[['工作台','/dashboard.html'],['已创建签到','/sessions.html'],['创建签到','/session-create.html'],['签到记录','/records.html']]:[['我的签到','/dashboard.html'],['签到记录','/records.html'],['我的照片','/faces.html']];
    for(const [label,url] of links){const a=document.createElement('a');a.textContent=label;a.href=url;if(location.pathname===url)a.setAttribute('aria-current','page');nav.append(a);}
    const button=document.createElement('button');button.type='button';button.className='quiet';button.textContent='退出登录';
    button.onclick=async()=>{button.disabled=true;try{await protectedWrite('/auth/logout',{method:'POST'});for(const key of Object.keys(sessionStorage)){if(key.startsWith('face-task:'))sessionStorage.removeItem(key);}location.replace('/login.html');}catch(error){const node=document.querySelector('#message');if(node)showMessage(node,error.message,true);button.disabled=false;}};
    header.append(button);
  }
  return me;
}

// Keep fixed navigation away from form editing and the on-screen keyboard.
let pointerActive=false;
function updateEditing(){
  const field=document.activeElement,editing=!!field?.matches('input:not([type=checkbox]):not([type=file]),select,textarea');
  if(editing)document.body.classList.add('is-editing');
  else if(!pointerActive)document.body.classList.remove('is-editing');
}
document.addEventListener('pointerdown',()=>{pointerActive=true;},true);
for(const event of ['pointerup','pointercancel'])document.addEventListener(event,()=>setTimeout(()=>{pointerActive=false;updateEditing();},0),true);
document.addEventListener('focusin',updateEditing);
document.addEventListener('focusout',()=>setTimeout(updateEditing,0));
