from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
from threading import Barrier
from uuid import uuid4

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select,delete
from sqlalchemy.exc import OperationalError,ProgrammingError

from app.main import create_app
from app.models import User,FaceSample,FaceLibraryState,RecognitionTask
from app.face.types import FaceFeature,FaceError
from app.services.enrollment import finish_enrollment
from app.services.tasks import new_task
from app.services.uploads import stored_path
from tests.integration.test_auth import accounts,sign_in


def test_authenticated_upload_releases_auth_connection(client,settings,accounts,monkeypatch):
    from app.api import faces
    gate=Barrier(10);original=faces.face_transaction;ids=[]
    def together(*args):
        gate.wait(timeout=10)
        return original(*args)
    monkeypatch.setattr(faces,'face_transaction',together)
    monkeypatch.setattr(faces,'dispatch',lambda _:True)
    headers=sign_in(client,accounts,'student')
    image=BytesIO();Image.new('RGB',(100,100),'white').save(image,format='PNG')
    before=set(settings.storage_dir.rglob('*.image'))
    try:
        def submit(_):
            return client.post('/api/faces',files={'photo':('blank.png',image.getvalue())},headers={**headers,'Idempotency-Key':str(uuid4())})
        with ThreadPoolExecutor(max_workers=10) as pool:responses=list(pool.map(submit,range(10)))
        ids=[r.json()['task_id'] for r in responses if r.status_code==202]
        assert [r.status_code for r in responses]==[202]*10
        assert client.app.state.engine.pool.checkedout()==0
    finally:
        with accounts['factory'].begin() as db:
            db.execute(delete(RecognitionTask).where(RecognitionTask.id.in_(ids)))
        from app.services.capacity import release
        for tid in ids:release(client.app.state.redis,tid)
        for path in set(settings.storage_dir.rglob('*.image'))-before:path.unlink()


def test_database_connection_failure_is_503_without_details(settings):
    with TestClient(create_app(replace(settings,mysql_port=1))) as client:
        response=client.get('/api/classes')
        assert response.status_code==503 and response.json()['error']['code']=='SERVICE_UNAVAILABLE'
        assert 'pymysql' not in response.text and settings.mysql_password not in response.text


def test_database_sql_error_is_not_disguised_as_outage(client):
    @client.app.get('/test-only-database-error')
    def fail():raise ProgrammingError('secret-sql',{},Exception(1064,'secret-sql'))
    response=client.get('/test-only-database-error')
    assert response.status_code==500 and 'secret-sql' not in response.text


def test_rate_limit_retry_after_and_shared_nat_budget(client,accounts):
    from app.security import rate_limit
    from fastapi import Request
    @client.app.get('/test-only-nat')
    def budget(request:Request):rate_limit(request,'test-nat',request.app.state.settings.checkin_ip_rate_limit);return {}
    for _ in range(31):assert client.get('/test-only-nat').status_code==200
    @client.app.get('/test-only-small-budget')
    def small(request:Request):rate_limit(request,'test-small',2);return {}
    assert client.get('/test-only-small-budget').status_code==200
    assert client.get('/test-only-small-budget').status_code==200
    response=client.get('/test-only-small-budget');assert response.status_code==429
    assert 1<=int(response.headers['Retry-After'])<=60


def test_cross_account_duplicate_enrolment_is_atomic(settings,accounts):
    factory=accounts['factory'];owner=accounts['ids'][1];vector=np.zeros(512,dtype='<f4');vector[0]=1
    with factory.begin() as db:
        other=User(student_no=uuid4().hex,name='Duplicate fixture',password_hash='unused',status='PENDING');db.add(other);db.flush();uid=other.id
        face=FaceSample(user_id=owner,image_path='uploads/duplicate-fixture.image',embedding=vector.tobytes(),model_version='duplicate-test');db.add(face);db.flush();fid=face.id
        task=new_task(settings.app_secret,'duplicate-test',str(uuid4()),'a'*64,'ENROLL',uid,'uploads/unused.image');task.status='RUNNING';task.attempt_id='current';db.add(task);tid=task.id
    feature=FaceFeature(vector,'duplicate-test',100)
    try:
        with pytest.raises(FaceError,match='FACE_ALREADY_ENROLLED'):finish_enrollment(factory,tid,'current',feature)
        with factory() as db:
            assert db.get(User,uid).status=='PENDING'
            assert db.scalar(select(FaceSample.id).where(FaceSample.user_id==uid)) is None
        with factory.begin() as db:db.get(FaceSample,fid).status='DISABLED'
        finish_enrollment(factory,tid,'current',feature)
        with factory() as db:assert db.get(User,uid).status=='ACTIVE'
    finally:
        with factory.begin() as db:
            db.get(FaceLibraryState,1,with_for_update=True).version+=1
            db.execute(delete(FaceSample).where(FaceSample.user_id==uid));db.execute(delete(FaceSample).where(FaceSample.id==fid))
            db.execute(delete(RecognitionTask).where(RecognitionTask.id==tid));db.execute(delete(User).where(User.id==uid))
