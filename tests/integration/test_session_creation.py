from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select,delete,func
import pytest
from app import clock
from app.models import User,ClassRoom
from app.models.attendance_sessions import AttendanceSession,SessionMember
from app.services.attendance_sessions import create_session
from app.errors import AppError
from tests.integration.test_auth import accounts


def test_roster_snapshot_and_separate_sessions(accounts):
    factory=accounts['factory'];created=[];new_user=None
    start=clock.utc_now();end=start+timedelta(minutes=10)
    try:
        with factory.begin() as s:
            row,count=create_session(s,accounts['ids'][0],'第一场',accounts['class_id'],start,end)
            created.append(row.id);assert count==1
        with factory.begin() as s:
            user=User(student_no=uuid4().hex,name='后来注册',class_id=accounts['class_id'],password_hash='unused',status='ACTIVE')
            s.add(user);s.flush();new_user=user.id
        with factory.begin() as s:
            assert s.scalar(select(func.count()).select_from(SessionMember).where(SessionMember.session_id==created[0]))==1
            row,count=create_session(s,accounts['ids'][0],'第二场',accounts['class_id'],start,end)
            created.append(row.id);assert count==2
            assert s.get(AttendanceSession,created[0]).public_code!=row.public_code
    finally:
        with factory.begin() as s:
            s.execute(delete(SessionMember).where(SessionMember.session_id.in_(created)))
            s.execute(delete(AttendanceSession).where(AttendanceSession.id.in_(created)))
            if new_user:s.execute(delete(User).where(User.id==new_user))


def test_empty_class_and_invalid_window(accounts):
    factory=accounts['factory'];now=clock.utc_now()
    with factory() as s:
        empty=ClassRoom(name='空班级');s.add(empty);s.flush()
        with pytest.raises(AppError,match='EMPTY_ROSTER'):
            create_session(s,accounts['ids'][0],'空名单',empty.id,now,now+timedelta(minutes=1))
        with pytest.raises(AppError,match='INVALID_WINDOW'):
            create_session(s,accounts['ids'][0],'无效',accounts['class_id'],now,now)
        s.rollback()
