from datetime import datetime, timezone, timedelta
from uuid import uuid4
from dataclasses import replace

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient

from app.database import make_engine, make_session_factory
from app.models import ClassRoom, User
from app.main import create_app


def test_health_and_public_files(client):
    assert client.get('/').status_code == 200
    assert client.get('/assets/home.js').status_code == 200
    live = client.get('/api/health/live')
    assert live.status_code == 200
    assert len(live.headers['x-request-id']) == 32
    ready = client.get('/api/health/ready')
    checks=ready.json()['checks']
    assert checks['mysql']=='ok' and checks['redis']=='ok'
    assert checks['model_worker'] in {'ok','unavailable'}
    assert ready.status_code == (200 if checks['model_worker']=='ok' else 503)
    for path in ['/.env', '/docs/design.md', '/api/not-implemented', '/assets/../app/main.py']:
        response = client.get(path)
        assert response.status_code == 404
        assert response.json()['error']['request_id'] == response.headers['x-request-id']


def test_missing_database_is_unavailable(settings):
    with TestClient(create_app(replace(settings, mysql_port=1))) as client:
        assert client.get('/api/health/live').status_code == 200
        result = client.get('/api/health/ready')
        assert result.status_code == 503
        assert result.json()['checks']['mysql'] == 'unavailable'


def test_rollback_and_unique_student(settings):
    engine = make_engine(settings)
    factory = make_session_factory(engine)
    marker = uuid4().hex
    with factory() as s:
        classroom = ClassRoom(name=marker)
        s.add(classroom); s.flush()
        for _ in range(2):
            s.add(User(student_no=marker, name='测试', class_id=classroom.id, password_hash='unused'))
        with pytest.raises(IntegrityError):
            s.flush()
        s.rollback()
    with factory() as s:
        assert s.scalar(select(ClassRoom).where(ClassRoom.name == marker)) is None
        assert s.scalar(select(User).where(User.student_no == marker)) is None
    engine.dispose()


def test_timezone_roundtrip_and_foreign_key(session):
    moment = datetime(2026, 9, 28, 14, 0, tzinfo=timezone(timedelta(hours=8)))
    row = ClassRoom(name='时区验证', created_at=moment)
    session.add(row); session.flush(); session.expire(row)
    assert row.created_at == datetime(2026, 9, 28, 6, 0, tzinfo=timezone.utc)
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.add(User(student_no=uuid4().hex, name='外键验证', class_id=2147483647, password_hash='unused'))
            session.flush()


def test_logs_and_errors_do_not_echo_secrets(client, caplog):
    caplog.set_level('INFO', logger='attendance.requests')
    response = client.get('/missing?password=never-log-this', headers={'X-Task-Token': 'never-log-this'})
    assert response.status_code == 404
    assert 'never-log-this' not in response.text
    own_logs = '\n'.join(r.message for r in caplog.records if r.name == 'attendance.requests')
    assert 'never-log-this' not in own_logs
    assert response.headers['x-request-id'] in own_logs
