from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4
from types import SimpleNamespace
from io import BytesIO
from contextlib import contextmanager
import time

import numpy as np
import pytest
from PIL import Image
from sqlalchemy import select, delete, func

from app import clock
from app.models import AttendanceRecord, AttendanceSession, SessionMember, RecognitionTask, FaceLibraryState, FaceSample
from app.services.attendance_sessions import create_session
from app.services.attendance import finish_checkin
from app.services.tasks import new_task
from app.services.uploads import stored_path
from app.face.matcher import Match
from app.face.types import FaceFeature
from app.jobs import worker, checkin
from tests.integration.test_auth import accounts


@pytest.fixture
def attendance(accounts, settings):
    factory = accounts['factory']; now = clock.utc_now()
    with factory.begin() as db:
        row, _ = create_session(db, accounts['ids'][0], '签到测试', accounts['class_id'], now-timedelta(minutes=1), now+timedelta(minutes=5))
        db.flush(); sid = row.id; code = row.public_code
    yield {**accounts, 'sid': sid, 'code': code}
    with factory.begin() as db:
        db.execute(delete(AttendanceRecord).where(AttendanceRecord.session_id == sid))
        for task in db.scalars(select(RecognitionTask).where(RecognitionTask.session_id == sid)):
            if task.image_path: stored_path(settings.storage_dir, task.image_path).unlink(missing_ok=True)
        db.execute(delete(RecognitionTask).where(RecognitionTask.session_id == sid))
        db.execute(delete(SessionMember).where(SessionMember.session_id == sid))
        db.execute(delete(AttendanceSession).where(AttendanceSession.id == sid))
        db.execute(delete(FaceSample).where(FaceSample.user_id.in_(accounts['ids'])))
        db.get(FaceLibraryState, 1, with_for_update=True).version += 1


def running_task(factory, settings, sid, *, expired=False):
    with factory.begin() as db:
        task = new_task(settings.app_secret, 'test-checkin', str(uuid4()), uuid4().hex, 'CHECKIN')
        task.session_id = sid; task.status = 'RUNNING'; task.attempt_id = str(uuid4())
        if expired: task.expires_at = clock.utc_now()-timedelta(seconds=1)
        db.add(task)
        return task.id, task.attempt_id


def test_atomic_duplicate_late_completion_stale_and_version(attendance, settings):
    factory = attendance['factory']; sid = attendance['sid']; owner = attendance['ids'][1]
    first = running_task(factory, settings, sid); second = running_task(factory, settings, sid)
    with factory.begin() as db:
        version = db.get(FaceLibraryState, 1).version
        # Both requests were fully received before the server closed the session.
        db.get(AttendanceSession, sid).closed_at = clock.utc_now()
    assert finish_checkin(factory, first[0], 'stale', version, Match(owner, .9), None, 'test')
    assert not finish_checkin(factory, first[0], first[1], version-1, Match(owner, .9), None, 'test')
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(AttendanceRecord).where(AttendanceRecord.session_id == sid)) == 0
    def complete(pair):
        return finish_checkin(factory, *pair, version, Match(owner, .9), None, 'test')
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert all(pool.map(complete, [first, second]))
    with factory() as db:
        records = db.scalars(select(AttendanceRecord).where(AttendanceRecord.session_id == sid)).all()
        assert len(records) == 1 and records[0].user_id == owner
        assert {db.get(RecognitionTask, p[0]).result_code for p in [first, second]} == {'CHECKED_IN', 'ALREADY_CHECKED_IN'}
        original_time = records[0].received_at
    complete(first)
    with factory() as db:
        assert db.scalar(select(AttendanceRecord).where(AttendanceRecord.session_id == sid)).received_at == original_time
    expired = running_task(factory, settings, sid, expired=True)
    complete(expired)
    with factory() as db:
        assert db.get(RecognitionTask, expired[0]).result_code == 'TASK_TIMEOUT'


