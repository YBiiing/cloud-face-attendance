import {session} from './api.js';
try{await session();location.replace('/dashboard.html');}catch(error){document.querySelector('#guest-actions').hidden=false;document.querySelector('#service-status').textContent=error.status===401?'': '暂时无法检查登录状态，请稍后重试。';}
