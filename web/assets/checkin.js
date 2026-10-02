import {api,showMessage,requestKey,previewPhoto} from './api.js';
import {pollTask,resultMessages} from './tasks.js';

const code=new URLSearchParams(location.search).get('session_code');
const form=document.querySelector('#checkin-form'),message=document.querySelector('#message'),resume=document.querySelector('#resume');
const controller=new AbortController(),storageKey='checkin-task:'+code;
let row=null,key=requestKey(),busy=false,pending=null,offset=0;
previewPhoto(form.elements.photo,document.querySelector('#preview'));
form.addEventListener('input',()=>{key=requestKey();if(!pending)sessionStorage.removeItem(storageKey);});
function update(){
  const now=Date.now()+offset;
  const open=row && row.status!=='CLOSED' && now>=Date.parse(row.starts_at) && now<Date.parse(row.effective_end);
  form.hidden=!row;
  for(const field of form.elements)field.disabled=busy||!!pending||!open;
  resume.disabled=busy;document.querySelector('#refresh').disabled=busy;
  if(row){
    const seconds=Math.max(0,Math.ceil((Date.parse(row.effective_end)-now)/1000));
    document.querySelector('#countdown').textContent=open?`预计剩余 ${Math.floor(seconds/60)} 分 ${seconds%60} 秒（以服务器接收时间为准）`:
      (now<Date.parse(row.starts_at)&&row.status!=='CLOSED'?'签到尚未开始，可稍后刷新':'本场次已结束，已上传任务仍可查询结果');
  }
}
async function load(){
  if(!code)throw new Error('请使用老师提供的课程签到链接');
  row=await api('/sessions/'+encodeURIComponent(code),{signal:controller.signal});
  offset=Date.parse(row.server_time)-Date.now();
  document.querySelector('#title').textContent=row.title;
  document.querySelector('#details').textContent=`${row.class_name} · ${{SCHEDULED:'未开始',OPEN:'进行中',CLOSED:'已结束'}[row.status]} · ${new Date(row.starts_at).toLocaleString('zh-CN')} 至 ${new Date(row.effective_end).toLocaleString('zh-CN')}`;
  update();
}
async function follow(task){
  pending=task;sessionStorage.setItem(storageKey,JSON.stringify(task));resume.hidden=false;update();
  let result;
  try{
    result=await pollTask(task,r=>showMessage(message,r.status==='PENDING'?'已收到照片，正在排队……':'正在识别人脸并核对名单……'),controller.signal);
  }catch(error){
    if(error.status===404){
      pending=null;resume.hidden=true;sessionStorage.removeItem(storageKey);key=requestKey();update();
      throw new Error('保存的签到任务已失效，请重新上传；是否签到成功可登录后查看记录。');
    }
    throw error;
  }
  pending=null;resume.hidden=true;
  showMessage(message,resultMessages[result.result_code]||'处理未完成，请稍后重试',result.status!=='SUCCEEDED');
  key=requestKey();update();
}
async function run(action){
  if(busy)return;busy=true;update();
  try{await action();}catch(error){if(!controller.signal.aborted)showMessage(message,error.message||'网络异常，请保留页面后重试',true);}
  finally{busy=false;update();}
}
document.querySelector('#refresh').onclick=()=>run(load);
resume.onclick=()=>run(()=>follow(pending));
form.onsubmit=event=>{
  event.preventDefault();if(busy||pending)return;
  const file=form.elements.photo.files[0];
  run(async()=>{
    if(!file||file.size>8*1024*1024)throw new Error('请选择不超过 8 MiB 的照片');
    const body=new FormData();body.append('session_code',code);body.append('photo',file);
    showMessage(message,'正在上传照片……');
    const task=await api('/checkins',{method:'POST',body,headers:{'Idempotency-Key':key},signal:controller.signal});
    await follow(task);
  });
};
const timer=setInterval(update,1000);
window.addEventListener('pagehide',()=>{controller.abort();clearInterval(timer);});
window.addEventListener('pageshow',event=>{if(event.persisted)location.reload();});
await run(async()=>{
  await load();
  const saved=sessionStorage.getItem(storageKey);
  if(saved){
    let task;
    try{task=JSON.parse(saved);if(!task.task_id||!task.task_token)throw new Error();}
    catch{sessionStorage.removeItem(storageKey);throw new Error('本页任务凭证无效，请重新上传');}
    await follow(task);
  }
});
