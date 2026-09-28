from io import BytesIO
from uuid import uuid4
import time
import numpy as np
from PIL import Image
from sqlalchemy import select,delete
from app.models import FaceSample,FaceLibraryState,RecognitionTask
from app.face.gallery import Gallery
from app.services.uploads import stored_path
from tests.integration.test_auth import accounts,sign_in


def test_private_faces_failed_replacement_and_cache(client,settings,accounts):
    owner=accounts['ids'][1];factory=accounts['factory'];relative='uploads/'+uuid4().hex+'.image'
    file=stored_path(settings.storage_dir,relative);file.parent.mkdir(parents=True,exist_ok=True)
    data=BytesIO();Image.new('RGB',(640,640),'white').save(data,format='PNG');file.write_bytes(data.getvalue())
    with factory.begin() as s:
        state=s.get(FaceLibraryState,1,with_for_update=True);state.version+=1
        sample=FaceSample(user_id=owner,image_path=relative,embedding=(np.ones(512,dtype='<f4')/np.sqrt(512)).tobytes(),dimension=512,dtype='float32-le',model_version='test')
        s.add(sample);s.flush();face_id=sample.id
    caches=[Gallery(),Gallery()]
    try:
        assert client.get(f'/api/faces/{face_id}/image').status_code==401
        headers=sign_in(client,accounts,'student')
        assert client.get('/api/faces',params={'user_id':accounts['ids'][0]}).status_code==404
        image=client.get(f'/api/faces/{face_id}/image')
        assert image.status_code==200 and image.headers['cache-control']=='private, no-store'
        assert client.get('/api/faces').json()['total']==1
        for cache in caches: assert any(c.user_id==owner for c in cache.load(factory)[1])
        result=client.post('/api/faces',data={'replace_id':str(face_id)},files={'photo':('blank.png',data.getvalue())},headers={**headers,'Idempotency-Key':str(uuid4())})
        assert result.status_code==202,result.text
        task=result.json();deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            result=client.get(task['poll_url'],headers={'X-Task-Token':task['task_token']}).json()
            if result['status'] in {'REJECTED','FAILED','SUCCEEDED'}:break
            time.sleep(.2)
        assert result['status']=='REJECTED' and result['result_code']=='NO_FACE'
        assert client.get('/api/faces').json()['total']==1
        assert client.delete(f'/api/faces/{face_id}',headers=headers).status_code==204
        assert client.get('/api/faces').json()['total']==0
        for cache in caches: assert not any(c.user_id==owner for c in cache.load(factory)[1])
        assert client.get(f'/api/faces/{face_id}/image').status_code==404
    finally:
        with factory.begin() as s:
            state=s.get(FaceLibraryState,1,with_for_update=True);state.version+=1
            for task in s.scalars(select(RecognitionTask).where(RecognitionTask.owner_user_id==owner)):
                if task.image_path:stored_path(settings.storage_dir,task.image_path).unlink(missing_ok=True)
            s.execute(delete(RecognitionTask).where(RecognitionTask.owner_user_id==owner))
            s.execute(delete(FaceSample).where(FaceSample.user_id==owner))
        file.unlink(missing_ok=True)
