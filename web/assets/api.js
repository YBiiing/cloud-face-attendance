export class ApiError extends Error {
  constructor(message, status, code) { super(message); this.status=status; this.code=code; }
}
export async function api(path, options={}) {
  const headers=new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type','application/json');
  const response=await fetch('/api'+path,{...options,headers,credentials:'same-origin'});
  const data=response.status===204 ? null : await response.json();
  if (!response.ok) throw new ApiError(data?.error?.message || '请求失败，请稍后重试',response.status,data?.error?.code);
  return data;
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
