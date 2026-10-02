import {session,protectedWrite,showMessage} from './api.js';
export async function workspace(role){
  let me;
  try{me=await session();}catch(error){if(error.status===401){location.replace('/login.html');return null;}throw error;}
  if(role&&me.user.role!==role){location.replace('/dashboard.html');return null;}
  const nav=document.querySelector('[data-workspace-nav]');
  if(nav){
    nav.replaceChildren();
    const links=me.user.role==='ADMIN'?[['工作台','/dashboard.html'],['已创建签到','/sessions.html'],['创建签到','/session-create.html'],['签到记录','/records.html']]:[['我的签到','/dashboard.html'],['签到记录','/records.html'],['我的照片','/faces.html']];
    for(const [label,url] of links){const a=document.createElement('a');a.textContent=label;a.href=url;if(location.pathname===url)a.setAttribute('aria-current','page');nav.append(a);}
    const button=document.createElement('button');button.type='button';button.className='quiet';button.textContent='退出登录';
    button.onclick=async()=>{button.disabled=true;try{await protectedWrite('/auth/logout',{method:'POST'});for(const key of Object.keys(sessionStorage)){if(key.startsWith('face-task:'))sessionStorage.removeItem(key);}location.replace('/login.html');}catch(error){const node=document.querySelector('#message');if(node)showMessage(node,error.message,true);button.disabled=false;}};
    nav.append(button);
  }
  return me;
}
