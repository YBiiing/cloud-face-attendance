export class ApiError extends Error {
  constructor(message, status, code) { super(message); this.status=status; this.code=code; }
}
export async function api(path, options={}) {
  const headers=new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type','application/json');
  const controller=new AbortController(),abort=()=>controller.abort();
  if(options.signal?.aborted)abort();
  options.signal?.addEventListener('abort',abort,{once:true});
  const timer=setTimeout(abort,30000);
  try {
    const response=await fetch('/api'+path,{...options,headers,credentials:'same-origin',signal:controller.signal});
    const data=response.status===204 ? null : await response.json().catch(()=>null);
    if (!response.ok) throw new ApiError(data?.error?.message || '服务暂时不可用，请稍后重试',response.status,data?.error?.code);
    if(response.status!==204 && data===null)throw new ApiError('服务器返回格式异常，请重试',response.status);
    return data;
  }catch(error){
    if(error.name==='AbortError'&&!options.signal?.aborted)throw new ApiError('请求超时，请保留页面后重试',0,'NETWORK_TIMEOUT');
    throw error;
  }finally{clearTimeout(timer);options.signal?.removeEventListener('abort',abort);}
}
export async function session() { return await api('/me'); }
export async function protectedWrite(path,options={}) {
  const me=await session();
  return api(path,{...options,headers:{...options.headers,'X-CSRF-Token':me.csrf_token}});
}
export function showMessage(node,message,isError=false) { node.textContent=message; node.classList.toggle('error',isError); }
export function requestKey() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
  const hex=Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}
export function previewPhoto(input,image) {
  let previous=null;
  input.addEventListener('change',()=>{
    if(previous) URL.revokeObjectURL(previous);
    image.hidden=!input.files.length;
    if(input.files.length) { previous=URL.createObjectURL(input.files[0]);image.src=previous; }
  });
}
