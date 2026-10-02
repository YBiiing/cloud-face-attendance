from datetime import timedelta
from uuid import uuid4
from sqlalchemy import delete
from app import clock
from app.models import AttendanceSession,SessionMember,AttendanceRecord,RecognitionTask
from app.services.tasks import new_task
from tests.integration.test_auth import accounts,sign_in


def test_student_discovers_only_own_roster_and_pending_sessions(client,settings,accounts):
    factory=accounts['factory'];now=clock.utc_now();ids=[];task_id=None
    try:
        with factory.begin() as db:
            for index in range(4):
                row=AttendanceSession(title='发现测试'+str(index),class_id=accounts['class_id'],created_by=accounts['ids'][0],
                    public_code=uuid4().hex,starts_at=now+timedelta(minutes=5) if index==1 else now-timedelta(minutes=5),
                    ends_at=now+timedelta(minutes=20),closed_at=now-timedelta(seconds=1) if index==2 else None)
                db.add(row);db.flush();ids.append(row.id)
                if index!=3:db.add(SessionMember(session_id=row.id,user_id=accounts['ids'][1]))
        assert client.get('/api/sessions/mine').status_code==401
        sign_in(client,accounts,'student')
        pending=client.get('/api/sessions/mine').json()
        assert pending['total']==2 and {r['id'] for r in pending['items']}==set(ids[:2])
        assert {r['status'] for r in pending['items']}=={'OPEN','SCHEDULED'}
        assert all(r['checkin_path'].startswith('/checkin.html?session_code=') for r in pending['items'])
        all_rows=client.get('/api/sessions/mine?view=all').json()
        assert all_rows['total']==3 and ids[3] not in {r['id'] for r in all_rows['items']}
        assert next(r for r in all_rows['items'] if r['id']==ids[2])['attendance_status']=='MISSED'
        with factory.begin() as db:
            task=new_task(settings.app_secret,'discovery-test',str(uuid4()),'a'*64,'CHECKIN');task.session_id=ids[0];task.status='SUCCEEDED'
            db.add(task);db.flush();task_id=task.id
            db.add(AttendanceRecord(session_id=ids[0],user_id=accounts['ids'][1],task_id=task.id,received_at=now,confirmed_at=now,score=.9,model_version='test'))
        assert client.get('/api/sessions/mine').json()['total']==1
        result=client.get('/api/sessions/mine?view=all&page_size=1').json()
        assert result['total']==3 and len(result['items'])==1
        all_rows=client.get('/api/sessions/mine?view=all').json()
        assert next(r for r in all_rows['items'] if r['id']==ids[0])['attendance_status']=='ATTENDED'
        assert client.get('/api/sessions').status_code==403
        assert client.get('/api/sessions/mine?view=invalid').status_code==422
        sign_in(client,accounts,'admin');assert client.get('/api/sessions/mine').status_code==403
    finally:
        with factory.begin() as db:
            db.execute(delete(AttendanceRecord).where(AttendanceRecord.session_id.in_(ids)))
            if task_id:db.execute(delete(RecognitionTask).where(RecognitionTask.id==task_id))
            db.execute(delete(SessionMember).where(SessionMember.session_id.in_(ids)))
            db.execute(delete(AttendanceSession).where(AttendanceSession.id.in_(ids)))
