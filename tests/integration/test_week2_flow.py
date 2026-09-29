"""Positive business flow with an explicit test-only feature extractor.

Real MySQL, HTTP handlers, image decoding, worker, transactions and sessions;
does not establish accuracy on real people. Production has no fake-model mode.
"""
from io import BytesIO
from uuid import uuid4
from types import SimpleNamespace

import numpy as np
from PIL import Image
from sqlalchemy import select, delete, func

from app.models import User, FaceSample, FaceLibraryState, RecognitionTask, LoginSession
from app.face.types import FaceFeature
from app.jobs import worker
from app.api import registration, faces
from app.services.uploads import stored_path
from tests.integration.test_auth import accounts
from scripts.week2_snapshot import snapshot


def test_register_login_replace_replay_logout(client, settings, accounts, monkeypatch):
    feature = FaceFeature(np.ones(512, dtype=np.float32) / np.sqrt(512), 'test-only', 100)
    monkeypatch.setattr(worker, 'get_engine', lambda: SimpleNamespace(extract=lambda image: feature))
    monkeypatch.setattr(registration, 'dispatch', lambda task_id: worker.process(task_id))
    monkeypatch.setattr(faces, 'dispatch', lambda task_id: worker.process(task_id))
    factory = accounts['factory']
    student_no = uuid4().hex
    password = 'test-only-password'
    photo = BytesIO()
    Image.new('RGB', (640, 640), 'white').save(photo, format='PNG')
    files = {'photo': ('test.png', photo.getvalue(), 'image/png')}
    owner = None
    try:
        result = client.post('/api/auth/register', data={
            'name': '第二次作业流程测试', 'student_no': student_no,
            'password': password, 'class_id': str(accounts['class_id']),
        }, files=files, headers={'Idempotency-Key': str(uuid4())})
        assert result.status_code == 202, result.text
        task = result.json()
        status = client.get(task['poll_url'], headers={'X-Task-Token': task['task_token']}).json()
        assert (status['status'], status['result_code']) == ('SUCCEEDED', 'ENROLLED')
        with factory() as db:
            user = db.scalar(select(User).where(User.student_no == student_no))
            owner = user.id
            assert user.status == 'ACTIVE' and user.password_hash != password
            sample = db.scalar(select(FaceSample).where(FaceSample.user_id == owner))
            old_id = sample.id
            assert sample.dimension == 512 and len(sample.embedding) == 2048
        login = client.post('/api/auth/login', json={'student_no': student_no, 'password': password})
        assert login.status_code == 200
        csrf = {'X-CSRF-Token': login.json()['csrf_token']}
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(LoginSession).where(LoginSession.user_id == owner)) == 1
            evidence = snapshot(db, student_no)
            assert evidence['user']['status'] == 'ACTIVE'
            assert evidence['active_login_sessions'] == 1
            assert evidence['photos'][0]['embedding_bytes'] == 2048
            assert 'password' not in str(evidence) and 'task_token' not in str(evidence)
        assert client.get('/api/faces').json()['total'] == 1
        headers = {**csrf, 'Idempotency-Key': str(uuid4())}
        result = client.post('/api/faces', data={'replace_id': str(old_id)}, files=files, headers=headers)
        assert result.status_code == 202, result.text
        repeat = client.post('/api/faces', data={'replace_id': str(old_id)}, files=files, headers=headers)
        assert repeat.status_code == 202, repeat.text
        for field in ['task_id', 'task_token', 'poll_url']:
            assert repeat.json()[field] == result.json()[field]
        assert repeat.json()['status'] == 'SUCCEEDED'
        with factory() as db:
            assert db.get(FaceSample, old_id).status == 'DISABLED'
            assert db.scalar(select(func.count()).select_from(FaceSample).where(FaceSample.user_id == owner, FaceSample.status == 'ACTIVE')) == 1
        assert client.post('/api/auth/logout', headers=csrf).status_code == 204
        assert client.get('/api/me').status_code == 401
        assert client.get('/api/faces').status_code == 401
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(LoginSession).where(LoginSession.user_id == owner)) == 0
            assert snapshot(db, student_no)['active_login_sessions'] == 0
            assert snapshot(db, uuid4().hex) == {'account_found': False}
    finally:
        with factory.begin() as db:
            if owner is None:
                owner = db.scalar(select(User.id).where(User.student_no == student_no))
            if owner is not None:
                for task in db.scalars(select(RecognitionTask).where(RecognitionTask.owner_user_id == owner)):
                    if task.image_path:
                        stored_path(settings.storage_dir, task.image_path).unlink(missing_ok=True)
                state = db.get(FaceLibraryState, 1, with_for_update=True)
                state.version += 1
                for model in [LoginSession, FaceSample]:
                    db.execute(delete(model).where(model.user_id == owner))
                db.execute(delete(RecognitionTask).where(RecognitionTask.owner_user_id == owner))
                db.execute(delete(User).where(User.id == owner))
