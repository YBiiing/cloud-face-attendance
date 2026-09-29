"""Course demo business flow. Only the extractor is replaced in this process.

It proves API/database behavior, not recognition accuracy on real people.
"""
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4
from datetime import timedelta

import numpy as np
from PIL import Image
from sqlalchemy import select, delete

from app import clock
from app.face.types import FaceFeature
from app.jobs import worker
from app.models import User, ClassRoom, LoginSession, FaceSample, FaceLibraryState, RecognitionTask, AttendanceSession, SessionMember, AttendanceRecord
from app.services.uploads import stored_path
from tests.integration.test_auth import accounts, sign_in


def test_register_known_checkin_unknown_and_records(client, accounts, monkeypatch, settings):
    vector = np.zeros(512, dtype=np.float32); vector[0] = 1
    feature = FaceFeature(vector, 'course-flow-test', 100)
    extractor = SimpleNamespace(extract=lambda image: feature)
    monkeypatch.setattr(worker, 'get_engine', lambda: extractor)
    monkeypatch.setattr('app.api.registration.dispatch', lambda task_id: worker.process(task_id))
    monkeypatch.setattr('app.api.checkins.dispatch', lambda task_id: worker.process(task_id))
    factory = accounts['factory']; marker = uuid4().hex
    class_id = sid = owner = None
    photo = BytesIO(); Image.new('RGB', (640, 640), 'white').save(photo, format='PNG')
    files = {'photo': ('test.png', photo.getvalue(), 'image/png')}
    def result(task):
        return client.get(task['poll_url'], headers={'X-Task-Token': task['task_token']}).json()
    try:
        admin_headers = sign_in(client, accounts, 'admin')
        classroom = client.post('/api/classes', json={'name': '完整业务演示 '+marker}, headers=admin_headers)
        assert classroom.status_code == 201; class_id = classroom.json()['id']
        assert client.post('/api/auth/logout', headers=admin_headers).status_code == 204
        registration = client.post('/api/auth/register', data={'name': '流程测试人员', 'student_no': marker,
            'class_id': class_id, 'password': 'test-only-password'}, files=files, headers={'Idempotency-Key': str(uuid4())})
        assert registration.status_code == 202, registration.text
        assert result(registration.json())['result_code'] == 'ENROLLED'
        with factory() as db: owner = db.scalar(select(User.id).where(User.student_no == marker))
        admin_headers = sign_in(client, accounts, 'admin'); now = clock.utc_now()
        response = client.post('/api/sessions', json={'title': '完整演示课程', 'class_id': class_id,
            'starts_at': (now-timedelta(minutes=1)).isoformat(), 'ends_at': (now+timedelta(minutes=5)).isoformat()}, headers=admin_headers)
        assert response.status_code == 201, response.text
        row = response.json(); sid = row['id']; assert row['expected_count'] == 1
        assert client.post('/api/auth/logout', headers=admin_headers).status_code == 204
        assert client.get('/api/me').status_code == 401
        def upload():
            response = client.post('/api/checkins', data={'session_code': row['public_code']}, files=files, headers={'Idempotency-Key': str(uuid4())})
            assert response.status_code == 202, response.text
            return result(response.json())
        assert upload()['result_code'] == 'CHECKED_IN'
        assert upload()['result_code'] == 'ALREADY_CHECKED_IN'
        unknown = np.zeros(512, dtype=np.float32); unknown[1] = 1
        extractor.extract = lambda image: FaceFeature(unknown, feature.model_version, 100)
        rejected = upload()
        assert rejected['status'] == 'REJECTED' and rejected['result_code'] == 'UNKNOWN_PERSON'
        admin_headers = sign_in(client, accounts, 'admin')
        report = client.get('/api/records', params={'session_id': sid}).json()
        assert report['summary']['expected'] == report['summary']['attended'] == 1
        assert report['summary']['absent'] == 0 and report['summary']['pending_tasks'] == 0
        assert report['items'][0]['student_no'] == marker
        assert client.post(f'/api/sessions/{sid}/close', headers=admin_headers).status_code == 200
        assert client.get('/api/records', params={'session_id': sid}).json()['summary']['finalized']
        assert client.post('/api/auth/logout', headers=admin_headers).status_code == 204
        login = client.post('/api/auth/login', json={'student_no': marker, 'password': 'test-only-password'})
        assert login.status_code == 200
        assert client.get('/api/records').json()['total'] == 1
    finally:
        with factory.begin() as db:
            if owner is None: owner = db.scalar(select(User.id).where(User.student_no == marker))
            if sid:
                db.execute(delete(AttendanceRecord).where(AttendanceRecord.session_id == sid))
            conditions = []
            if owner: conditions.append(RecognitionTask.owner_user_id == owner)
            if sid: conditions.append(RecognitionTask.session_id == sid)
            from sqlalchemy import or_
            if conditions:
                for task in db.scalars(select(RecognitionTask).where(or_(*conditions))):
                    if task.image_path: stored_path(settings.storage_dir, task.image_path).unlink(missing_ok=True)
                db.execute(delete(RecognitionTask).where(or_(*conditions)))
            if sid:
                db.execute(delete(SessionMember).where(SessionMember.session_id == sid))
                db.execute(delete(AttendanceSession).where(AttendanceSession.id == sid))
            if owner:
                db.execute(delete(LoginSession).where(LoginSession.user_id == owner))
                db.execute(delete(FaceSample).where(FaceSample.user_id == owner))
                db.execute(delete(User).where(User.id == owner))
                db.get(FaceLibraryState, 1, with_for_update=True).version += 1
            if class_id: db.execute(delete(ClassRoom).where(ClassRoom.id == class_id))
