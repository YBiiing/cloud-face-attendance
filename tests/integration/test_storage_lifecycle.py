from datetime import timedelta
import os
from uuid import uuid4
import numpy as np
from sqlalchemy import delete
from app import clock
from app.models import FaceSample,RecognitionTask
from app.services.tasks import new_task
from app.services.storage_lifecycle import cleanup
from tests.integration.test_auth import accounts


def test_cleanup_protects_active_running_recent_and_unmanaged(settings,accounts,tmp_path):
    factory=accounts['factory'];root=tmp_path;uploads=root/'uploads';uploads.mkdir()
    old=(clock.utc_now()-timedelta(days=3)).timestamp();ids=[];paths=[]
    try:
        for _ in range(5):
            path=uploads/(uuid4().hex+'.image');path.write_bytes(b'test-only');os.utime(path,(old,old));paths.append(path)
        unmanaged=uploads/'keep-me.txt';unmanaged.write_text('untouched')
        recent=uploads/(uuid4().hex+'.image');recent.write_bytes(b'recent')
        with factory.begin() as db:
            db.add(FaceSample(user_id=accounts['ids'][1],image_path='uploads/'+paths[0].name,embedding=np.zeros(512,dtype='<f4').tobytes(),model_version='test'))
            for n in range(1,4):
                task=new_task(settings.app_secret,'cleanup-test',str(uuid4()),uuid4().hex,'CHECKIN',image_path='uploads/'+paths[n].name)
                task.status='RUNNING' if n==1 else 'REJECTED'
                task.finished_at=clock.utc_now()-timedelta(days=2) if n==2 else clock.utc_now()
                db.add(task);ids.append(task.id)
        preview=cleanup(factory,root)
        assert set(preview['eligible'])=={'uploads/'+paths[n].name for n in [2,4]}
        assert all(path.exists() for path in paths)
        applied=cleanup(factory,root,apply=True)
        assert len(applied['removed'])==2
        assert all(paths[n].exists() for n in [0,1,3]) and recent.exists() and unmanaged.exists()
        with factory() as db:assert db.get(RecognitionTask,ids[1]).image_path is None
        assert not cleanup(factory,root,apply=True)['removed']
    finally:
        with factory.begin() as db:
            db.execute(delete(RecognitionTask).where(RecognitionTask.id.in_(ids)))
            db.execute(delete(FaceSample).where(FaceSample.user_id==accounts['ids'][1]))
