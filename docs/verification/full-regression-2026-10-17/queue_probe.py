import sys,json,time,base64,subprocess,urllib.request,urllib.error
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
sys.path.insert(0,str(Path.cwd()/'tests/browser'))
from check_live_attendance import server_python,GUARD,COMPOSE
assert COMPOSE[3]=='face-attendance-test-final'
ROOT=Path.cwd();OUT=Path(__file__).parent
local_open=urllib.request.build_opener(urllib.request.ProxyHandler({})).open
f=server_python(GUARD+"""
import json,base64
from sqlalchemy import func
from datetime import timedelta
from io import BytesIO
from uuid import uuid4
from PIL import Image
from app import clock
from app.services.attendance_sessions import create_session
with factory.begin() as db:
 assert db.scalar(select(func.count()).select_from(RecognitionTask).where(RecognitionTask.status.in_(['PENDING','RUNNING'])))==0
 marker='QUEUE'+uuid4().hex[:12]
 c=ClassRoom(name=marker);db.add(c);db.flush()
 t=User(student_no=marker+'T',name='Queue test teacher',role='ADMIN',status='ACTIVE',password_hash='unused')
 s=User(student_no=marker+'S',name='Queue test student',class_id=c.id,status='ACTIVE',password_hash='unused')
 db.add_all([t,s]);db.flush()
 row,_=create_session(db,t.id,marker,c.id,clock.utc_now()-timedelta(minutes=1),clock.utc_now()+timedelta(minutes=10));db.flush()
 result={'class_id':c.id,'ids':[t.id,s.id],'sid':row.id,'code':row.public_code,'marker':marker}
 buffer=BytesIO();Image.new('RGB',(640,640),'white').save(buffer,format='PNG');result['photo']=base64.b64encode(buffer.getvalue()).decode()
engine.dispose();print(json.dumps(result))
""")
photo=base64.b64decode(f.pop('photo'));rows=[];accepted=[]
def command(args):subprocess.run(COMPOSE+args,check=True,capture_output=True,timeout=50)
def post(_):
 boundary=uuid4().hex
 body=(f'--{boundary}\r\nContent-Disposition: form-data; name="session_code"\r\n\r\n{f["code"]}\r\n--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="blank.png"\r\nContent-Type: image/png\r\n\r\n').encode()+photo+f'\r\n--{boundary}--\r\n'.encode()
 start=time.monotonic()
 try:
  with local_open(urllib.request.Request('http://127.0.0.1:8001/api/checkins',data=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary,'Idempotency-Key':str(uuid4())}),timeout=15) as r:result={'http':r.status,'task':json.load(r)}
 except urllib.error.HTTPError as e:result={'http':e.code,'code':json.load(e)['error']['code']}
 result['ms']=round((time.monotonic()-start)*1000,2);return result
try:
 command(['stop','scheduler','worker'])
 with ThreadPoolExecutor(max_workers=10) as pool:rows=list(pool.map(post,range(60)))
 counts=dict(Counter(r['http'] for r in rows));assert counts=={202:50,503:10},counts
 assert all(r.get('code')=='QUEUE_FULL' for r in rows if r['http']==503)
 before=server_python(GUARD+f'sid={f["sid"]!r}\n'+"""
import json
from app.services.capacity import KEY
from redis import Redis
from sqlalchemy import func
r=Redis.from_url(settings.redis_url)
with factory() as db:
 result={'tasks':db.scalar(select(func.count()).select_from(RecognitionTask).where(RecognitionTask.session_id==sid)),'capacity':r.zcard(KEY),'files':len(list(settings.storage_dir.rglob('*.image')))}
r.close();engine.dispose();print(json.dumps(result))
""")
 assert before['tasks']==before['capacity']==50
 command(['start','worker','scheduler'])
 accepted=[r['task'] for r in rows if r['http']==202];results=[];deadline=time.monotonic()+45
 for task in accepted:
  while True:
   with local_open(urllib.request.Request('http://127.0.0.1:8001'+task['poll_url'],headers={'X-Task-Token':task['task_token']}),timeout=5) as response:result=json.load(response)
   if result['status'] in {'SUCCEEDED','REJECTED','FAILED'}:break
   assert time.monotonic()<deadline,'Queue drain exceeded bound'
   time.sleep(.1)
  results.append(result['result_code'])
 assert Counter(results)=={'NO_FACE':50}
 after=server_python(GUARD+"""
import json
from app.services.capacity import KEY
from redis import Redis
r=Redis.from_url(settings.redis_url);print(json.dumps({'capacity':r.zcard(KEY)}));r.close();engine.dispose()
""")
 assert after['capacity']==0
 report={'scope':'Real loopback HTTP, MySQL, Redis and ONNX; worker paused to hold backlog, then resumed; limits unchanged; not successful-human throughput','requests':60,'concurrent_clients':10,'http_counts':counts,'rejection_codes':{'QUEUE_FULL':10},'accepted_tasks':50,'terminal_codes':dict(Counter(results)),'capacity_before_drain':before['capacity'],'capacity_after_drain':after['capacity'],'drain_seconds':round(45-(deadline-time.monotonic()),2)}
 print(json.dumps(report,indent=2),flush=True)
finally:
 command(['start','worker','scheduler'])
 clean=server_python(GUARD+f'f={f!r}\n'+"""
import json
from app.services.uploads import stored_path
from app.services.capacity import release
from redis import Redis
paths=[];tids=[]
with factory.begin() as db:
 assert db.get(ClassRoom,f['class_id']).name==f['marker']
 assert all(db.get(User,uid).student_no.startswith(f['marker']) for uid in f['ids'])
 tasks=db.scalars(select(RecognitionTask).where(RecognitionTask.session_id==f['sid'])).all()
 assert all(t.status in {'SUCCEEDED','REJECTED','FAILED'} for t in tasks),'Do not remove active work'
 for t in tasks:
  tids.append(t.id)
  if t.image_path:paths.append(stored_path(settings.storage_dir,t.image_path))
 assert not db.scalar(select(AttendanceRecord.id).where(AttendanceRecord.session_id==f['sid']))
 db.execute(delete(RecognitionTask).where(RecognitionTask.session_id==f['sid']))
 db.execute(delete(SessionMember).where(SessionMember.session_id==f['sid']))
 db.execute(delete(AttendanceSession).where(AttendanceSession.id==f['sid']))
 db.execute(delete(User).where(User.id.in_(f['ids'])))
 db.execute(delete(ClassRoom).where(ClassRoom.id==f['class_id']))
for path in paths:path.unlink(missing_ok=True)
r=Redis.from_url(settings.redis_url)
for tid in tids:release(r,tid)
r.close();engine.dispose();print(json.dumps({'tasks_removed':len(tids),'cleanup':'complete'}))
""")
 print(clean,flush=True)
 if 'report' in globals():
  report['cleanup']=clean
  (OUT/'queue-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
