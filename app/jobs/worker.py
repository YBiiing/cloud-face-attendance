from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select
from app import clock
from app.config import Settings
from app.database import make_engine,make_session_factory
from app.models.tasks import RecognitionTask
from app.jobs.celery_app import celery_app


@celery_app.task(name='attendance.process')
def process(task_id):
    engine=make_engine(Settings.from_env()); factory=make_session_factory(engine)
    attempt=str(uuid4())
    try:
        with factory.begin() as session:
            task=session.scalar(select(RecognitionTask).where(RecognitionTask.id==task_id).with_for_update())
            if not task or task.status!='PENDING': return
            now=clock.utc_now()
            if task.expires_at<=now:
                task.status='FAILED';task.result_code='TASK_TIMEOUT';task.finished_at=now
                return
            task.status='RUNNING';task.attempt_id=attempt;task.attempts+=1
            task.started_at=now;task.lease_until=now+timedelta(seconds=150)
            kind=task.type
        if kind=='PING':
            with factory.begin() as session:
                task=session.scalar(select(RecognitionTask).where(RecognitionTask.id==task_id).with_for_update())
                if task.status=='RUNNING' and task.attempt_id==attempt and task.expires_at>clock.utc_now():
                    task.status='SUCCEEDED';task.result_code='WORKER_OK';task.finished_at=clock.utc_now()
        else:
            # Business task handlers are introduced by P3-03 and P5-02.
            raise RuntimeError('Unsupported task type')
    except Exception:
        with factory.begin() as session:
            task=session.scalar(select(RecognitionTask).where(RecognitionTask.id==task_id).with_for_update())
            if task and task.status=='RUNNING' and task.attempt_id==attempt:
                task.status='FAILED';task.result_code='PROCESSING_FAILED';task.finished_at=clock.utc_now()
    finally: engine.dispose()
