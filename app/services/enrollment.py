from sqlalchemy import select
import numpy as np
from app import clock
from app.models import User
from app.models.tasks import RecognitionTask
from app.models.faces import FaceSample,FaceLibraryState
from app.face.types import FaceError,FaceFeature
from app.face.matcher import Candidate,match_face
from app.services.retry import retry_transaction


@retry_transaction
def finish_enrollment(factory,task_id,attempt,feature,threshold=0.5):
    with factory.begin() as session:
        state=session.scalar(select(FaceLibraryState).where(FaceLibraryState.id==1).with_for_update())
        task=session.scalar(select(RecognitionTask).where(RecognitionTask.id==task_id).with_for_update())
        if not task or task.status!='RUNNING' or task.attempt_id!=attempt or task.expires_at<=clock.utc_now(): return
        user=session.scalar(select(User).where(User.id==task.owner_user_id).with_for_update())
        if not user or user.status=='DISABLED': raise FaceError('USER_UNAVAILABLE')
        if task.type=='ENROLL' and user.status!='PENDING': raise FaceError('ALREADY_ENROLLED')
        # The gallery lock also serializes concurrent enrolments. Check other
        # identities in this transaction, before replacing any existing photo.
        other_faces=session.scalars(select(FaceSample).join(User).where(
            FaceSample.status=='ACTIVE',User.status=='ACTIVE',FaceSample.user_id!=user.id,
            FaceSample.model_version==feature.model_version)).all()
        candidates=[Candidate(face.user_id,FaceFeature(np.frombuffer(face.embedding,dtype='<f4'),face.model_version,0)) for face in other_faces]
        try:match_face(feature,candidates,threshold,0)
        except FaceError as error:
            if error.code!='UNKNOWN_PERSON':raise
        else:raise FaceError('FACE_ALREADY_ENROLLED')
        replace_id=task.payload.get('replace_id')
        if replace_id:
            old=session.scalar(select(FaceSample).where(FaceSample.id==replace_id).with_for_update())
            if not old or old.user_id!=user.id or old.status!='ACTIVE': raise FaceError('PHOTO_CHANGED')
            old.status='DISABLED'
        session.add(FaceSample(user_id=user.id,image_path=task.image_path,embedding=feature.embedding.astype('<f4').tobytes(),
            dimension=512,dtype='float32-le',model_version=feature.model_version,status='ACTIVE'))
        if task.type=='ENROLL': user.status='ACTIVE'
        state.version+=1;state.updated_at=clock.utc_now()
        task.status='SUCCEEDED';task.result_code='ENROLLED' if task.type=='ENROLL' else 'FACE_SAVED';task.finished_at=clock.utc_now()
