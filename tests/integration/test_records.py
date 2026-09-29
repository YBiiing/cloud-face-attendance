from sqlalchemy import select
from uuid import uuid4
from app import clock
from app.models import User, SessionMember, FaceLibraryState, AttendanceSession, RecognitionTask
from app.services.attendance import finish_checkin
from app.face.matcher import Match
from tests.integration.test_auth import accounts, sign_in
from tests.integration.test_attendance import attendance, running_task


def test_records_privacy_pagination_and_pending_summary(client, attendance, settings):
    factory = attendance['factory']; sid = attendance['sid']
    with factory.begin() as db:
        user = User(student_no=uuid4().hex, name='第二位测试学生', class_id=attendance['class_id'], password_hash='unused', status='ACTIVE')
        db.add(user); db.flush(); attendance['ids'].append(user.id)
        db.add(SessionMember(session_id=sid, user_id=user.id))
        version = db.get(FaceLibraryState, 1).version
    task = running_task(factory, settings, sid)
    finish_checkin(factory, *task, version, Match(attendance['ids'][1], .9), None, 'test')
    pending = running_task(factory, settings, sid)
    with factory.begin() as db: db.get(AttendanceSession, sid).closed_at = clock.utc_now()
    assert client.get('/api/records').status_code == 401
    assert client.get('/api/records/sessions').status_code == 401
    headers = sign_in(client, attendance, 'student')
    personal = client.get('/api/records', params={'session_id': sid, 'user_id': attendance['ids'][0]})
    assert personal.status_code == 200 and personal.headers['cache-control'] == 'no-store'
    assert personal.json()['total'] == 1 and personal.json()['summary'] is None
    assert personal.json()['items'][0]['student_no'] == attendance['student']
    assert client.get('/api/records', params={'session_id': 2147483647}).json()['items'] == []
    choices = client.get('/api/records/sessions').json()
    assert choices['total'] == 1 and choices['items'][0]['id'] == sid
    client.post('/api/auth/logout', headers=headers)
    headers = sign_in(client, attendance, 'admin')
    result = client.get('/api/records', params={'session_id': sid, 'page_size': 1}).json()
    assert result['total'] == 2 and len(result['items']) == 1
    assert result['summary'] == {'expected': 2, 'attended': 1, 'absent': 1, 'pending_tasks': 1, 'finalized': False}
    next_page = client.get('/api/records', params={'session_id': sid, 'page_size': 1, 'page': 2}).json()
    assert next_page['items'][0]['user_id'] != result['items'][0]['user_id']
    assert next_page['summary'] == result['summary']
    assert client.get('/api/records', params={'session_id': sid, 'page_size': 1, 'page': 3}).json()['items'] == []
    with factory.begin() as db:
        row = db.get(RecognitionTask, pending[0]); row.status = 'REJECTED'; row.result_code = 'UNKNOWN_PERSON'; row.finished_at = clock.utc_now()
    summary = client.get('/api/records', params={'session_id': sid}).json()['summary']
    assert summary['finalized'] and summary['pending_tasks'] == 0
    assert summary['expected'] == summary['attended']+summary['absent']
    assert client.get('/api/records', params={'session_id': 2147483647}).status_code == 404
    client.post('/api/auth/logout', headers=headers)
    assert client.get('/api/records', params={'session_id': sid}).status_code == 401
