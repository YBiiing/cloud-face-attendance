import {api,showMessage,requestKey,previewPhoto} from './api.js';
import {pollTask,resultMessages} from './tasks.js';
const form=document.querySelector('#register-form'),message=document.querySelector('#message'),button=document.querySelector('#submit');
const controller=new AbortController();window.addEventListener('pagehide',()=>controller.abort());
window.addEventListener('pageshow',event=>{if(event.persisted)location.reload();});
let key=requestKey(),retryTask=null,pendingTask=null,busy=false;
const resume=document.createElement('button');resume.type='button';resume.textContent='继续查询注册结果';resume.hidden=true;message.after(resume);
function lock(value){
  busy=value;
  for(const field of form.elements)field.disabled=value || (!!retryTask && ['name','student_no','class_id','password'].includes(field.name));
  resume.disabled=value;
}
form.addEventListener('input',()=>{key=requestKey();});
previewPhoto(form.elements.photo,document.querySelector('#preview'));
function handleError(error){
  if(controller.signal.aborted)return;
  if(error.status===404){
    pendingTask=null;retryTask=null;resume.hidden=true;key=requestKey();
    sessionStorage.removeItem('registration-task');button.textContent='注册并录入';
    showMessage(message,'保存的注册任务已失效，请重新填写；若学号已注册，请尝试登录或联系管理员处理录入。',true);
  }else{
    showMessage(message,error.code==='ACCOUNT_EXISTS'?'该学号已注册，请尝试登录；尚未完成录入且凭证丢失时，请联系管理员。':error.message||'网络异常，请保留页面并重试',true);
  }
}
async function loadClasses(){
  const select=form.elements.class_id;select.replaceChildren(new Option('请选择班级',''));
  let page=1;
  try {while(true){const data=await api(`/classes?page=${page}&page_size=100`);for(const c of data.items)select.add(new Option(c.name,c.id));if(page*100>=data.total)break;page++;}
    if(select.options.length===1)showMessage(message,'暂无班级，请先联系管理员创建班级。',true);
  }catch(error){showMessage(message,error.message,true);}
}
loadClasses();
async function follow(task){
  pendingTask=task;resume.hidden=false;
  sessionStorage.setItem('registration-task',JSON.stringify(task));
  const result=await pollTask(task,r=>showMessage(message,r.status==='PENDING'?'已接收，正在排队……':'正在处理照片……'),controller.signal);
  pendingTask=null;resume.hidden=true;
  showMessage(message,resultMessages[result.result_code] || '处理未完成，请稍后重试',result.status!=='SUCCEEDED');
  if(result.status==='SUCCEEDED'){sessionStorage.removeItem('registration-task');form.hidden=true;}
  else {retryTask=task;for(const name of ['name','student_no','class_id','password'])form.elements[name].disabled=true;button.textContent='重新上传照片';}
}
resume.onclick=async()=>{
  if(busy||!pendingTask)return;lock(true);
  try{await follow(pendingTask);}catch(error){handleError(error);}finally{lock(false);if(pendingTask)for(const field of form.elements)field.disabled=true;}
};
const saved=sessionStorage.getItem('registration-task');
if(saved){try{const task=JSON.parse(saved);if(!task.task_id||!task.task_token)throw new Error('保存的任务凭证无效');lock(true);await follow(task);}catch(error){if(!pendingTask)sessionStorage.removeItem('registration-task');handleError(error);}finally{lock(false);if(pendingTask)for(const field of form.elements)field.disabled=true;}}
form.addEventListener('submit',async event=>{
  event.preventDefault();if(busy||pendingTask)return;
  const photo=form.elements.photo.files[0],body=new FormData(form);lock(true);showMessage(message,'正在上传，请稍候……');
  try {
    if(!photo||photo.size>8*1024*1024)throw new Error('请选择不超过 8 MiB 的照片');
    const headers={'Idempotency-Key':key};let path='/auth/register',payload=body;
    if(retryTask){path+=`/${retryTask.task_id}/retry`;headers['X-Task-Token']=retryTask.task_token;payload=new FormData();payload.append('photo',photo);}
    const task=await api(path,{method:'POST',body:payload,headers,signal:controller.signal});await follow(task);
  }catch(error){handleError(error);}
  finally {lock(false);if(pendingTask)for(const field of form.elements)field.disabled=true;}
});
