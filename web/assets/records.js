import {api,session,showMessage} from './api.js';
const select=document.querySelector('#session'),list=document.querySelector('#record-list'),summary=document.querySelector('#summary'),message=document.querySelector('#message');
let page=1,busy=false,total=0;
function clear(){list.replaceChildren();summary.hidden=true;summary.replaceChildren();document.querySelector('#pagination').hidden=true;}
async function load(){
  clear();
  const params=new URLSearchParams({page,page_size:20});if(select.value)params.set('session_id',select.value);
  const data=await api('/records?'+params);total=data.total;
  if(data.summary){
    const s=data.summary;summary.hidden=false;
    const counts=document.createElement('p');counts.textContent=`应到 ${s.expected} 人 · 已到 ${s.attended} 人 · ${s.finalized?'未到':'暂未到'} ${s.absent} 人`;
    const pending=document.createElement('p');pending.textContent=`处理中任务 ${s.pending_tasks} 个 · ${s.finalized?'本场结果已确定':'结果仍可能更新'}`;
    summary.append(counts,pending);
  }
  for(const item of data.items){
    const card=document.createElement('section'),title=document.createElement('h2'),person=document.createElement('p'),status=document.createElement('p');
    title.textContent=item.session_title||data.session_title;
    person.textContent=`${item.name}（${item.student_no}）`;
    status.textContent=item.attended?`已签到 · 接收时间 ${new Date(item.received_at).toLocaleString('zh-CN')}`:(data.summary?.finalized?'未签到':'暂未签到');
    card.append(title,person,status);list.append(card);
  }
  if(!data.items.length){const empty=document.createElement('p');empty.textContent='暂无记录';list.append(empty);}
  document.querySelector('#pagination').hidden=false;
  document.querySelector('#page-info').textContent=`第 ${page} 页，共 ${total} 条`;
  document.querySelector('#previous').disabled=page===1;
  document.querySelector('#next').disabled=page*20>=total;
}
async function action(fn){
  if(busy)return;busy=true;select.disabled=true;document.querySelector('#refresh').disabled=true;
  try{showMessage(message,'');await fn();}
  catch(error){clear();showMessage(message,error.status===401?'请先登录后查看签到记录':error.message,true);if(error.status===401){document.querySelector('#controls').hidden=true;document.querySelector('#access-hint').textContent='登录后可查看有权限的记录';}}
  finally{busy=false;select.disabled=false;document.querySelector('#refresh').disabled=false;}
}
async function initialize(){
  clear();const me=await session();
  document.querySelector('#access-hint').textContent=me.user.role==='ADMIN'?'选择场次查看全班名单与统计；全部记录显示已签到人员。':'仅显示本人的成功签到记录。';
  const current=select.value||new URLSearchParams(location.search).get('session_id')||'';
  select.replaceChildren(new Option('全部成功签到记录',''));
  let n=1;
  while(true){const result=await api(`/records/sessions?page=${n}&page_size=100`);for(const row of result.items)select.add(new Option(`${row.title} · ${new Date(row.starts_at).toLocaleString('zh-CN')}`,row.id));if(n*100>=result.total)break;n++;}
  select.value=current;if(select.selectedIndex<0)select.value='';
  document.querySelector('#controls').hidden=false;await load();
}
select.onchange=()=>action(async()=>{page=1;await load();});
document.querySelector('#refresh').onclick=()=>action(load);
document.querySelector('#previous').onclick=()=>action(async()=>{page=Math.max(1,page-1);await load();});
document.querySelector('#next').onclick=()=>action(async()=>{page++;await load();});
window.addEventListener('pageshow',event=>{if(event.persisted)action(initialize);});
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')action(initialize);});
await action(initialize);
