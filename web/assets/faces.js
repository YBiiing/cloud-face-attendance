import {api,session,protectedWrite,showMessage,requestKey,previewPhoto} from './api.js';
import {pollTask,resultMessages} from './tasks.js';
const message=document.querySelector('#message'),form=document.querySelector('#face-form'),list=document.querySelector('#photo-list'),people=document.querySelector('#people');
const controller=new AbortController();window.addEventListener('pagehide',()=>controller.abort());
let owner=null,page=1,total=0,replaceId=null,key=requestKey(),busy=false;
previewPhoto(form.elements.photo,document.querySelector('#preview'));
form.addEventListener('input',()=>key=requestKey());
function cancelReplace(){replaceId=null;key=requestKey();document.querySelector('#upload-title').textContent='新增标准照';document.querySelector('#cancel-replace').hidden=true;}
document.querySelector('#cancel-replace').onclick=cancelReplace;
async function load(){
  const data=await api(`/faces?user_id=${owner}&page=${page}&page_size=10`);total=data.total;list.replaceChildren();
  for(const face of data.items){
    const card=document.createElement('section'),image=document.createElement('img');image.className='preview';image.alt='已录入标准照';image.src=face.image_url;card.append(image);
    const replace=document.createElement('button');replace.type='button';replace.textContent='替换';replace.onclick=()=>{if(busy)return;replaceId=face.id;key=requestKey();document.querySelector('#upload-title').textContent='替换标准照';document.querySelector('#cancel-replace').hidden=false;form.scrollIntoView({behavior:'smooth'});};
    const remove=document.createElement('button');remove.type='button';remove.textContent='删除';remove.onclick=async()=>{if(busy||!confirm('删除这张标准照？历史签到记录会保留。'))return;try{await protectedWrite(`/faces/${face.id}`,{method:'DELETE'});cancelReplace();await load();}catch(error){showMessage(message,error.message,true);}};
    card.append(replace,remove);list.append(card);
  }
  if(!data.items.length){const empty=document.createElement('p');empty.textContent='暂无有效标准照';list.append(empty);}
  document.querySelector('#page-info').textContent=`第 ${page} 页，共 ${total} 张`;
  document.querySelector('#previous').disabled=page===1;document.querySelector('#next').disabled=page*10>=total;
}
async function navigate(delta){if(busy)return;page+=delta;try{await load();}catch(error){showMessage(message,error.message,true);}}
document.querySelector('#previous').onclick=()=>navigate(-1);document.querySelector('#next').onclick=()=>navigate(1);
people.onchange=async()=>{if(busy)return;owner=Number(people.value);page=1;cancelReplace();await load();};
try{
  const me=await session();owner=me.user.id;
  if(me.user.role==='ADMIN'){
    document.querySelector('#people-label').hidden=false;let p=1;
    while(true){const data=await api(`/users?page=${p}&page_size=100`);for(const user of data.items){if(user.status==='ACTIVE')people.add(new Option(`${user.name}（${user.student_no}）`,user.id));}if(p*100>=data.total)break;p++;}
    people.value=String(owner);if(!people.value&&people.options.length)owner=Number(people.options[0].value);
  }
  await load();
}catch(error){form.hidden=true;showMessage(message,error.status===401?'请先登录后管理照片':error.message,true);}
form.addEventListener('submit',async event=>{
  event.preventDefault();if(busy)return;busy=true;people.disabled=true;const button=form.querySelector('button');button.disabled=true;
  try{
    const file=form.elements.photo.files[0];if(file.size>8*1024*1024)throw new Error('照片超过 8 MiB');
    const body=new FormData(form);body.append('user_id',owner);if(replaceId)body.append('replace_id',replaceId);
    const task=await protectedWrite('/faces',{method:'POST',body,headers:{'Idempotency-Key':key}});
    const result=await pollTask(task,r=>showMessage(message,r.status==='PENDING'?'等待处理……':'正在处理……'),controller.signal);
    showMessage(message,resultMessages[result.result_code]||'操作未完成',result.status!=='SUCCEEDED');
    if(result.status==='SUCCEEDED'){form.reset();document.querySelector('#preview').hidden=true;cancelReplace();await load();}
  }catch(error){showMessage(message,error.message,true);}finally{busy=false;people.disabled=false;button.disabled=false;}
});
