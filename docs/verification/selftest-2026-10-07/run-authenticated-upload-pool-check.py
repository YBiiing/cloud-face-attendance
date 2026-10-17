"""Real test DB regression: ten authenticated uploads must not exhaust the pool.

Requires isolated test MySQL, Redis and worker. Uses a scheduling barrier, not
model/rate-limit mocks. Writes evidence to .tmp and cleans only its own fixture.
Current known bug produces exit code 1. Never run against production.
"""
import json,subprocess,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'.tmp'/('pool-check-'+uuid4().hex[:12]);OUT.mkdir(parents=True)
sys.path.insert(0,str(ROOT/'tests/browser'))
from check_live_attendance import GUARD,COMPOSE
code=GUARD+'''
import json,sys,time
from threading import Barrier,Lock,Event
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from io import BytesIO
from uuid import uuid4
from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy.exc import TimeoutError
from app.main import create_app
from app.api import faces
from app.observability import logger
from app.models import FaceSample
from app.security import hash_password
from app.services.uploads import stored_path
from app.services.capacity import release
from redis import Redis
marker='POOL'+uuid4().hex[:12]
with factory.begin() as db:
 c=ClassRoom(name='Pool check '+marker);db.add(c);db.flush()
 u=User(student_no=marker,name='No-face pool fixture',class_id=c.id,status='ACTIVE',password_hash=hash_password('abc123'));db.add(u);db.flush();uid=u.id;cid=c.id
entered=Event();gate=Barrier(10,action=entered.set);lock=Lock();seen=[];peak=[];original=faces.face_transaction;original_error=logger.error;app=create_app(settings)
def scheduled(*args,**kwargs):
 with lock:peak.append(app.state.engine.pool.checkedout())
 gate.wait(timeout=15)
 return original(*args,**kwargs)
def diagnostic(*args,**kwargs):
 exc=sys.exc_info()[1]
 with lock:seen.append({'exception_type':type(exc).__name__,'is_queue_pool_timeout':isinstance(exc,TimeoutError) and 'QueuePool limit' in str(exc)})
 original_error(*args,**kwargs)
faces.face_transaction=scheduled;logger.error=diagnostic
buf=BytesIO();Image.new('RGB',(640,640),'white').save(buf,format='PNG');pixels=buf.getvalue();paths=[];tids=[]
try:
 with TestClient(app) as client:
  login=client.post('/api/auth/login',json={'student_no':marker,'password':'abc123'});assert login.status_code==200
  csrf=login.json()['csrf_token']
  def submit(_):
   r=client.post('/api/faces',files={'photo':('blank.png',pixels,'image/png')},headers={'X-CSRF-Token':csrf,'Idempotency-Key':str(uuid4())})
   return {'status':r.status_code,'code':r.json().get('error',{}).get('code')}
  def health(path):
   started=time.monotonic();r=client.get(path)
   return {'status':r.status_code,'duration_ms':round((time.monotonic()-started)*1000,1)}
  with ThreadPoolExecutor(max_workers=12) as pool:
   futures=[pool.submit(submit,i) for i in range(10)];assert entered.wait(15)
   live=pool.submit(health,'/api/health/live');ready=pool.submit(health,'/api/health/ready')
   rows=[future.result() for future in futures];health_results={'live':live.result(),'ready':ready.result()}
 result={'scope':'Actual FastAPI/MySQL/Redis, in-process TestClient; scheduling barrier only; blank PNG; no model or rate-limit mocks','http_counts':dict(Counter(r['status'] for r in rows)),'exceptions':seen,'pool_checkedout_peak':max(peak),'pool_size':app.state.engine.pool.size(),'max_overflow':app.state.engine.pool._max_overflow,'pool_timeout_seconds':app.state.engine.pool._timeout,'health_during_pool_contention':health_results}
finally:
 faces.face_transaction=original;logger.error=original_error
 deadline=time.monotonic()+40
 while True:
  with factory() as db:tasks=list(db.scalars(select(RecognitionTask).where(RecognitionTask.owner_user_id==uid)))
  if all(t.status in ('SUCCEEDED','REJECTED','FAILED') for t in tasks):break
  assert time.monotonic()<deadline,'Leave active jobs intact for diagnosis'
  time.sleep(.2)
 with factory.begin() as db:
  assert db.get(ClassRoom,cid).name=='Pool check '+marker and db.get(User,uid).student_no==marker
  assert not list(db.scalars(select(FaceSample).where(FaceSample.user_id==uid)))
  for t in db.scalars(select(RecognitionTask).where(RecognitionTask.owner_user_id==uid)):
   assert t.status in ('SUCCEEDED','REJECTED','FAILED');tids.append(t.id)
   if t.image_path:paths.append(t.image_path)
  db.execute(delete(RecognitionTask).where(RecognitionTask.id.in_(tids)))
  db.execute(delete(LoginSession).where(LoginSession.user_id==uid))
  db.delete(db.get(User,uid));db.delete(db.get(ClassRoom,cid))
 for path in paths:stored_path(settings.storage_dir,path).unlink(missing_ok=True)
 r=Redis.from_url(settings.redis_url)
 for tid in tids:release(r,tid)
 r.close();engine.dispose()
result['cleanup']='complete';print(json.dumps(result))
'''
r=subprocess.run(COMPOSE+['run','--rm','--no-deps','-T','tests','python','-'],input=code,cwd=ROOT,capture_output=True,encoding='utf-8')
if r.returncode:raise RuntimeError('Isolated diagnostic failed: '+r.stderr[-900:])
result=json.loads(r.stdout);output=OUT/'results.json';output.write_text(json.dumps(result,indent=2),encoding='utf-8')
print('Evidence: '+str(output));print('HTTP counts: '+json.dumps(result['http_counts']))
if result['http_counts']!={'202':10} or result['exceptions']:raise SystemExit(1)
