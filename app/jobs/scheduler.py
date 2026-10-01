import time
from datetime import timedelta
from sqlalchemy import select
from app import clock
from app.config import Settings
from app.database import make_engine,make_session_factory
from app.models.tasks import RecognitionTask
from app.services.tasks import dispatch
from app.services.capacity import release
from redis import Redis


def sweep(factory, publish=dispatch, on_terminal=None):
    now=clock.utc_now()
    with factory.begin() as session:
        rows=session.scalars(select(RecognitionTask).where(
            RecognitionTask.status.in_(['PENDING','RUNNING']),
            (RecognitionTask.expires_at<=now) | (RecognitionTask.lease_until.is_(None)) | (RecognitionTask.lease_until<=now)
        ).order_by(RecognitionTask.created_at).limit(100).with_for_update(skip_locked=True)).all()
        pending=[];terminal=[]
        for row in rows:
            lease_expired = row.status=='RUNNING' and (row.lease_until is None or row.lease_until<=now)
            if row.expires_at<=now or (row.attempts>=3 and (row.status=='PENDING' or lease_expired)):
                row.status='FAILED';row.result_code='TASK_TIMEOUT';row.finished_at=now;terminal.append(row.id)
            elif lease_expired:
                row.status='PENDING';row.attempt_id=None;row.lease_until=now+timedelta(seconds=15);pending.append(row.id)
            elif row.status=='PENDING':
                row.lease_until=now+timedelta(seconds=15);pending.append(row.id)
    # A process crash or unavailable broker here loses no task. The publication
    # lease expires and another sweep retries, without flooding every five seconds.
    if on_terminal:
        for task_id in terminal: on_terminal(task_id)
    for task_id in pending: publish(task_id)
    return len(pending)


def main():
    settings=Settings.from_env()
    engine=make_engine(settings);factory=make_session_factory(engine)
    redis=Redis.from_url(settings.redis_url,socket_connect_timeout=2,socket_timeout=2)
    try:
        while True:
            try: sweep(factory,on_terminal=lambda task_id:release(redis,task_id))
            except Exception: print('Scheduler dependency unavailable; retrying',flush=True)
            time.sleep(5)
    finally: redis.close();engine.dispose()


if __name__=='__main__': main()
