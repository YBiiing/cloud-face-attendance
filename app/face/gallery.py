import numpy as np
from sqlalchemy import select
from app.models import User
from app.models.faces import FaceSample, FaceLibraryState
from app.face.types import FaceFeature
from app.face.matcher import Candidate


class Gallery:
    def __init__(self): self.version=-1;self.candidates=[]

    def load(self,factory):
        # Both reads share one MySQL REPEATABLE READ snapshot.
        with factory() as session:
            version=session.scalar(select(FaceLibraryState.version).where(FaceLibraryState.id==1))
            if version==self.version: return version,self.candidates
            rows=session.scalars(select(FaceSample).join(User).where(FaceSample.status=='ACTIVE',User.status=='ACTIVE')).all()
            candidates=[]
            for row in rows:
                if row.dimension!=512 or row.dtype!='float32-le' or len(row.embedding)!=2048:
                    raise RuntimeError('Invalid stored feature')
                vector=np.frombuffer(row.embedding,dtype='<f4').copy()
                candidates.append(Candidate(row.user_id,FaceFeature(vector,row.model_version,0)))
        self.version=version;self.candidates=candidates
        return version,candidates
