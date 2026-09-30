"""Bounded real-model NO_FACE load probe against isolated localhost:8001 only.

Preserves rate limits. This measures blank-image rejection, not successful human
recognition throughput. It never targets the development or a public endpoint.
"""
import base64
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import time
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from uuid import uuid4
from scripts.test_redis_recovery import execute


def percentile(values,q):
    if not values:return None
    values=sorted(values);return round(values[min(len(values)-1,max(0,math.ceil(len(values)*q)-1))],2)


def main():
    cooldown=execute('''
from redis import Redis
redis=Redis.from_url(settings.redis_url)
delay=max([redis.ttl(key) for key in redis.scan_iter('rate:checkin:*')]+[0])
redis.close();engine.dispose();print(json.dumps(max(0,delay)))
''')
    if cooldown:
        print(f'Waiting {cooldown+1}s for existing test rate windows to expire (limits remain enabled)',flush=True)
        for _ in range(cooldown+1):time.sleep(1)
    fixture=execute('''
import base64,os,platform
from io import BytesIO
from datetime import timedelta
from uuid import uuid4
from PIL import Image
from app import clock
from app.models import User,ClassRoom,FaceSample
from sqlalchemy import select,func
from app.services.attendance_sessions import create_session
marker='LOAD'+uuid4().hex[:12]
with factory.begin() as db:
    classroom=ClassRoom(name=marker);db.add(classroom);db.flush()
    admin=User(student_no=marker+'A',name='load-test',role='ADMIN',status='ACTIVE',password_hash='unused')
    student=User(student_no=marker+'S',name='load-test',class_id=classroom.id,status='ACTIVE',password_hash='unused')
    db.add_all([admin,student]);db.flush()
    row,_=create_session(db,admin.id,marker,classroom.id,clock.utc_now()-timedelta(minutes=1),clock.utc_now()+timedelta(minutes=10));db.flush()
    result=dict(sid=row.id,code=row.public_code,ids=[admin.id,student.id],class_id=classroom.id,marker=marker,
                gallery_size=db.scalar(select(func.count()).select_from(FaceSample).where(FaceSample.status=='ACTIVE')),
                logical_cpus=os.cpu_count(),python=platform.python_version())
buffer=BytesIO();Image.new('RGB',(640,640),'white').save(buffer,format='PNG');result['photo']=base64.b64encode(buffer.getvalue()).decode()
engine.dispose();print(json.dumps(result))
''')
    photo=base64.b64decode(fixture.pop('photo'));rounds=[]
    def request_one(_):
        boundary=uuid4().hex
        body=(f'--{boundary}\r\nContent-Disposition: form-data; name="session_code"\r\n\r\n{fixture["code"]}\r\n'
              f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="blank.png"\r\nContent-Type: image/png\r\n\r\n').encode()+photo+f'\r\n--{boundary}--\r\n'.encode()
        start=time.perf_counter()
        req=Request('http://127.0.0.1:8001/api/checkins',data=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary,'Idempotency-Key':str(uuid4())})
        try:
            with urlopen(req,timeout=15) as response:task=json.load(response)
        except HTTPError as error:
            return {'http':error.code,'accept_ms':(time.perf_counter()-start)*1000}
        accepted=time.perf_counter();deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            poll=Request('http://127.0.0.1:8001'+task['poll_url'],headers={'X-Task-Token':task['task_token']})
            with urlopen(poll,timeout=5) as response:result=json.load(response)
            if result['status'] in {'SUCCEEDED','REJECTED','FAILED'}:
                return {'http':202,'result':result['result_code'],'accept_ms':(accepted-start)*1000,'end_ms':(time.perf_counter()-start)*1000}
            time.sleep(.1)
        raise RuntimeError('Stop load: task exceeded 30 seconds')
    try:
        for concurrency in [1,5,10,20]:
            start=time.perf_counter()
            with ThreadPoolExecutor(max_workers=concurrency) as pool:results=list(pool.map(request_one,range(concurrency)))
            elapsed=time.perf_counter()-start
            accepted=[r for r in results if r['http']==202]
            assert all(r['result']=='NO_FACE' for r in accepted), 'Unexpected model result'
            rounds.append({'concurrency':concurrency,'requests':concurrency,'seconds':round(elapsed,3),
                'http_counts':dict(Counter(r['http'] for r in results)),
                'terminal_counts':dict(Counter(r.get('result','HTTP_REJECTED') for r in results)),
                'accepted_latency_p50_ms':percentile([r['accept_ms'] for r in accepted],.5),
                'accepted_latency_p95_ms':percentile([r['accept_ms'] for r in accepted],.95),
                'end_to_end_p50_ms':percentile([r['end_ms'] for r in accepted],.5),
                'end_to_end_p95_ms':percentile([r['end_ms'] for r in accepted],.95),
                'completed_rejections_per_second':round(len(accepted)/elapsed,2)})
            if elapsed>30:break
        timings=execute(f'''
from sqlalchemy import select
with factory() as db:
    rows=db.scalars(select(RecognitionTask).where(RecognitionTask.session_id=={fixture['sid']})).all()
    result={{'queued_ms':[(r.started_at-r.received_at).total_seconds()*1000 for r in rows if r.started_at],
             'processing_ms':[(r.finished_at-r.started_at).total_seconds()*1000 for r in rows if r.finished_at and r.started_at]}}
engine.dispose();print(json.dumps(result))
''')
        report={'profile':'isolated real ONNX blank-image NO_FACE; not human throughput','image_bytes':len(photo),
                'worker_processes':1,'inference_threads':1,'model':'buffalo_l CPU','logical_cpus':fixture['logical_cpus'],
                'python':fixture['python'],'percentile_method':'nearest rank','valid_face_gallery_size':fixture['gallery_size'],'rate_limits_enabled':True,
                'rounds':rounds,'queue_p95_ms':percentile(timings['queued_ms'],.95),'processing_p95_ms':percentile(timings['processing_ms'],.95)}
        output=Path(__file__).resolve().parents[1]/'docs/verification/local-load.json'
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2))
    finally:
        execute(f'''
from sqlalchemy import select,delete
from app.models import AttendanceRecord,AttendanceSession,SessionMember,User,ClassRoom
from app.services.uploads import stored_path
from redis import Redis
from app.services.capacity import release
fixture={fixture!r}
paths=[];tasks=[]
with factory.begin() as db:
    assert db.get(ClassRoom,fixture['class_id']).name==fixture['marker']
    assert all(db.get(User,uid).student_no.startswith(fixture['marker']) for uid in fixture['ids'])
    for task in db.scalars(select(RecognitionTask).where(RecognitionTask.session_id==fixture['sid'])):
        assert task.status in {'SUCCEEDED','REJECTED','FAILED'},'Keep active test task until it finishes'
        if task.image_path:paths.append(stored_path(settings.storage_dir,task.image_path))
        tasks.append(task.id)
    assert db.scalar(select(AttendanceRecord.id).where(AttendanceRecord.session_id==fixture['sid'])) is None
    db.execute(delete(RecognitionTask).where(RecognitionTask.session_id==fixture['sid']))
    db.execute(delete(SessionMember).where(SessionMember.session_id==fixture['sid']))
    db.execute(delete(AttendanceSession).where(AttendanceSession.id==fixture['sid']))
    db.execute(delete(User).where(User.id.in_(fixture['ids'])))
    db.execute(delete(ClassRoom).where(ClassRoom.id==fixture['class_id']))
for path in paths:path.unlink(missing_ok=True)
redis=Redis.from_url(settings.redis_url)
for task_id in tasks:release(redis,task_id)
redis.close();engine.dispose();print(json.dumps(True))
''')


if __name__=='__main__':main()
