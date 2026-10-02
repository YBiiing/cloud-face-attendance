import {api,protectedWrite,showMessage} from './api.js';
import {workspace} from './workspace.js';
const message=document.querySelector('#message'),list=document.querySelector('#session-list');let page=1,busy=false;
const labels={SCHEDULED:'未开始',OPEN:'进行中',CLOSED:'已结束'};
async function load(){
  if(busy)return;busy=true;for(const id of ['refresh','previous','next'])document.getElementById(id).disabled=true;
  try{
    const data=await api(`/sessions?page=${page}&page_size=10`);list.replaceChildren();
    for(const row of data.items){
      const card=document.createElement('section'),title=document.createElement('h2'),info=document.createElement('p'),badge=document.createElement('span'),close=document.createElement('button');
      card.className='session-card';title.textContent=row.title;badge.className='badge';badge.textContent=labels[row.status];
      info.textContent=`应到 ${row.expected_count} 人 · ${new Date(row.starts_at).toLocaleString('zh-CN')} 至 ${new Date(row.ends_at).toLocaleString('zh-CN')}`;
      close.textContent='提前结束';close.className='quiet';close.disabled=row.status==='CLOSED';
      close.onclick=async()=>{if(!confirm('立即结束本场签到？结束后学生不能继续提交。'))return;close.disabled=true;try{await protectedWrite(`/sessions/${row.id}/close`,{method:'POST'});await load();showMessage(message,'本场签到已结束');}catch(error){showMessage(message,error.message,true);close.disabled=false;}};
      const records=document.createElement('a');records.href='/records.html?session_id='+row.id;records.textContent='查看出勤名单';records.className='button-link';
      const actions=document.createElement('div');actions.className='toolbar';actions.append(records,close);card.append(badge,title,info,actions);list.append(card);
    }
    if(!data.items.length){const empty=document.createElement('section');empty.textContent='还没有创建签到。点击“创建签到”发布第一场课程签到。';list.append(empty);}
    document.querySelector('#page-info').textContent=`第 ${page} 页，共 ${data.total} 场`;document.querySelector('#previous').disabled=page===1;document.querySelector('#next').disabled=page*10>=data.total;
  }catch(error){showMessage(message,error.message,true);if(error.status===401)location.replace('/login.html');}
  finally{busy=false;document.querySelector('#refresh').disabled=false;}
}
document.querySelector('#previous').onclick=()=>{if(!busy){page--;load();}};document.querySelector('#next').onclick=()=>{if(!busy){page++;load();}};document.querySelector('#refresh').onclick=load;
try{if(await workspace('ADMIN')){document.querySelector('#admin-area').hidden=false;if(new URLSearchParams(location.search).has('created'))showMessage(message,'签到已发布，名单中的学生现在可以在自己的工作台查看。');await load();}}catch(error){showMessage(message,error.message,true);}
window.addEventListener('pageshow',event=>{if(event.persisted)location.reload();});
