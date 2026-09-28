from uuid import uuid4
from datetime import timedelta
import time
import pytest
from sqlalchemy import select, delete

from app.database import make_engine,make_session_factory
from app.models.tasks import RecognitionTask
from app.services.tasks import new_task,find_replay,accepted,dispatch
from app.errors import AppError


def test_task_credentials_replay_and_real_worker(client,settings):
    engine=make_engine(settings);factory=make_session_factory(engine)
    key=str(uuid4());digest='a'*64
    task=new_task(settings.app_secret,'test',key,digest,'PING')
    with factory.begin() as s: s.add(task)
    try:
        response=accepted(task,settings.app_secret,key)
        path=response['poll_url'];headers={'X-Task-Token':response['task_token']}
        assert client.get(path).status_code==404
        assert client.get(path,headers={'X-Task-Token':'bad'}).status_code==404
        assert client.get(path,headers=headers).status_code==200
        with factory() as s:
            replay=find_replay(s,'test',key,digest)
            assert accepted(replay,settings.app_secret,key)['task_token']==response['task_token']
            with pytest.raises(AppError,match='IDEMPOTENCY_CONFLICT'): find_replay(s,'test',key,'b'*64)
        assert dispatch(task.id)
        assert dispatch(task.id)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            result=client.get(path,headers=headers).json()
            if result['status']=='SUCCEEDED': break
            time.sleep(.2)
        assert result['status']=='SUCCEEDED'
        assert result['result_code']=='WORKER_OK'
        with factory() as s:
            saved=s.get(RecognitionTask,task.id)
            assert saved.attempts==1
    finally:
        with factory.begin() as s: s.execute(delete(RecognitionTask).where(RecognitionTask.id==task.id))
        engine.dispose()
