from fastapi import APIRouter,Request
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app import clock
from app.models.attendance_sessions import AttendanceSession
from app.security import check_origin,rate_limit
from app.errors import AppError
from app.services.forms import photo_form
from app.services.uploads import receive_photo,stored_path
from app.services.tasks import validate_key,request_digest,find_replay,new_task,accepted,dispatch
from app.services.time_policy import eligible_time,session_status
from app.services.capacity import reserve,release

router=APIRouter(prefix='/api/checkins',tags=['checkins'])


@router.post('',status_code=202)
async def submit(request:Request):
    check_origin(request)
    await run_in_threadpool(rate_limit,request,'checkin',30)
    key=validate_key(request.headers.get('idempotency-key'))
    form=await photo_form(request,{'session_code','photo'})
    try:
        code=form.get('session_code')
        if not isinstance(code,str) or not 1<=len(code)<=64:raise AppError('INVALID_REQUEST','场次码不合法',422)
        uploaded=await receive_photo(form['photo'],request.app.state.settings.storage_dir)
        received_at=clock.utc_now()
        return await run_in_threadpool(submit_transaction,request,code,uploaded,key,received_at)
    finally:
        await form.close()


def submit_transaction(request,code,uploaded,key,received_at):
    settings=request.app.state.settings;retained=False;reservation=None
    with request.app.state.sessions() as session:
        try:
            digest=request_digest(settings.app_secret,{'session_code':code,'photo':uploaded.digest})
            existing=find_replay(session,'checkin',key,digest)
            if existing:return accepted(existing,settings.app_secret,key)
            # Current locking read ensures an overlapping close is observed.
            row=session.scalar(select(AttendanceSession).where(AttendanceSession.public_code==code).with_for_update())
            if not row:raise AppError('NOT_FOUND','签到场次不存在',404)
            if not eligible_time(row,received_at):
                future=session_status(row,received_at)=='SCHEDULED'
                raise AppError('SESSION_NOT_STARTED' if future else 'SESSION_ENDED','签到尚未开始' if future else '本场次已结束',409)
            task=new_task(settings.app_secret,'checkin',key,digest,'CHECKIN',image_path=uploaded.path,received_at=received_at)
            task.session_id=row.id
            reserve(request.app.state.redis,task.id,task.expires_at);reservation=task.id
            # Preserve the photo once COMMIT starts: a lost acknowledgement is not a rollback.
            session.add(task);session.flush();retained=True;session.commit();dispatch(task.id)
            return accepted(task,settings.app_secret,key)
        except IntegrityError:
            session.rollback();existing=find_replay(session,'checkin',key,digest)
            if existing:return accepted(existing,settings.app_secret,key)
            raise AppError('CONFLICT','请求冲突，请稍后重试',409) from None
        finally:
            if uploaded and not retained:stored_path(settings.storage_dir,uploaded.path).unlink(missing_ok=True)
            if reservation and not retained:release(request.app.state.redis,reservation)
