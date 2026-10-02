import {api,showMessage} from './api.js';
import {workspace} from './workspace.js';
const message=document.querySelector('#message'),list=document.querySelector('#session-list');let page=1,view='pending',busy=false;
async function load(){
  if(busy)return;busy=true;document.querySelector('#list-status').textContent='正在加载场次……';
  for(const id of ['pending','all','refresh','previous','next'])document.getElementById(id).disabled=true;
  try{
    const data=await api(`/sessions/mine?view=${view}&page=${page}&page_size=10`);list.replaceChildren();showMessage(message,'');
    for(const row of data.items){
      const card=document.createElement('section');card.className='session-card';
      const title=document.createElement('h2');title.textContent=row.title;
      const state=document.createElement('span');state.className='badge';state.textContent=row.attendance_status==='ATTENDED'?'已签到':row.status==='OPEN'?'待签到 · 进行中':row.status==='SCHEDULED'?'未开始':'已结束 · 未签到';
      const info=document.createElement('p');info.className='hint';info.textContent=`${row.class_name} · ${new Date(row.starts_at).toLocaleString('zh-CN')} 至 ${new Date(row.effective_end).toLocaleString('zh-CN')}`;
      card.append(state,title,info);
      if(row.status==='OPEN'&&row.attendance_status==='PENDING'){const link=document.createElement('a');link.className='button-link';link.href=row.checkin_path;link.textContent='去签到';card.append(link);}
      else{const note=document.createElement('p');note.textContent=row.attendance_status==='ATTENDED'?'本场签到已完成。':row.status==='SCHEDULED'?'到开始时间后，刷新列表即可签到。':'本场签到已结束。';card.append(note);}
      list.append(card);
    }
    document.querySelector('#list-status').textContent=data.total?'':view==='pending'?'暂无待签到场次。老师发布后可刷新查看；已完成的场次在“全部场次”中。':'暂无场次。新加入班级的学生会出现在之后创建的签到名单中。';
    document.querySelector('#page-info').textContent=`第 ${page} 页，共 ${data.total} 场`;
    document.querySelector('#previous').disabled=page===1;document.querySelector('#next').disabled=page*10>=data.total;
  }catch(error){list.replaceChildren();document.querySelector('#list-status').textContent='加载失败，请重试。';showMessage(message,error.message,true);if(error.status===401)location.replace('/login.html');}
  finally{busy=false;for(const id of ['pending','all','refresh'])document.getElementById(id).disabled=false;}
}
for(const value of ['pending','all'])document.getElementById(value).onclick=()=>{if(busy)return;view=value;page=1;for(const id of ['pending','all'])document.getElementById(id).setAttribute('aria-pressed',String(id===view));load();};
document.querySelector('#refresh').onclick=load;
document.querySelector('#previous').onclick=()=>{if(!busy){page--;load();}};document.querySelector('#next').onclick=()=>{if(!busy){page++;load();}};
try{const me=await workspace();if(me){document.querySelector('#welcome').textContent=`${me.user.name}，你好`;document.querySelector('#role-label').textContent=me.user.role==='ADMIN'?'老师工作台':'学生工作台';document.querySelector(me.user.role==='ADMIN'?'#teacher-area':'#student-area').hidden=false;if(me.user.role!=='ADMIN')await load();}}catch(error){showMessage(message,error.message,true);}
window.addEventListener('pageshow',event=>{if(event.persisted)location.reload();});
