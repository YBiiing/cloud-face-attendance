"""Kill a Linux process in the real worker function, then recover via Celery."""
from datetime import timedelta
from io import BytesIO
import subprocess
import sys
import time
from uuid import uuid4
from PIL import Image
import pytest
from sqlalchemy import delete
from app import clock
from app.models import RecognitionTask
from app.jobs.scheduler import sweep
from app.services.tasks import new_task,dispatch
from app.services.uploads import stored_path
from app.database import make_engine,make_session_factory


@pytest.mark.parametrize('crash_point',['extraction','before_commit'])
def test_crash_after_claim_and_after_commit(settings,crash_point):
    engine=make_engine(settings);factory=make_session_factory(engine);ids=[]
    relative='uploads/'+uuid4().hex+'.image';path=stored_path(settings.storage_dir,relative)
    path.parent.mkdir(parents=True,exist_ok=True);image=BytesIO();Image.new('RGB',(640,640),'white').save(image,format='PNG');path.write_bytes(image.getvalue())
    try:
        with factory.begin() as db:
            task=new_task(settings.app_secret,'process-loss',str(uuid4()),uuid4().hex,'ENROLL',image_path=relative)
            db.add(task);ids.append(task.id)
        # Only this child replaces extraction with an abrupt process exit. It
        # reaches extraction through the actual committed RUNNING transition.
        if crash_point=='extraction':
            hook="worker.get_engine=lambda:SimpleNamespace(extract=lambda image:os._exit(23));"
        else:
            hook="worker.get_engine=lambda:SimpleNamespace(extract=lambda image:None);worker.finish_enrollment=lambda *args:os._exit(23);"
        code="import os;from app.jobs import worker;from types import SimpleNamespace;"+hook+"worker.process("+repr(ids[0])+")"
        result=subprocess.run([sys.executable,'-c',code],timeout=25,capture_output=True)
        assert result.returncode==23
        with factory.begin() as db:
            row=db.get(RecognitionTask,ids[0]);assert row.status=='RUNNING' and row.attempts==1
            row.lease_until=clock.utc_now()-timedelta(seconds=1)
        sweep(factory)
        deadline=time.monotonic()+40
        while time.monotonic()<deadline:
            with factory() as db:
                row=db.get(RecognitionTask,ids[0]);status=row.status
            if status in {'SUCCEEDED','REJECTED','FAILED'}:break
            time.sleep(.2)
        with factory() as db:
            row=db.get(RecognitionTask,ids[0]);assert (row.status,row.result_code,row.attempts)==('REJECTED','NO_FACE',2)
        with factory.begin() as db:
            task=new_task(settings.app_secret,'post-commit-loss',str(uuid4()),uuid4().hex,'PING');db.add(task);ids.append(task.id)
        result=subprocess.run([sys.executable,'-c',"import os;from app.jobs.worker import process;process("+repr(ids[1])+");os._exit(24)"],timeout=25,capture_output=True)
        assert result.returncode==24
        assert dispatch(ids[1])
        # Synchronous duplicate and actual broker delivery both share the same guard.
        from app.jobs.worker import process
        process(ids[1])
        with factory() as db:
            row=db.get(RecognitionTask,ids[1]);assert row.status=='SUCCEEDED' and row.attempts==1
    finally:
        with factory.begin() as db:db.execute(delete(RecognitionTask).where(RecognitionTask.id.in_(ids)))
        path.unlink(missing_ok=True);engine.dispose()
