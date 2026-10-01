"""A lost COMMIT acknowledgement must not delete committed task photos."""
from datetime import timedelta
from io import BytesIO
from uuid import uuid4

from PIL import Image
import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import clock
from app.models import User, RecognitionTask, AttendanceSession, SessionMember
from app.services.attendance_sessions import create_session
from app.services.tasks import new_task, task_token
from app.services.uploads import stored_path
from app.security import token_hash
from tests.integration.test_auth import accounts, sign_in


@pytest.mark.parametrize('kind', ['register', 'retry', 'face', 'checkin'])
def test_committed_upload_survives_lost_ack(client, settings, accounts, monkeypatch, kind):
    factory = accounts['factory']; marker = uuid4().hex; key = str(uuid4())
    sid = None; owner = None; old_id = None
    headers = {'Idempotency-Key': key}; data = {}
    if kind == 'face':
        headers.update(sign_in(client, accounts, 'student')); path = '/api/faces'
    elif kind == 'checkin':
        now = clock.utc_now()
        with factory.begin() as db:
            row, _ = create_session(db, accounts['ids'][0], marker, accounts['class_id'], now-timedelta(minutes=1), now+timedelta(minutes=5))
            db.flush(); sid = row.id; data = {'session_code': row.public_code}
        path = '/api/checkins'
    elif kind == 'register':
        path = '/api/auth/register'
        data = {'name': '提交异常', 'student_no': marker, 'class_id': accounts['class_id'], 'password': 'test-only-password'}
    else:
        with factory.begin() as db:
            user = User(student_no=marker, name='重试异常', password_hash='unused', class_id=accounts['class_id'])
            db.add(user); db.flush(); owner = user.id
            old = new_task(settings.app_secret, 'register', key, 'a'*64, 'ENROLL', owner)
            old.status = 'FAILED'; old.finished_at = clock.utc_now(); db.add(old); old_id = old.id
        headers['X-Task-Token'] = task_token(settings.app_secret, old_id, key)
        path = f'/api/auth/register/{old_id}/retry'
    image = BytesIO(); Image.new('RGB', (100, 100), 'white').save(image, format='PNG')
    committed = []; original = Session.commit

    def commit_then_lose_ack(db):
        # Route explicitly flushes before commit, so query captures durable IDs.
        ids = list(db.scalars(select(RecognitionTask.id).where(RecognitionTask.request_key == token_hash(key))))
        original(db); committed.extend(ids)
        raise OperationalError('COMMIT', {}, Exception('simulated lost acknowledgement'))

    try:
        with monkeypatch.context() as patch:
            patch.setattr(Session, 'commit', commit_then_lose_ack)
            response = client.post(path, data=data, files={'photo': ('p.png', image.getvalue())}, headers=headers)
        assert response.status_code == 500
        with factory() as db:
            rows = db.scalars(select(RecognitionTask).where(RecognitionTask.id.in_(committed), RecognitionTask.id != (old_id or ''))).all()
            assert len(rows) == 1
            assert rows[0].status == 'PENDING'
            assert stored_path(settings.storage_dir, rows[0].image_path).read_bytes() == image.getvalue()
            if kind in {'register', 'retry'}: owner = rows[0].owner_user_id
            if kind == 'checkin': assert client.app.state.redis.zscore('tasks:reservations', rows[0].id) is not None
    finally:
        with factory.begin() as db:
            for row in db.scalars(select(RecognitionTask).where(RecognitionTask.id.in_(committed + ([old_id] if old_id else [])))):
                if row.image_path: stored_path(settings.storage_dir, row.image_path).unlink(missing_ok=True)
                client.app.state.redis.zrem('tasks:reservations', row.id)
                db.delete(row)
            db.flush()
            if owner: db.execute(delete(User).where(User.id == owner))
            if sid:
                db.execute(delete(SessionMember).where(SessionMember.session_id == sid))
                db.execute(delete(AttendanceSession).where(AttendanceSession.id == sid))
