from uuid import uuid4
from datetime import timedelta
import pytest
from sqlalchemy import delete, select
from app.database import make_engine, make_session_factory
from app.models import User, ClassRoom, LoginSession
from app.security import hash_password, COOKIE
from app import clock


@pytest.fixture
def accounts(settings):
    engine=make_engine(settings); factory=make_session_factory(engine)
    marker=uuid4().hex[:12]; password='test-password-'+marker
    with factory.begin() as s:
        classroom=ClassRoom(name=marker); s.add(classroom); s.flush()
        rows=[User(student_no=marker+role, name=role, role=role, status='ACTIVE', class_id=classroom.id if role=='STUDENT' else None, password_hash=hash_password(password)) for role in ['ADMIN','STUDENT']]
        s.add_all(rows); s.flush(); ids=[r.id for r in rows]; class_id=classroom.id
    yield {'admin':marker+'ADMIN','student':marker+'STUDENT','password':password,'factory':factory,'ids':ids,'class_id':class_id}
    with factory.begin() as s:
        s.execute(delete(LoginSession).where(LoginSession.user_id.in_(ids)))
        s.execute(delete(User).where(User.id.in_(ids)))
        s.execute(delete(ClassRoom).where(ClassRoom.id==class_id))
    engine.dispose()


def sign_in(client, accounts, role):
    result=client.post('/api/auth/login',json={'student_no':accounts[role],'password':accounts['password']})
    assert result.status_code==200
    return {'X-CSRF-Token':result.json()['csrf_token']}


def test_sessions_roles_csrf_logout(client, accounts):
    assert client.get('/api/me').status_code==401
    headers=sign_in(client,accounts,'student')
    cookie=client.cookies.get(COOKIE)
    assert client.get('/api/me').json()['user']['role']=='STUDENT'
    assert client.post('/api/classes',json={'name':'拒绝'},headers=headers).status_code==403
    assert client.post('/api/auth/logout').status_code==403
    assert client.post('/api/auth/logout',headers=headers).status_code==204
    assert client.get('/api/me',headers={'cookie':f'{COOKIE}={cookie}'}).status_code==401
    headers=sign_in(client,accounts,'admin')
    assert client.get('/api/users').status_code==200
    result=client.post('/api/classes',json={'name':'新测试班'},headers=headers)
    assert result.status_code==201
    with accounts['factory'].begin() as s: s.execute(delete(ClassRoom).where(ClassRoom.id==result.json()['id']))


def test_invalid_login_origin_and_expired_session(client,accounts):
    data={'student_no':accounts['admin'],'password':'wrong-password'}
    assert client.post('/api/auth/login',json=data).status_code==401

    data['password']=accounts['password']
    assert client.post('/api/auth/login',json=data,headers={'Origin':'https://evil.example'}).status_code==403
    assert client.post('/api/auth/login',json={**data,'role':'ADMIN'}).status_code==422
    sign_in(client,accounts,'admin')
    with accounts['factory'].begin() as s:
        row=s.scalar(select(LoginSession).where(LoginSession.user_id==accounts['ids'][0]))
        row.expires_at=clock.utc_now()-timedelta(seconds=1)
    assert client.get('/api/me').status_code==401
    with accounts['factory'].begin() as s: s.get(User,accounts['ids'][0]).status='DISABLED'
    assert client.post('/api/auth/login',json=data).status_code==401


def test_login_rate_limit_remains_enforced(client):
    data={'student_no':uuid4().hex,'password':'abc123'}
    for _ in range(20):
        assert client.post('/api/auth/login',json=data).status_code==401
    response=client.post('/api/auth/login',json=data)
    assert response.status_code==429 and response.json()['error']['code']=='RATE_LIMITED'
