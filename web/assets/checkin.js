import {api,showMessage} from './api.js';
const code=new URLSearchParams(location.search).get('session_code'),message=document.querySelector('#message');
try{
  if(!code)throw new Error('请使用管理员提供的课程签到链接');
  const row=await api('/sessions/'+encodeURIComponent(code));
  document.querySelector('#title').textContent=row.title;
  document.querySelector('#details').textContent=`${row.class_name} · ${{SCHEDULED:'未开始',OPEN:'进行中',CLOSED:'已结束'}[row.status]} · ${new Date(row.starts_at).toLocaleString('zh-CN')} 至 ${new Date(row.effective_end).toLocaleString('zh-CN')}`;
}catch(error){showMessage(message,error.message,true);document.querySelector('#details').textContent='无法读取场次';}
