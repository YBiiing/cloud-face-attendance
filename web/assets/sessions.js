import {api,session,protectedWrite,showMessage} from './api.js';
const message=document.querySelector('#message'),form=document.querySelector('#session-form'),classForm=document.querySelector('#class-form'),list=document.querySelector('#session-list');
let page=1;
const labels={SCHEDULED:'未开始',OPEN:'进行中',CLOSED:'已结束'};
async function loadClasses(){form.elements.class_id.replaceChildren(new Option('请选择班级',''));let p=1;while(true){const data=await api(`/classes?page=${p}&page_size=100`);for(const c of data.items)form.elements.class_id.add(new Option(c.name,c.id));if(p*100>=data.total)break;p++;}}
async function load(){
  const data=await api(`/sessions?page=${page}&page_size=10`);list.replaceChildren();
  for(const row of data.items){
    const card=document.createElement('section'),title=document.createElement('h3'),info=document.createElement('p'),link=document.createElement('a'),close=document.createElement('button');
    title.textContent=row.title;info.textContent=`${labels[row.status]} · 应到 ${row.expected_count} 人 · ${new Date(row.starts_at).toLocaleString('zh-CN')} 至 ${new Date(row.ends_at).toLocaleString('zh-CN')}`;
    link.href=row.checkin_path;link.textContent='打开签到入口';
    const address=document.createElement('input');address.readOnly=true;address.value=new URL(row.checkin_path,location.origin).href;address.setAttribute('aria-label','签到链接，选中后可复制');address.onclick=()=>address.select();
    close.textContent='提前结束';close.disabled=row.status==='CLOSED';close.onclick=async()=>{if(!confirm('立即结束本场签到？新的上传将被拒绝。'))return;try{await protectedWrite(`/sessions/${row.id}/close`,{method:'POST'});await load();}catch(error){showMessage(message,error.message,true);}};
    const records=document.createElement('a');records.href='/records.html?session_id='+row.id;records.textContent='查看名单与签到记录';
    card.append(title,info,link,address,records,close);list.append(card);
  }
  document.querySelector('#page-info').textContent=`第 ${page} 页，共 ${data.total} 场`;document.querySelector('#previous').disabled=page===1;document.querySelector('#next').disabled=page*10>=data.total;
}
async function navigate(delta){page+=delta;try{await load();}catch(error){showMessage(message,error.message,true);}}
document.querySelector('#previous').onclick=()=>navigate(-1);document.querySelector('#next').onclick=()=>navigate(1);
try{const me=await session();if(me.user.role!=='ADMIN')throw new Error('仅管理员可管理课程签到');document.querySelector('#admin-area').hidden=false;await loadClasses();await load();}catch(error){showMessage(message,error.status===401?'请先登录管理员账号':error.message,true);}
classForm.onsubmit=async event=>{event.preventDefault();const button=classForm.querySelector('button');button.disabled=true;try{await protectedWrite('/classes',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(classForm)))});classForm.reset();await loadClasses();showMessage(message,'班级已创建');}catch(error){showMessage(message,error.message,true);}finally{button.disabled=false;}};
form.onsubmit=async event=>{event.preventDefault();const button=form.querySelector('button');button.disabled=true;try{const data=Object.fromEntries(new FormData(form));data.class_id=Number(data.class_id);data.starts_at=new Date(data.starts_at).toISOString();data.ends_at=new Date(data.ends_at).toISOString();await protectedWrite('/sessions',{method:'POST',body:JSON.stringify(data)});page=1;await load();showMessage(message,'签到场次已发布，可复制入口链接');}catch(error){showMessage(message,error.message,true);}finally{button.disabled=false;}};
