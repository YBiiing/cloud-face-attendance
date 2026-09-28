from io import BytesIO
from uuid import uuid4
import time
from PIL import Image
import numpy as np
from sqlalchemy import select,delete
from app.database import make_engine,make_session_factory
from app.models import ClassRoom,User,RecognitionTask,FaceSample,FaceLibraryState
from app.face.types import FaceFeature
from app.services.enrollment import finish_enrollment
from app.services.tasks import new_task
from app import clock
from contextlib import contextmanager
import pytest


def test_registration_unknown_photo_retry_and_idempotency(client,settings):
    engine=make_engine(settings);factory=make_session_factory(engine)
    with factory.begin() as s:
        classroom=ClassRoom(name='注册测试');s.add(classroom);s.flush();class_id=classroom.id
    marker=uuid4().hex;key=str(uuid4());owner=None;task_ids=[]
    photo=BytesIO();Image.new('RGB',(640,640),'white').save(photo,format='PNG');content=photo.getvalue()
    data={'name':'测试','student_no':marker,'class_id':str(class_id),'password':'test-password-only'}
    headers={'Idempotency-Key':key}
    try:
        r=client.post('/api/auth/register',data=data,files={'photo':('photo.png',content,'image/png')},headers=headers)
        assert r.status_code==202,r.text
        result=r.json();task_ids.append(result['task_id']);task_headers={'X-Task-Token':result['task_token']}
        repeat=client.post('/api/auth/register',data=data,files={'photo':('photo.png',content,'image/png')},headers=headers)
        assert repeat.status_code==202 and repeat.json()['task_id']==result['task_id']
        with factory() as s: owner=s.scalar(select(User.id).where(User.student_no==marker))
        assert client.post('/api/auth/login',json={'student_no':marker,'password':data['password']}).status_code==401
        deadline=time.monotonic()+40
        while time.monotonic()<deadline:
            result_status=client.get(result['poll_url'],headers=task_headers).json()
            if result_status['status'] in {'REJECTED','FAILED','SUCCEEDED'}: break
            time.sleep(.2)
        assert result_status['status']=='REJECTED' and result_status['result_code']=='NO_FACE',result_status
        retry_url=f"/api/auth/register/{result['task_id']}/retry"
        assert client.post(retry_url,files={'photo':('p.png',content)},headers={'Idempotency-Key':str(uuid4())}).status_code==404
        retry=client.post(retry_url,files={'photo':('p.png',content)},headers={**task_headers,'Idempotency-Key':str(uuid4())})
        assert retry.status_code==202,retry.text
        task_ids.append(retry.json()['task_id'])
        with factory() as s:
            assert s.get(User,owner).status=='PENDING'
            assert s.scalar(select(FaceSample.id).where(FaceSample.user_id==owner)) is None
    finally:
        with factory.begin() as s:
            tasks=s.scalars(select(RecognitionTask).where(RecognitionTask.owner_user_id==owner)).all() if owner else []
            for t in tasks:
                if t.image_path:
                    from app.services.uploads import stored_path
                    stored_path(settings.storage_dir,t.image_path).unlink(missing_ok=True)
            s.execute(delete(RecognitionTask).where(RecognitionTask.owner_user_id==owner))
            if owner: s.execute(delete(User).where(User.id==owner))
            s.execute(delete(ClassRoom).where(ClassRoom.id==class_id))
        engine.dispose()


def test_atomic_enrollment_and_stale_attempt(settings):
    engine=make_engine(settings);factory=make_session_factory(engine);marker=uuid4().hex
    with factory.begin() as s:
        user=User(student_no=marker,name='事务验证',password_hash='unused');s.add(user);s.flush();owner=user.id
        task=new_task(settings.app_secret,'atomic',str(uuid4()),'a'*64,'ENROLL',owner,'uploads/test.image')
        task.status='RUNNING';task.attempt_id='current';s.add(task);task_id=task.id
    feature=FaceFeature(np.ones(512,dtype=np.float32)/np.sqrt(512),'test-only',100)
    try:
        finish_enrollment(factory,task_id,'stale',feature)
        with factory() as s: assert s.get(User,owner).status=='PENDING'
        class FailingFactory:
            @contextmanager
            def begin(self):
                with factory.begin() as session:
                    yield session
                    raise RuntimeError('Injected commit failure')
        with pytest.raises(RuntimeError,match='Injected commit failure'):
            finish_enrollment(FailingFactory(),task_id,'current',feature)
        with factory() as s:
            assert s.get(User,owner).status=='PENDING'
            assert s.scalar(select(FaceSample.id).where(FaceSample.user_id==owner)) is None
            assert s.get(RecognitionTask,task_id).status=='RUNNING'
        finish_enrollment(factory,task_id,'current',feature)
        with factory() as s:
            assert s.get(User,owner).status=='ACTIVE'
            assert s.get(RecognitionTask,task_id).status=='SUCCEEDED'
            assert s.scalar(select(FaceSample.id).where(FaceSample.user_id==owner)) is not None
    finally:
        with factory.begin() as s:
            state=s.get(FaceLibraryState,1,with_for_update=True);state.version+=1
            s.execute(delete(FaceSample).where(FaceSample.user_id==owner))
            s.execute(delete(RecognitionTask).where(RecognitionTask.id==task_id))
            s.execute(delete(User).where(User.id==owner))
        engine.dispose()
