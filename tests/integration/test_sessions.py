from datetime import timedelta
from sqlalchemy import delete
from app import clock
from app.models.attendance_sessions import AttendanceSession,SessionMember
from tests.integration.test_auth import accounts,sign_in


def test_session_permissions_public_information_and_close(client,accounts):
    now=clock.utc_now();created=[]
    data={'title':'云计算课程','class_id':accounts['class_id'],'starts_at':(now-timedelta(minutes=1)).isoformat(),'ends_at':(now+timedelta(minutes=5)).isoformat()}
    try:
        assert client.post('/api/sessions',json=data).status_code==401
        headers=sign_in(client,accounts,'student')
        assert client.post('/api/sessions',json=data,headers=headers).status_code==403
        headers=sign_in(client,accounts,'admin')
        assert client.post('/api/sessions',json={**data,'starts_at':'2026-09-28T10:00:00'},headers=headers).status_code==422
        result=client.post('/api/sessions',json=data,headers=headers)
        assert result.status_code==201,result.text
        row=result.json();created.append(row['id']);assert row['expected_count']==1
        client.cookies.clear()
        public=client.get('/api/sessions/'+row['public_code'])
        assert public.status_code==200 and public.json()['status']=='OPEN'
        assert set(public.json())=={'title','class_name','starts_at','ends_at','effective_end','status','server_time'}
        assert client.get('/api/sessions').status_code==401
        headers=sign_in(client,accounts,'admin')
        first=client.post(f"/api/sessions/{row['id']}/close",headers=headers)
        second=client.post(f"/api/sessions/{row['id']}/close",headers=headers)
        assert first.status_code==200 and first.json()['closed_at']==second.json()['closed_at']
        assert client.get('/api/sessions/'+row['public_code']).json()['status']=='CLOSED'
    finally:
        with accounts['factory'].begin() as s:
            s.execute(delete(SessionMember).where(SessionMember.session_id.in_(created)))
            s.execute(delete(AttendanceSession).where(AttendanceSession.id.in_(created)))
