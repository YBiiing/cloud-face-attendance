from datetime import timedelta
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

from PIL import Image
from sqlalchemy import delete, select

from app import clock
from app.models import User, RecognitionTask, AttendanceSession, SessionMember
from app.services import capacity
from app.services.attendance_sessions import create_session
from app.services.tasks import new_task, task_token
from app.services.uploads import stored_path
from app.jobs.worker import process
from app.jobs.scheduler import sweep
from app.face.types import FaceError
from tests.integration.test_auth import accounts, sign_in


def test_all_ingress_share_capacity_and_terminal_release(client, settings, accounts, monkeypatch):
    key = 'test-capacity:'+uuid4().hex; monkeypatch.setattr(capacity, 'KEY', key)
    for module in ['registration', 'faces', 'checkins']:
        monkeypatch.setattr(f'app.api.{module}.dispatch', lambda task_id: True)
        monkeypatch.setattr(f'app.api.{module}.rate_limit', lambda *args: None)
    redis = client.app.state.redis; factory = accounts['factory']; ids = []; marker = uuid4().hex[:20]
    with factory.begin() as db:
        user = User(student_no=marker, name='重试容量', password_hash='unused', class_id=accounts['class_id'])
        db.add(user); db.flush(); retry_owner = user.id
        retry_key = str(uuid4()); old = new_task(settings.app_secret, 'capacity-retry', retry_key, 'a'*64, 'ENROLL', user.id)
        old.status = 'FAILED'; old.finished_at = clock.utc_now(); db.add(old); old_id = old.id; ids.append(old_id)
        now = clock.utc_now()
        row, _ = create_session(db, accounts['ids'][0], '容量验证', accounts['class_id'], now-timedelta(minutes=1), now+timedelta(minutes=5))
        db.flush(); sid = row.id; code = row.public_code
    image = BytesIO(); Image.new('RGB', (100, 100), 'white').save(image, format='PNG')
    headers = sign_in(client, accounts, 'student')
    calls = [('/api/auth/register', {'name': '容量录入', 'student_no': marker+'new', 'password': 'test-only-password', 'class_id': accounts['class_id']}, {}),
             (f'/api/auth/register/{old_id}/retry', {}, {'X-Task-Token': task_token(settings.app_secret, old_id, retry_key)}),
             ('/api/faces', {}, headers), ('/api/checkins', {'session_code': code}, {})]
    try:
        for path, data, extra in calls:
            response = client.post(path, data=data, files={'photo': ('p.png', image.getvalue())}, headers={**extra, 'Idempotency-Key': str(uuid4())})
            assert response.status_code == 202, response.text
            task_id = response.json()['task_id']; ids.append(task_id)
            assert redis.zscore(key, task_id) is not None
        assert redis.zcard(key) == 4
        # Fill the remaining slots, then every route must reject without orphan uploads.
        for i in range(46): capacity.reserve(redis, 'filler-'+str(i), now+timedelta(minutes=5))
        before = set(settings.storage_dir.rglob('*.image'))
        # Retry is already running; use another failed task for its capacity check.
        with factory.begin() as db:
            task = db.get(RecognitionTask, ids[2]); task.status = 'FAILED'; task.finished_at = now
        for path, data, extra in calls:
            if path == '/api/auth/register': data = {**data, 'student_no': marker+'full'}
            response = client.post(path, data=data, files={'photo': ('p.png', image.getvalue())}, headers={**extra, 'Idempotency-Key': str(uuid4())})
            assert response.status_code == 503 and response.json()['error']['code'] == 'QUEUE_FULL', response.text
        assert set(settings.storage_dir.rglob('*.image')) == before
        def reject(_): raise FaceError('NO_FACE')
        monkeypatch.setattr('app.jobs.worker.get_engine', lambda: SimpleNamespace(extract=reject))
        for task_id in [ids[1], ids[3], ids[4]]:
            process(task_id)
            assert redis.zscore(key, task_id) is None
        # Retry budget timeout must release before the reservation TTL expires.
        with factory.begin() as db:
            task = db.get(RecognitionTask, ids[2]); task.status = 'PENDING'; task.attempts = 3
        sweep(factory, publish=lambda _: None, on_terminal=lambda task_id: capacity.release(redis, task_id))
        assert redis.zscore(key, ids[2]) is None
    finally:
        redis.delete(key)
        with factory.begin() as db:
            for task in db.scalars(select(RecognitionTask).where(RecognitionTask.id.in_(ids))):
                if task.image_path: stored_path(settings.storage_dir, task.image_path).unlink(missing_ok=True)
                db.delete(task)
            db.flush()
            db.execute(delete(User).where(User.student_no.in_([marker, marker+'new', marker+'full'])))
            db.execute(delete(SessionMember).where(SessionMember.session_id == sid))
            db.execute(delete(AttendanceSession).where(AttendanceSession.id == sid))
