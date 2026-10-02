from datetime import timezone
from typing import Annotated,Literal
from fastapi import APIRouter,Depends,Query
from pydantic import BaseModel,ConfigDict,Field,AwareDatetime,StringConstraints
from sqlalchemy import select,func
from app import clock
from app.models import ClassRoom,AttendanceRecord
from app.models.attendance_sessions import AttendanceSession,SessionMember
from app.security import db_session,admin_user,current_user
from app.errors import AppError
from app.services.attendance_sessions import create_session
from app.services.time_policy import effective_end,session_status

router=APIRouter(prefix='/api/sessions',tags=['sessions'])


class SessionInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title:Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=100)]
    class_id:int=Field(gt=0)
    starts_at:AwareDatetime
    ends_at:AwareDatetime


def management_data(row):
    result={key:getattr(row,key) for key in ['id','public_code','title','class_id','starts_at','ends_at','closed_at']}
    result.update(status=session_status(row,clock.utc_now()),checkin_path='/checkin.html?session_code='+row.public_code)
    return result


@router.post('',status_code=201)
def create(data:SessionInput,actor=Depends(admin_user),session=Depends(db_session)):
    row,count=create_session(session,actor.id,data.title,data.class_id,data.starts_at.astimezone(timezone.utc),data.ends_at.astimezone(timezone.utc))
    session.commit();return {**management_data(row),'expected_count':count}


@router.get('')
def list_sessions(class_id:int|None=Query(None,gt=0),page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),actor=Depends(admin_user),session=Depends(db_session)):
    query=select(AttendanceSession)
    if class_id:query=query.where(AttendanceSession.class_id==class_id)
    total=session.scalar(select(func.count()).select_from(query.subquery()))
    rows=session.scalars(query.order_by(AttendanceSession.id.desc()).offset((page-1)*page_size).limit(page_size)).all()
    items=[]
    for row in rows:
        count=session.scalar(select(func.count()).select_from(SessionMember).where(SessionMember.session_id==row.id))
        items.append({**management_data(row),'expected_count':count})
    return {'items':items,'total':total,'page':page,'page_size':page_size}


@router.get('/mine')
def my_sessions(view:Literal['pending','all']='pending',page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),actor=Depends(current_user),session=Depends(db_session)):
    if actor.role!='STUDENT':raise AppError('FORBIDDEN','此页面仅供学生查看自己的签到场次',403)
    now=clock.utc_now()
    query=(select(AttendanceSession,ClassRoom.name,AttendanceRecord.id)
        .join(SessionMember,SessionMember.session_id==AttendanceSession.id)
        .join(ClassRoom,ClassRoom.id==AttendanceSession.class_id)
        .outerjoin(AttendanceRecord,(AttendanceRecord.session_id==AttendanceSession.id)&(AttendanceRecord.user_id==actor.id))
        .where(SessionMember.user_id==actor.id))
    if view=='pending':
        query=query.where(AttendanceRecord.id.is_(None),AttendanceSession.ends_at>now,
                          (AttendanceSession.closed_at.is_(None))|(AttendanceSession.closed_at>now))
    total=session.scalar(select(func.count()).select_from(query.subquery()))
    rows=session.execute(query.order_by(AttendanceSession.starts_at.desc(),AttendanceSession.id.desc())
                         .offset((page-1)*page_size).limit(page_size)).all()
    items=[]
    for row,class_name,record_id in rows:
        status=session_status(row,now)
        items.append({**management_data(row),'class_name':class_name,'effective_end':effective_end(row),
                      'attendance_status':'ATTENDED' if record_id is not None else ('MISSED' if status=='CLOSED' else 'PENDING')})
    return {'items':items,'total':total,'page':page,'page_size':page_size,'server_time':now}


@router.get('/{code}')
def public_session(code:str,session=Depends(db_session)):
    if len(code)>64:raise AppError('NOT_FOUND','签到场次不存在',404)
    row=session.scalar(select(AttendanceSession).where(AttendanceSession.public_code==code))
    if not row:raise AppError('NOT_FOUND','签到场次不存在',404)
    classroom=session.get(ClassRoom,row.class_id);now=clock.utc_now()
    return {'title':row.title,'class_name':classroom.name,'starts_at':row.starts_at,'ends_at':row.ends_at,'effective_end':effective_end(row),'status':session_status(row,now),'server_time':now}


@router.post('/{session_id}/close')
def close(session_id:int,actor=Depends(admin_user),session=Depends(db_session)):
    row=session.scalar(select(AttendanceSession).where(AttendanceSession.id==session_id).with_for_update())
    if not row:raise AppError('NOT_FOUND','签到场次不存在',404)
    if row.closed_at is None:row.closed_at=clock.utc_now()
    session.commit();return management_data(row)
