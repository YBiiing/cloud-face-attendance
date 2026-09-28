import hmac
from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy import select
from app import clock
from app.models import User, LoginSession
from app.models.tasks import RecognitionTask
from app.security import db_session, token_hash, COOKIE
from app.errors import AppError

router=APIRouter(prefix='/api/tasks',tags=['tasks'])


@router.get('/{task_id}')
def task_result(task_id:str, request:Request, response:Response, session=Depends(db_session)):
    task=session.get(RecognitionTask,task_id)
    supplied=request.headers.get('x-task-token','')
    allowed=task is not None and supplied and hmac.compare_digest(task.token_hash,token_hash(supplied))
    if task and not allowed and request.cookies.get(COOKIE):
        login=session.scalar(select(LoginSession).where(LoginSession.token_hash==token_hash(request.cookies[COOKIE]),LoginSession.expires_at>clock.utc_now()))
        user=session.get(User,login.user_id) if login else None
        allowed=user and user.status=='ACTIVE' and (user.role=='ADMIN' or (task.type!='CHECKIN' and task.owner_user_id==user.id))
    if not allowed: raise AppError('NOT_FOUND','任务不存在或凭证无效',404)
    response.headers['Cache-Control']='no-store'
    return {'task_id':task.id,'status':task.status,'result_code':task.result_code,
            'created_at':task.created_at,'finished_at':task.finished_at}
