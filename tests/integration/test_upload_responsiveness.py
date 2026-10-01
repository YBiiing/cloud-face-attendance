"""Blocked sync dependencies must not stall unrelated requests on the same app."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

from PIL import Image
import pytest
from app.security import current_user
from app.services.uploads import stored_path


@pytest.mark.parametrize('kind', ['register', 'retry', 'face', 'checkin'])
@pytest.mark.parametrize('stage', ['transaction', 'rate_limit'])
def test_blocked_upload_dependency_keeps_api_responsive(client, settings, monkeypatch, kind, stage):
    entered = Event(); release = Event()
    module = {'register': 'registration', 'retry': 'registration', 'face': 'faces', 'checkin': 'checkins'}[kind]
    service = {'register': 'register_transaction', 'retry': 'retry_transaction', 'face': 'face_transaction', 'checkin': 'submit_transaction'}[kind]
    def hold():
        entered.set()
        if not release.wait(8): raise RuntimeError('test did not release dependency')
    def transaction(*args):
        try:
            if stage == 'transaction': hold()
            return {'task_id': 'test-only'}
        finally:
            upload = next(arg for arg in args if hasattr(arg, 'digest') and hasattr(arg, 'path'))
            stored_path(settings.storage_dir, upload.path).unlink(missing_ok=True)
    def limit(*args):
        if stage == 'rate_limit': hold()
    monkeypatch.setattr(f'app.api.{module}.{service}', transaction)
    monkeypatch.setattr(f'app.api.{module}.rate_limit', limit)
    monkeypatch.setattr('app.api.registration.validate_retry', lambda *args: None)
    client.app.dependency_overrides[current_user] = lambda: SimpleNamespace(id=1, role='STUDENT')
    paths = {'register': '/api/auth/register', 'retry': '/api/auth/register/test/retry', 'face': '/api/faces', 'checkin': '/api/checkins'}
    data = {'register': {'name': '响应测试', 'student_no': uuid4().hex, 'password': 'test-only-password', 'class_id': 1},
            'checkin': {'session_code': 'test-only'}}.get(kind, {})
    image = BytesIO(); Image.new('RGB', (100, 100), 'white').save(image, format='PNG')
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            upload = executor.submit(client.post, paths[kind], data=data,
                files={'photo': ('p.png', image.getvalue())}, headers={'Idempotency-Key': str(uuid4())})
            try:
                assert entered.wait(3), 'upload did not reach the controlled dependency'
                health = executor.submit(client.get, '/api/health/live')
                assert health.result(timeout=2).status_code == 200
                assert not upload.done(), 'dependency should still be blocked during the health response'
            finally:
                release.set()
            assert upload.result(timeout=3).status_code == 202
    finally:
        release.set(); client.app.dependency_overrides.clear()
