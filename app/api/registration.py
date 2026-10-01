import hmac
from fastapi import APIRouter,Request,Depends
from pydantic import BaseModel,ConfigDict,Field,ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.models import User,ClassRoom
from app.models.tasks import RecognitionTask
from app.errors import AppError
from app.schemas.accounts import Name,StudentNumber,Password
from app.security import check_origin,rate_limit,db_session,hash_password,token_hash
from app.services.forms import photo_form
from app.services.uploads import receive_photo,stored_path
from app.services.tasks import validate_key,request_digest,find_replay,new_task,accepted,dispatch

from app.services.capacity import reserve,release

router=APIRouter(prefix='/api/auth',tags=['registration'])


class RegistrationInput(BaseModel):
    model_config=ConfigDict(extra='forbid',hide_input_in_errors=True)
    name:Name
    student_no:StudentNumber
    password:Password
    class_id:int=Field(gt=0)


@router.post('/register',status_code=202)
async def register(request:Request,session=Depends(db_session)):
    check_origin(request);rate_limit(request,'registration',10)
    key=validate_key(request.headers.get('idempotency-key'))
    form=await photo_form(request,{'name','student_no','password','class_id','photo'})
    uploaded=None;retained=False;reservation=None
    settings=request.app.state.settings
    try:
        try: data=RegistrationInput.model_validate({k:v for k,v in form.items() if k!='photo'})
        except ValidationError: raise AppError('INVALID_REQUEST','请检查姓名、学号、班级和密码长度',422) from None
        uploaded=await receive_photo(form['photo'],settings.storage_dir)
        digest=request_digest(settings.app_secret,{**data.model_dump(),'photo':uploaded.digest})
        existing=find_replay(session,'register',key,digest)
        if existing: return accepted(existing,settings.app_secret,key)
        classroom=session.get(ClassRoom,data.class_id)
        if not classroom or classroom.status!='ACTIVE': raise AppError('INVALID_CLASS','班级不可用',400)
        if session.scalar(select(User.id).where(User.student_no==data.student_no)):
            raise AppError('ACCOUNT_EXISTS','该学号已注册；录入失败请使用原任务凭证重试',409)
        password_hash=await run_in_threadpool(hash_password,data.password)
        user=User(student_no=data.student_no,name=data.name,class_id=data.class_id,password_hash=password_hash,status='PENDING')
        session.add(user);session.flush()
        task=new_task(settings.app_secret,'register',key,digest,'ENROLL',user.id,uploaded.path)
        reserve(request.app.state.redis,task.id,task.expires_at);reservation=task.id
        # Preserve the photo once COMMIT starts: a lost acknowledgement is not a rollback.
        session.add(task);session.flush();retained=True;session.commit()
        dispatch(task.id)
        return accepted(task,settings.app_secret,key)
    except IntegrityError:
        session.rollback()
        existing=find_replay(session,'register',key,digest)
        if existing: return accepted(existing,settings.app_secret,key)
        raise AppError('ACCOUNT_EXISTS','该学号已注册或请求正在处理',409) from None
    finally:
        await form.close()
        if uploaded and not retained: stored_path(settings.storage_dir,uploaded.path).unlink(missing_ok=True)
        if reservation and not retained:release(request.app.state.redis,reservation)


@router.post('/register/{task_id}/retry',status_code=202)
async def retry_registration(task_id:str,request:Request,session=Depends(db_session)):
    check_origin(request);rate_limit(request,'registration',10)
    key=validate_key(request.headers.get('idempotency-key'))
    old=session.get(RecognitionTask,task_id)
    if not old or old.type!='ENROLL' or not hmac.compare_digest(old.token_hash,token_hash(request.headers.get('x-task-token',''))):
        raise AppError('NOT_FOUND','原注册任务凭证无效',404)
    form=await photo_form(request,{'photo'});uploaded=None;retained=False;reservation=None
    settings=request.app.state.settings
    try:
        uploaded=await receive_photo(form['photo'],settings.storage_dir)
        scope='register-retry:'+task_id
        digest=request_digest(settings.app_secret,{'photo':uploaded.digest})
        replay=find_replay(session,scope,key,digest)
        if replay: return accepted(replay,settings.app_secret,key)
        # End the initial read snapshot before obtaining current locked state.
        session.rollback()
        old=session.scalar(select(RecognitionTask).where(RecognitionTask.id==task_id).with_for_update())
        user=session.scalar(select(User).where(User.id==old.owner_user_id).with_for_update())
        replay=find_replay(session,scope,key,digest)
        if replay: return accepted(replay,settings.app_secret,key)
        active=session.scalar(select(RecognitionTask.id).where(RecognitionTask.owner_user_id==user.id,RecognitionTask.status.in_(['PENDING','RUNNING'])))
        if old.status not in {'REJECTED','FAILED'} or user.status!='PENDING' or active:
            raise AppError('RETRY_UNAVAILABLE','当前注册不能重试，请查看原任务结果',409)
        task=new_task(settings.app_secret,scope,key,digest,'ENROLL',user.id,uploaded.path)
        reserve(request.app.state.redis,task.id,task.expires_at);reservation=task.id
        # Preserve the photo once COMMIT starts: a lost acknowledgement is not a rollback.
        session.add(task);session.flush();retained=True;session.commit();dispatch(task.id)
        return accepted(task,settings.app_secret,key)
    finally:
        await form.close()
        if uploaded and not retained: stored_path(settings.storage_dir,uploaded.path).unlink(missing_ok=True)
        if reservation and not retained:release(request.app.state.redis,reservation)