def test_full_gallery_rejects_unknown_ambiguous_and_outside_roster(attendance, settings):
    factory = attendance['factory']; sid = attendance['sid']
    basis = np.zeros(512, dtype=np.float32); basis[0] = 1
    feature = FaceFeature(basis, 'test-checkin', 100)
    with factory.begin() as db:
        # ADMIN is deliberately enrolled but absent from the frozen student roster.
        db.add(FaceSample(user_id=attendance['ids'][0], image_path='uploads/unused.image', embedding=basis.astype('<f4').tobytes(), model_version=feature.model_version))
        db.get(FaceLibraryState, 1, with_for_update=True).version += 1
    outside = running_task(factory, settings, sid)
    checkin.recognize_checkin(factory, *outside, feature, settings)
    other = basis.copy(); other[0] = 0; other[1] = 1
    unknown = running_task(factory, settings, sid)
    checkin.recognize_checkin(factory, *unknown, FaceFeature(other, feature.model_version, 100), settings)
    with factory.begin() as db:
        db.add(FaceSample(user_id=attendance['ids'][1], image_path='uploads/unused.image', embedding=basis.astype('<f4').tobytes(), model_version=feature.model_version))
        db.get(FaceLibraryState, 1, with_for_update=True).version += 1
    ambiguous = running_task(factory, settings, sid)
    checkin.recognize_checkin(factory, *ambiguous, feature, settings)
    with factory() as db:
        assert [db.get(RecognitionTask, p[0]).result_code for p in [outside, unknown, ambiguous]] == ['NOT_IN_ROSTER', 'UNKNOWN_PERSON', 'AMBIGUOUS_PERSON']
        assert db.scalar(select(func.count()).select_from(AttendanceRecord).where(AttendanceRecord.session_id == sid)) == 0


def test_rollback_and_distinct_sessions(attendance, settings):
    factory = attendance['factory']; owner = attendance['ids'][1]; now = clock.utc_now()
    first = running_task(factory, settings, attendance['sid'])
    with factory.begin() as db:
        version = db.get(FaceLibraryState, 1).version
        row, _ = create_session(db, attendance['ids'][0], '另一场次', attendance['class_id'], now-timedelta(minutes=1), now+timedelta(minutes=2))
        db.flush(); other_sid = row.id
    other = running_task(factory, settings, other_sid)
    class FailingFactory:
        @contextmanager
        def begin(self):
            with factory.begin() as db:
                yield db
                db.flush()
                raise RuntimeError('Injected transaction failure')
    try:
        with pytest.raises(RuntimeError, match='Injected transaction failure'):
            finish_checkin(FailingFactory(), *first, version, Match(owner, .9), None, 'test')
        with factory() as db:
            assert db.get(RecognitionTask, first[0]).status == 'RUNNING'
            assert db.scalar(select(func.count()).select_from(AttendanceRecord).where(AttendanceRecord.session_id == attendance['sid'])) == 0
        for pair in [first, other]:
            finish_checkin(factory, *pair, version, Match(owner, .9), None, 'test')
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(AttendanceRecord).where(AttendanceRecord.user_id == owner)) == 2
    finally:
        with factory.begin() as db:
            db.execute(delete(AttendanceRecord).where(AttendanceRecord.session_id == other_sid))
            db.execute(delete(RecognitionTask).where(RecognitionTask.session_id == other_sid))
            db.execute(delete(SessionMember).where(SessionMember.session_id == other_sid))
            db.execute(delete(AttendanceSession).where(AttendanceSession.id == other_sid))


def test_anonymous_worker_flow_and_real_no_face(client, attendance, settings, monkeypatch):
    factory = attendance['factory']; owner = attendance['ids'][1]
    vector = np.ones(512, dtype=np.float32)/np.sqrt(512)
    feature = FaceFeature(vector, 'test-worker', 100)
    with factory.begin() as db:
        db.add(FaceSample(user_id=owner, image_path='uploads/unused.image', embedding=vector.astype('<f4').tobytes(), model_version=feature.model_version))
        db.get(FaceLibraryState, 1, with_for_update=True).version += 1
    data = BytesIO(); Image.new('RGB', (640, 640), 'white').save(data, format='PNG')
    def submit():
        response = client.post('/api/checkins', data={'session_code': attendance['code']}, files={'photo': ('blank.png', data.getvalue())}, headers={'Idempotency-Key': str(uuid4())})
        assert response.status_code == 202, response.text
        return response.json()
    with monkeypatch.context() as patch:
        patch.setattr(worker, 'get_engine', lambda: SimpleNamespace(extract=lambda image: feature))
        patch.setattr('app.api.checkins.dispatch', lambda task_id: worker.process(task_id))
        task = submit()
        result = client.get(task['poll_url'], headers={'X-Task-Token': task['task_token']}).json()
        assert result['status'] == 'SUCCEEDED' and result['result_code'] == 'CHECKED_IN'
        assert 'user_id' not in result and 'name' not in result
        assert client.app.state.redis.zscore('tasks:reservations', task['task_id']) is None
    # Separate real Celery/ONNX negative path; no fixture extractor in the worker.
    task = submit(); deadline = time.monotonic()+40
    while time.monotonic() < deadline:
        result = client.get(task['poll_url'], headers={'X-Task-Token': task['task_token']}).json()
        if result['status'] in {'REJECTED', 'FAILED', 'SUCCEEDED'}: break
        time.sleep(.2)
    assert result['status'] == 'REJECTED' and result['result_code'] == 'NO_FACE'
