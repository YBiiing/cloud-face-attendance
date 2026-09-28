import {api,showMessage,requestKey,previewPhoto} from './api.js';
import {pollTask,resultMessages} from './tasks.js';
const form=document.querySelector('#register-form'),message=document.querySelector('#message'),button=document.querySelector('#submit');
const controller=new AbortController();window.addEventListener('pagehide',()=>controller.abort());
let key=requestKey(),retryTask=null;
form.addEventListener('input',()=>{key=requestKey();});
previewPhoto(form.elements.photo,document.querySelector('#preview'));
async function loadClasses(){
  const select=form.elements.class_id;select.replaceChildren(new Option('请选择班级',''));
  let page=1;
  try {while(true){const data=await api(`/classes?page=${page}&page_size=100`);for(const c of data.items)select.add(new Option(c.name,c.id));if(page*100>=data.total)break;page++;}
    if(select.options.length===1)showMessage(message,'暂无班级，请先联系管理员创建班级。',true);
  }catch(error){showMessage(message,error.message,true);}
}
loadClasses();
async function follow(task){
  sessionStorage.setItem('registration-task',JSON.stringify(task));
  const result=await pollTask(task,r=>showMessage(message,r.status==='PENDING'?'已接收，正在排队……':'正在处理照片……'),controller.signal);
  showMessage(message,resultMessages[result.result_code] || '处理未完成，请稍后重试',result.status!=='SUCCEEDED');
  if(result.status==='SUCCEEDED'){sessionStorage.removeItem('registration-task');form.hidden=true;}
  else {retryTask=task;for(const name of ['name','student_no','class_id','password'])form.elements[name].disabled=true;button.textContent='重新上传照片';}
}
const saved=sessionStorage.getItem('registration-task');
if(saved){try{button.disabled=true;await follow(JSON.parse(saved));}catch(error){showMessage(message,error.message,true);}finally{button.disabled=false;}}
form.addEventListener('submit',async event=>{
  event.preventDefault();button.disabled=true;showMessage(message,'正在上传，请稍候……');
  try {
    if(form.elements.photo.files[0].size>8*1024*1024)throw new Error('照片超过 8 MiB，请压缩或重拍');
    const headers={'Idempotency-Key':key};let path='/auth/register';let body=new FormData(form);
    if(retryTask){path+=`/${retryTask.task_id}/retry`;headers['X-Task-Token']=retryTask.task_token;body=new FormData();body.append('photo',form.elements.photo.files[0]);}
    const task=await api(path,{method:'POST',body,headers,signal:controller.signal});await follow(task);
  }catch(error){if(!controller.signal.aborted)showMessage(message,error.message || '网络异常，请保留页面并重试',true);}
  finally {button.disabled=false;}
});
