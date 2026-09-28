import {api} from './api.js';
const terminal=new Set(['SUCCEEDED','REJECTED','FAILED']);
export const resultMessages={
  ENROLLED:'注册成功，可以登录了',FACE_SAVED:'标准照已保存',CHECKED_IN:'签到成功',ALREADY_CHECKED_IN:'本场次已签到',
  NO_FACE:'未检测到人脸，请重新拍摄',MULTIPLE_FACES:'照片中有多张人脸，请只拍本人',LOW_QUALITY:'照片不够清晰或人脸太小，请重拍',
  UNKNOWN_PERSON:'未识别到已录入人员',AMBIGUOUS_PERSON:'身份无法明确，请重新拍摄',NOT_IN_ROSTER:'你不在本场次签到名单中',
  PROCESSING_FAILED:'处理失败，请稍后重试',TASK_TIMEOUT:'任务超时，请稍后重试',USER_UNAVAILABLE:'账户当前不可用',PHOTO_CHANGED:'原照片已变化，请刷新后重试'
};
export async function pollTask(task,onProgress,signal) {
  let failures=0;
  while(!signal.aborted) {
    try {
      const result=await api(`/tasks/${task.task_id}`,{headers:{'X-Task-Token':task.task_token},signal});
      failures=0;onProgress(result);
      if(terminal.has(result.status)) return result;
    } catch(error) {
      if(signal.aborted) throw error;
      if(error.status===404 || ++failures>=5) throw error;
    }
    await new Promise(resolve=>setTimeout(resolve, Math.min(1000*2**failures,8000)));
  }
  throw new DOMException('页面已离开','AbortError');
}
