import numpy as np
from sqlalchemy import delete
from app.face.types import FaceFeature
from app.face.matcher import Match
from app.jobs.checkin import recognize_checkin
from app.models import FaceSample,FaceLibraryState,RecognitionTask,AttendanceRecord
from app.services.attendance import finish_checkin
from tests.integration.test_auth import accounts
from tests.integration.test_attendance import attendance,running_task


def test_deleted_feature_cannot_commit_stale_identity(attendance,settings):
    factory=attendance['factory'];owner=attendance['ids'][1];vector=np.zeros(512,dtype='<f4');vector[0]=1
    with factory.begin() as db:
        face=FaceSample(user_id=owner,image_path='uploads/unused.image',embedding=vector.tobytes(),model_version='version-test');db.add(face);db.flush();fid=face.id
        state=db.get(FaceLibraryState,1,with_for_update=True);state.version+=1;old_version=state.version
    task=running_task(factory,settings,attendance['sid'])
    # Delete commits while the worker still holds a match from the old snapshot.
    with factory.begin() as db:
        state=db.get(FaceLibraryState,1,with_for_update=True)
        db.get(FaceSample,fid).status='DISABLED';state.version+=1
    assert finish_checkin(factory,*task,old_version,Match(owner,1),None,'version-test') is False
    recognize_checkin(factory,*task,FaceFeature(vector,'version-test',100),settings)
    with factory() as db:
        assert db.get(RecognitionTask,task[0]).result_code=='UNKNOWN_PERSON'
        assert db.query(AttendanceRecord).filter_by(session_id=attendance['sid']).count()==0
