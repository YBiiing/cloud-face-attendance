import os
from pathlib import Path
from io import BytesIO
from uuid import uuid4
import numpy as np
from PIL import Image
import pytest
from sqlalchemy import select
from app.models import FaceSample,FaceLibraryState
from app.face.matcher import Match
from app.services.attendance import finish_checkin
from app.services.uploads import stored_path
from scripts.backup_data import export_bundle,restore_bundle
from tests.integration.test_auth import accounts
from tests.integration.test_attendance import attendance,running_task


def test_backup_export_and_refuse_nonempty_restore(attendance,settings,tmp_path):
    factory=attendance['factory'];relative='uploads/'+uuid4().hex+'.image'
    path=stored_path(settings.storage_dir,relative);path.parent.mkdir(exist_ok=True,parents=True)
    image=BytesIO();Image.new('RGB',(100,100),'white').save(image,format='PNG');path.write_bytes(image.getvalue())
    vector=np.zeros(512,dtype='<f4');vector[0]=1
    try:
        with factory.begin() as db:
            db.add(FaceSample(user_id=attendance['ids'][1],image_path=relative,embedding=vector.tobytes(),model_version='backup-test'))
            state=db.get(FaceLibraryState,1,with_for_update=True);state.version+=1;version=state.version
        task=running_task(factory,settings,attendance['sid'])
        finish_checkin(factory,*task,version,Match(attendance['ids'][1],.9),None,'backup-test')
        destination=Path(os.environ.get('BACKUP_TEST_OUTPUT',str(tmp_path/'backup.zip')))
        report=export_bundle(factory,settings.storage_dir,destination)
        assert report['photos']==1 and report['rows']>=8
        original=destination.read_bytes()
        with pytest.raises(FileExistsError):export_bundle(factory,settings.storage_dir,destination)
        assert destination.read_bytes()==original
        with pytest.raises(ValueError,match='database'):
            restore_bundle(factory,tmp_path/'empty-storage',destination,settings)
        with factory() as db:
            assert db.scalar(select(FaceSample).where(FaceSample.user_id==attendance['ids'][1])).embedding==vector.tobytes()
    finally:path.unlink(missing_ok=True)
