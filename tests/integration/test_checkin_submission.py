from io import BytesIO
from uuid import uuid4
from datetime import timedelta
from PIL import Image
from sqlalchemy import delete,select
from app import clock
from app.models import AttendanceSession,SessionMember,RecognitionTask
from app.services.attendance_sessions import create_session
from app.services.uploads import stored_path
from app.errors import AppError
from tests.integration.test_auth import accounts


def test_anonymous_submission_replay_after_close_and_identity_rejection(client,settings,accounts,monkeypatch):
    now=clock.utc_now();factory=accounts['factory'];key=str(uuid4())
    # Isolate reception rules from job execution; real worker is tested separately.
    monkeypatch.setattr('app.api.checkins.dispatch',lambda task_id:True)
    with factory.begin() as s:
        row,_=create_session(s,accounts['ids'][0],'时间验证',accounts['class_id'],now-timedelta(minutes=1),now+timedelta(minutes=5));s.flush();sid=row.id;code=row.public_code
    photo=BytesIO();Image.new('RGB',(100,100),'white').save(photo,format='PNG');content=photo.getvalue()
    try:
        response=client.post('/api/checkins',data={'session_code':code},files={'photo':('p.png',content)},headers={'Idempotency-Key':key})
        assert response.status_code==202,response.text
        first=response.json()
        conflict=client.post('/api/checkins',data={'session_code':code+'x'},files={'photo':('p.png',content)},headers={'Idempotency-Key':key})
        assert conflict.status_code==409
        assert client.get(first['poll_url']).status_code==404
        before=set(settings.storage_dir.rglob('*.image'))
        def full(*args):raise AppError('QUEUE_FULL','排队已满',503)
        with monkeypatch.context() as patch:
            patch.setattr('app.api.checkins.reserve',full)
            overloaded=client.post('/api/checkins',data={'session_code':code},files={'photo':('p.png',content)},headers={'Idempotency-Key':str(uuid4())})
            assert overloaded.status_code==503 and overloaded.json()['error']['code']=='QUEUE_FULL'
        assert set(settings.storage_dir.rglob('*.image'))==before
        with factory() as s:
            assert len(s.scalars(select(RecognitionTask).where(RecognitionTask.session_id==sid)).all())==1
        with factory.begin() as s:s.get(AttendanceSession,sid).closed_at=clock.utc_now()
        replay=client.post('/api/checkins',data={'session_code':code},files={'photo':('p.png',content)},headers={'Idempotency-Key':key})
        assert replay.status_code==202 and replay.json()['task_id']==first['task_id']
        late=client.post('/api/checkins',data={'session_code':code},files={'photo':('p.png',content)},headers={'Idempotency-Key':str(uuid4())})
        assert late.status_code==409 and late.json()['error']['code']=='SESSION_ENDED'
        forged=client.post('/api/checkins',data={'session_code':code,'user_id':str(accounts['ids'][1])},files={'photo':('p.png',content)},headers={'Idempotency-Key':str(uuid4())})
        assert forged.status_code==422
    finally:
        with factory.begin() as s:
            for task in s.scalars(select(RecognitionTask).where(RecognitionTask.session_id==sid)):
                stored_path(settings.storage_dir,task.image_path).unlink(missing_ok=True)
                client.app.state.redis.zrem('tasks:reservations',task.id)
            s.execute(delete(RecognitionTask).where(RecognitionTask.session_id==sid))
            s.execute(delete(SessionMember).where(SessionMember.session_id==sid))
            s.execute(delete(AttendanceSession).where(AttendanceSession.id==sid))
