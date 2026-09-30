"""Host-side fault probe: only the isolated face-attendance-test Compose project."""
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
COMPOSE=['docker','compose','-p','face-attendance-test','-f','compose.yaml','-f','compose.test.yaml']
GUARD='''
import json
from app.config import Settings
from app.database import make_engine,make_session_factory
from app.models import RecognitionTask
settings=Settings.from_env()
assert settings.environment=='test' and settings.mysql_database=='face_attendance_test'
engine=make_engine(settings);factory=make_session_factory(engine)
'''


def command(args):
    subprocess.run(COMPOSE+args,cwd=ROOT,check=True,stdout=subprocess.DEVNULL)


def execute(code):
    result=subprocess.run(COMPOSE+['run','--rm','--no-deps','-T','api','python','-'],input=GUARD+code,
                          encoding='utf-8',cwd=ROOT,capture_output=True,timeout=45)
    if result.returncode:raise RuntimeError('Fault probe command failed: '+result.stderr[-1000:])
    return json.loads(result.stdout)


def main():
    task_id=execute('''
from uuid import uuid4
from app.services.tasks import new_task
with factory.begin() as db:
    task=new_task(settings.app_secret,'redis-outage-probe',str(uuid4()),uuid4().hex,'PING');db.add(task);task_id=task.id
engine.dispose();print(json.dumps(task_id))
''')
    try:
        command(['stop','redis'])
        delivered=execute(f'''from app.services.tasks import dispatch
print(json.dumps(dispatch({task_id!r})))
engine.dispose()
''')
        assert delivered is False
        command(['up','-d','--wait','redis'])
        report=execute(f'''
import time
from app.jobs.scheduler import sweep
from app.services.tasks import dispatch
sweep(factory)
deadline=time.monotonic()+25
while time.monotonic()<deadline:
    with factory() as db:
        row=db.get(RecognitionTask,{task_id!r});status=row.status;attempts=row.attempts
    if status=='SUCCEEDED':break
    time.sleep(.2)
assert status=='SUCCEEDED' and attempts==1
engine.dispose();print(json.dumps({{'status':status,'attempts':attempts}}))
''')
        print('PASS: Redis unavailable -> dispatch false -> restart -> DB sweep -> real Celery success; attempts='+str(report['attempts']))
    finally:
        command(['up','-d','--wait','redis'])
        execute(f'''
with factory.begin() as db:
    task=db.get(RecognitionTask,{task_id!r})
    if task:
        assert task.scope=='redis-outage-probe'
        db.delete(task)
engine.dispose();print(json.dumps(True))
''')


if __name__=='__main__':main()
