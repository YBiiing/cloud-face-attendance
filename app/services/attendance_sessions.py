import secrets
from sqlalchemy import select
from app import clock
from app.models import ClassRoom,User
from app.models.attendance_sessions import AttendanceSession,SessionMember
from app.errors import AppError


def create_session(session,actor_id,title,class_id,starts_at,ends_at):
    if ends_at<=starts_at or ends_at<=clock.utc_now():
        raise AppError('INVALID_WINDOW','结束时间须晚于开始时间和当前时间',422)
    classroom=session.get(ClassRoom,class_id)
    if not classroom or classroom.status!='ACTIVE':raise AppError('INVALID_CLASS','班级不可用',400)
    users=session.scalars(select(User.id).where(User.class_id==class_id,User.role=='STUDENT',User.status=='ACTIVE')).all()
    if not users:raise AppError('EMPTY_ROSTER','请先完成该班人员注册录入',409)
    row=AttendanceSession(title=title,class_id=class_id,public_code=secrets.token_urlsafe(24),starts_at=starts_at,ends_at=ends_at,created_by=actor_id)
    session.add(row);session.flush()
    session.add_all([SessionMember(session_id=row.id,user_id=user_id) for user_id in users])
    return row,len(users)
