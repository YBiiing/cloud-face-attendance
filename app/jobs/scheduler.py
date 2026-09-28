import time
from sqlalchemy import select
from app import clock
from app.config import Settings
from app.database import make_engine,make_session_factory
from app.models.tasks import RecognitionTask
from app.services.tasks import dispatch


def sweep(factory):
    now=clock.utc_now()
    with factory.begin() as session:
        rows=session.scalars(select(RecognitionTask).where(RecognitionTask.status.in_(['PENDING','RUNNING'])).with_for_update(skip_locked=True)).all()
        pending=[]
        for row in rows:
            lease_expired = row.status=='RUNNING' and row.lease_until and row.lease_until<=now
            if row.expires_at<=now or (row.attempts>=3 and (row.status=='PENDING' or lease_expired)):
                row.status='FAILED';row.result_code='TASK_TIMEOUT';row.finished_at=now
            elif lease_expired:
                row.status='PENDING';row.attempt_id=None;pending.append(row.id)
            elif row.status=='PENDING': pending.append(row.id)
    for task_id in pending: dispatch(task_id)


def main():
    engine=make_engine(Settings.from_env());factory=make_session_factory(engine)
    try:
        while True:
            try: sweep(factory)
            except Exception: print('Scheduler dependency unavailable; retrying',flush=True)
            time.sleep(5)
    finally: engine.dispose()


if __name__=='__main__': main()
