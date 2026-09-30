from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from app import clock
from app.config import Settings
from app.database import make_engine,make_session_factory
from app.models.tasks import RecognitionTask
from app.jobs.celery_app import celery_app
from celery.signals import worker_ready
from app.face.types import FaceError
from app.services.uploads import stored_path
from app.face.images import decode_image
from app.services.enrollment import finish_enrollment
from app.jobs.model_runtime import get_engine
from app.jobs.checkin import recognize_checkin
from app.services.capacity import release
from redis import Redis


@worker_ready.connect
def prepare_worker(sender=None, **kwargs):
    celery_app.send_task('attendance.warmup')


@celery_app.task(name='attendance.warmup')
def warmup():
    get_engine()


@celery_app.task(name='attendance.process')
def process(task_id):
    engine=make_engine(Settings.from_env()); factory=make_session_factory(engine)
    attempt=str(uuid4())
    try:
        with factory.begin() as session:
            task=session.scalar(select(RecognitionTask).where(RecognitionTask.id==task_id).with_for_update())
            if not task or task.status!='PENDING': return
            now=clock.utc_now()
            if task.expires_at<=now or task.attempts>=3:
                task.status='FAILED';task.result_code='TASK_TIMEOUT';task.finished_at=now
                return
            task.status='RUNNING';task.attempt_id=attempt;task.attempts+=1
            task.started_at=now;task.lease_until=now+timedelta(seconds=150)
            kind=task.type;image_path=task.image_path
        if kind=='PING':
            with factory.begin() as session:
                task=session.scalar(select(RecognitionTask).where(RecognitionTask.id==task_id).with_for_update())
                if task.status=='RUNNING' and task.attempt_id==attempt and task.expires_at>clock.utc_now():
                    task.status='SUCCEEDED';task.result_code='WORKER_OK';task.finished_at=clock.utc_now()
        elif kind in {'ENROLL','FACE','CHECKIN'}:
            image=decode_image(stored_path(Settings.from_env().storage_dir,image_path).read_bytes())
            feature=get_engine().extract(image)
            if kind=='CHECKIN':
                recognize_checkin(factory,task_id,attempt,feature,Settings.from_env())
            else:
                finish_enrollment(factory,task_id,attempt,feature)
        else:
            # Business task handlers are introduced by P3-03 and P5-02.
            raise RuntimeError('Unsupported task type')
    except OperationalError:
        # MySQL may be unavailable after inference or at commit. Keep the durable
        # attempt for lease recovery; never guess whether a commit succeeded.
        raise
    except Exception as error:
        with factory.begin() as session:
            task=session.scalar(select(RecognitionTask).where(RecognitionTask.id==task_id).with_for_update())
            if task and task.status=='RUNNING' and task.attempt_id==attempt:
                task.status='REJECTED' if isinstance(error,FaceError) else 'FAILED'
                task.result_code=error.code if isinstance(error,FaceError) else 'PROCESSING_FAILED'
                task.finished_at=clock.utc_now()
    finally:
        try:
            with factory() as session:
                task=session.get(RecognitionTask,task_id)
                terminal=task and task.type=='CHECKIN' and task.status in {'SUCCEEDED','REJECTED','FAILED'}
            if terminal:
                redis=Redis.from_url(Settings.from_env().redis_url,socket_connect_timeout=2,socket_timeout=2)
                try:release(redis,task_id)
                finally:redis.close()
        finally:engine.dispose()
