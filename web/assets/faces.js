import {api,session,protectedWrite,showMessage,requestKey,previewPhoto} from './api.js';
import {pollTask,resultMessages} from './tasks.js';
const message=document.querySelector('#message'),form=document.querySelector('#face-form'),list=document.querySelector('#photo-list'),people=document.querySelector('#people');
const controller=new AbortController();window.addEventListener('pagehide',()=>controller.abort());
window.addEventListener('pageshow',event=>{if(event.persisted)location.reload();});
let owner=null,page=1,total=0,replaceId=null,key=requestKey(),busy=false,pending=null,storageKey=null;
const resume=document.createElement('button');resume.type='button';resume.textContent='继续查询照片处理结果';resume.hidden=true;message.after(resume);
function lock(value){
  busy=value;people.disabled=value||!!pending;resume.disabled=value;
  for(const field of form.elements)field.disabled=value||!!pending;
}
async function follow(task){
  pending=task;resume.hidden=false;
  sessionStorage.setItem(storageKey,JSON.stringify({task,owner,replaceId}));lock(busy);
  let result;
  try{
    result=await pollTask(task,r=>showMessage(message,r.status==='PENDING'?'等待处理……':'正在处理……'),controller.signal);
  }catch(error){
    if(error.status===404){
      pending=null;resume.hidden=true;sessionStorage.removeItem(storageKey);key=requestKey();
      throw new Error('保存的照片任务已失效，请刷新照片列表确认结果后再上传。');
    }
    throw error;
  }
  pending=null;resume.hidden=true;sessionStorage.removeItem(storageKey);
  // Only a known terminal result allows a new processing attempt.
  key=requestKey();
  showMessage(message,resultMessages[result.result_code]||'操作未完成',result.status!=='SUCCEEDED');
  if(result.status==='SUCCEEDED'){form.reset();document.querySelector('#preview').hidden=true;cancelReplace();await load();}
}
resume.onclick=async()=>{
  if(busy||!pending)return;lock(true);
  try{await follow(pending);}catch(error){if(!controller.signal.aborted)showMessage(message,error.message,true);}finally{lock(false);}
};
previewPhoto(form.elements.photo,document.querySelector('#preview'));
form.addEventListener('input',()=>key=requestKey());
function cancelReplace(){replaceId=null;key=requestKey();document.querySelector('#upload-title').textContent='新增标准照';document.querySelector('#cancel-replace').hidden=true;}
document.querySelector('#cancel-replace').onclick=()=>{if(!busy&&!pending)cancelReplace();};
async function load(){
  const data=await api(`/faces?user_id=${owner}&page=${page}&page_size=10`);total=data.total;list.replaceChildren();
  for(const face of data.items){
    const card=document.createElement('section'),image=document.createElement('img');image.className='preview';image.alt='已录入标准照';image.src=face.image_url;card.append(image);
    const replace=document.createElement('button');replace.type='button';replace.textContent='替换';replace.onclick=()=>{if(busy||pending)return;replaceId=face.id;key=requestKey();document.querySelector('#upload-title').textContent='替换标准照';document.querySelector('#cancel-replace').hidden=false;form.scrollIntoView({behavior:'smooth'});};
    const remove=document.createElement('button');remove.type='button';remove.textContent='删除';remove.onclick=async()=>{if(busy||pending||!confirm('删除这张标准照？历史签到记录会保留。'))return;try{await protectedWrite(`/faces/${face.id}`,{method:'DELETE'});cancelReplace();await load();}catch(error){showMessage(message,error.message,true);}};
    card.append(replace,remove);list.append(card);
  }
  if(!data.items.length){const empty=document.createElement('p');empty.textContent='暂无有效标准照';list.append(empty);}
  document.querySelector('#page-info').textContent=`第 ${page} 页，共 ${total} 张`;
  document.querySelector('#previous').disabled=page===1;document.querySelector('#next').disabled=page*10>=total;
}
async function navigate(delta){if(busy||pending)return;page+=delta;try{await load();}catch(error){showMessage(message,error.message,true);}}
document.querySelector('#previous').onclick=()=>navigate(-1);document.querySelector('#next').onclick=()=>navigate(1);
people.onchange=async()=>{if(busy||pending)return;owner=Number(people.value);page=1;cancelReplace();try{await load();}catch(error){showMessage(message,error.message,true);}};
try{
  const me=await session();owner=me.user.id;storageKey='face-task:'+owner;
  if(me.user.role==='ADMIN'){
    document.querySelector('#people-label').hidden=false;let p=1;
    while(true){const data=await api(`/users?page=${p}&page_size=100`);for(const user of data.items){if(user.status==='ACTIVE')people.add(new Option(`${user.name}（${user.student_no}）`,user.id));}if(p*100>=data.total)break;p++;}
    people.value=String(owner);if(!people.value&&people.options.length)owner=Number(people.options[0].value);
  }
  await load();
  const saved=sessionStorage.getItem(storageKey);
  if(saved){
    try{
      const state=JSON.parse(saved);
      if(!state.task?.task_id||!state.task?.task_token||!Number.isInteger(state.owner)||state.owner<1||
        (me.user.role!=='ADMIN'&&state.owner!==me.user.id))throw new Error('保存的照片任务凭证无效，请确认照片列表后重新上传。');
      owner=state.owner;replaceId=state.replaceId;people.value=String(owner);
      if(replaceId){document.querySelector('#upload-title').textContent='替换标准照';document.querySelector('#cancel-replace').hidden=false;}
      lock(true);await load();await follow(state.task);
    }catch(error){if(!pending)sessionStorage.removeItem(storageKey);if(!controller.signal.aborted)showMessage(message,error.message,true);}
    finally{lock(false);}
  }
}catch(error){form.hidden=true;showMessage(message,error.status===401?'请先登录后管理照片':error.message,true);}
form.addEventListener('submit',async event=>{
  event.preventDefault();if(busy||pending)return;
  const body=new FormData(form),file=form.elements.photo.files[0];lock(true);
  try{
    if(!file||file.size>8*1024*1024)throw new Error('请选择不超过 8 MiB 的照片');
    body.append('user_id',owner);if(replaceId)body.append('replace_id',replaceId);
    const task=await protectedWrite('/faces',{method:'POST',body,headers:{'Idempotency-Key':key},signal:controller.signal});
    await follow(task);
  }catch(error){if(!controller.signal.aborted)showMessage(message,error.message,true);}finally{lock(false);}
});
