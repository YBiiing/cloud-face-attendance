from datetime import timedelta
from uuid import uuid4
from sqlalchemy import delete
from app import clock
from app.models import RecognitionTask
from app.jobs.scheduler import sweep
from app.jobs.worker import process
from app.services.tasks import new_task
from app.database import make_engine, make_session_factory


def test_republication_lease_lost_attempt_and_retry_cap(settings, monkeypatch):
    engine=make_engine(settings);factory=make_session_factory(engine);ids=[]
    now=clock.utc_now()
    monkeypatch.setattr(clock,'utc_now',lambda:now)
    try:
        with factory.begin() as db:
            for _ in range(3):
                task=new_task(settings.app_secret,'recovery-test',str(uuid4()),uuid4().hex,'PING')
                db.add(task);ids.append(task.id)
            row=db.get(RecognitionTask,ids[1]);row.status='RUNNING';row.attempt_id='lost';row.attempts=1;row.lease_until=now-timedelta(seconds=1)
            row=db.get(RecognitionTask,ids[2]);row.attempts=3
        deliveries=[]
        # Broker failure after DB commit: sweep retains a bounded publication lease.
        sweep(factory,publish=lambda task_id:deliveries.append(task_id) or False)
        assert set(ids[:2]).issubset(deliveries) and ids[2] not in deliveries
        deliveries.clear();sweep(factory,publish=deliveries.append)
        assert not set(ids)&set(deliveries)
        with factory() as db:
            assert db.get(RecognitionTask,ids[1]).attempt_id is None
            assert db.get(RecognitionTask,ids[2]).status=='FAILED'
        now+=timedelta(seconds=16)
        sweep(factory,publish=lambda task_id:process(task_id) if task_id in ids else None)
        process(ids[0])  # redelivery after a committed success
        with factory() as db:
            assert db.get(RecognitionTask,ids[0]).status=='SUCCEEDED'
            assert db.get(RecognitionTask,ids[0]).attempts==1
            assert db.get(RecognitionTask,ids[1]).status=='SUCCEEDED'
            assert db.get(RecognitionTask,ids[1]).attempts==2
    finally:
        with factory.begin() as db:db.execute(delete(RecognitionTask).where(RecognitionTask.id.in_(ids)))
        engine.dispose()
