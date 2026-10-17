"""AI fictional faces, real ONNX and HTTP; not human accuracy/phone acceptance."""
import sys,json,time,urllib.request,math,statistics
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'.tmp'/('synthetic-face-'+uuid4().hex[:12]);OUT.mkdir(parents=True);SAMPLES=ROOT/'private-samples/synthetic-20261007'
sys.path.insert(0,str(ROOT/'tests/browser'))
from check_live_attendance import server_python,GUARD
marker='AI'+uuid4().hex[:12];base='http://127.0.0.1:8001'
f=server_python(GUARD+f'marker={marker!r}\n'+'''
import json
from sqlalchemy import func
from app.models import FaceSample
from app.security import hash_password
with factory.begin() as db:
 assert db.scalar(select(func.count()).select_from(FaceSample).where(FaceSample.status=='ACTIVE'))==0,'Use a gallery without unrelated face fixtures'
 c=ClassRoom(name='AI fictional faces '+marker);db.add(c);db.flush()
 a=User(student_no=marker+'T',name='AI测试老师',role='ADMIN',status='ACTIVE',password_hash=hash_password('abc123'));db.add(a);db.flush()
 result={'marker':marker,'class_id':c.id,'admin_id':a.id,'admin_no':a.student_no,'student_no':marker+'S','peer_no':marker+'B','threshold':settings.match_threshold,'margin':settings.match_margin}
engine.dispose();print(json.dumps(result))
''')
(OUT/'ai-fixture.json').write_text(json.dumps(f),encoding='utf-8')
evidence={'scope':'AI fictional faces only; not human acceptance','model_mocked':False,'match_threshold_changed':False,'results':[]}
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(channel='msedge',headless=True)
  student=browser.new_page(viewport={'width':390,'height':844});errors=[]
  student.on('pageerror',lambda e:errors.append(str(e)))
  student.goto(base+'/register.html');student.locator('[name=name]').fill('AI合成身份A')
  student.locator('[name=student_no]').fill(f['student_no']);student.locator('[name=class_id]').select_option(str(f['class_id']));student.locator('[name=password]').fill('abc123')
  student.locator('[name=photo]').set_input_files(SAMPLES/'person-a-standard.png');student.locator('#submit').click()
  expect(student.locator('#message')).to_have_text('注册成功，可以登录了',timeout=45000)
  student.screenshot(path=str(OUT/'ai-registration-success.png'),full_page=True);evidence['results'].append('ENROLLED');print('PASS AI fictional A enrolled by real model',flush=True)
  student.goto(base+'/login.html');student.locator('[name=student_no]').fill(f['student_no']);student.locator('[name=password]').fill('abc123');student.locator('#login-form button').click();expect(student).to_have_url(base+'/dashboard.html')
  teacher=browser.new_page(viewport={'width':390,'height':844});teacher.goto(base+'/login.html');teacher.locator('[name=student_no]').fill(f['admin_no']);teacher.locator('[name=password]').fill('abc123');teacher.locator('#login-form button').click();expect(teacher).to_have_url(base+'/dashboard.html')
  teacher.goto(base+'/session-create.html');teacher.locator('[name=title]').fill('AI合成样本自动化测试');teacher.locator('[name=class_id]').select_option(str(f['class_id']))
  with teacher.expect_response(lambda r:r.url.endswith('/api/sessions') and r.request.method=='POST') as created:teacher.get_by_role('button',name='发布签到',exact=True).click()
  assert created.value.status==201
  expect(teacher).to_have_url(base+'/sessions.html?created=1')
  listed=teacher.request.get(base+'/api/sessions?class_id='+str(f['class_id']));assert listed.status==200
  sessions=listed.json()['items'];assert len(sessions)==1;session=sessions[0];assert session['expected_count']==1
  f['session_id']=session['id'];f['code']=session['public_code'];(OUT/'ai-fixture.json').write_text(json.dumps(f),encoding='utf-8')
  anon=browser.new_page(viewport={'width':390,'height':844});anon.goto(base+session['checkin_path']);expect(anon.locator('#checkin-form')).to_be_visible()
  assert not anon.context.cookies()
  anon.locator('[name=photo]').set_input_files(SAMPLES/'person-a-checkin.png');anon.locator('#submit').click();expect(anon.locator('#message')).to_have_text('签到成功',timeout=45000)
  assert not anon.context.cookies();anon.screenshot(path=str(OUT/'ai-checkin-success.png'),full_page=True);evidence['results'].append('CHECKED_IN');print('PASS different AI A portrait CHECKED_IN anonymously',flush=True)
  anon.locator('#submit').click();expect(anon.locator('#message')).to_have_text('本场次已签到',timeout=45000);evidence['results'].append('ALREADY_CHECKED_IN')
  anon.locator('[name=photo]').set_input_files(SAMPLES/'person-b-unknown.png');anon.locator('#submit').click();expect(anon.locator('#message')).to_have_text('未识别到已录入人员',timeout=45000)
  anon.screenshot(path=str(OUT/'ai-unknown-person.png'),full_page=True);evidence['results'].append('UNKNOWN_PERSON');print('PASS AI B UNKNOWN_PERSON, no identity supplied',flush=True)
  peer=browser.new_page(viewport={'width':390,'height':844});peer.goto(base+'/register.html');peer.locator('[name=name]').fill('AI合成身份B');peer.locator('[name=student_no]').fill(f['peer_no']);peer.locator('[name=class_id]').select_option(str(f['class_id']));peer.locator('[name=password]').fill('abc123');peer.locator('[name=photo]').set_input_files(SAMPLES/'person-b-unknown.png');peer.locator('#submit').click();expect(peer.locator('#message')).to_have_text('注册成功，可以登录了',timeout=45000);evidence['results'].append('ENROLLED')
  peer.goto(base+'/login.html');peer.locator('[name=student_no]').fill(f['peer_no']);peer.locator('[name=password]').fill('abc123');peer.locator('#login-form button').click();expect(peer).to_have_url(base+'/dashboard.html');expect(peer.locator('#session-list')).not_to_contain_text('AI合成样本自动化测试')
  anon.locator('#submit').click();expect(anon.locator('#message')).to_have_text('你不在本场次签到名单中',timeout=45000);evidence['results'].append('NOT_IN_ROSTER');print('PASS registered AI B matched full gallery but rejected by frozen old roster',flush=True)
  teacher.goto(base+'/session-create.html');teacher.locator('[name=title]').fill('AI第二场自动化测试');teacher.locator('[name=class_id]').select_option(str(f['class_id']))
  with teacher.expect_response(lambda r:r.url.endswith('/api/sessions') and r.request.method=='POST') as created2:teacher.get_by_role('button',name='发布签到',exact=True).click()
  assert created2.value.status==201;expect(teacher).to_have_url(base+'/sessions.html?created=1')
  sessions2=teacher.request.get(base+'/api/sessions?class_id='+str(f['class_id'])).json()['items'];assert len(sessions2)==2
  second=next(row for row in sessions2 if row['title']=='AI第二场自动化测试');assert second['expected_count']==2
  f['second_session_id']=second['id'];(OUT/'ai-fixture.json').write_text(json.dumps(f),encoding='utf-8')
  peer.reload();expect(peer.locator('#session-list')).to_contain_text('AI第二场自动化测试')
  anon.goto(base+second['checkin_path']);anon.locator('[name=photo]').set_input_files(SAMPLES/'person-a-checkin.png');anon.locator('#submit').click();expect(anon.locator('#message')).to_have_text('签到成功',timeout=45000);evidence['results'].append('CHECKED_IN')
  anon.locator('[name=photo]').set_input_files(SAMPLES/'person-b-unknown.png');anon.locator('#submit').click();expect(anon.locator('#message')).to_have_text('签到成功',timeout=45000);evidence['results'].append('CHECKED_IN');print('PASS two people in new roster and same AI A checks into second session on same day',flush=True)
  csrf=teacher.request.get(base+'/api/me').json()['csrf_token'];now=datetime.now(timezone.utc)
  burst_response=teacher.request.post(base+'/api/sessions',headers={'X-CSRF-Token':csrf},data={'title':'AI并发重复签到测试','class_id':f['class_id'],'starts_at':(now-timedelta(minutes=1)).isoformat(),'ends_at':(now+timedelta(minutes=10)).isoformat()})
  assert burst_response.status==201;burst_session=burst_response.json();assert burst_session['expected_count']==2
  f['third_session_id']=burst_session['id'];(OUT/'ai-fixture.json').write_text(json.dumps(f),encoding='utf-8')
  pixels=(SAMPLES/'person-a-checkin.png').read_bytes()
  def concurrent_photo(_):
   boundary=uuid4().hex;start=time.monotonic()
   body=f'--{boundary}\r\nContent-Disposition: form-data; name="session_code"\r\n\r\n{burst_session["public_code"]}\r\n--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="ai-a.png"\r\nContent-Type: image/png\r\n\r\n'.encode()+pixels+f'\r\n--{boundary}--\r\n'.encode()
   with urllib.request.urlopen(urllib.request.Request(base+'/api/checkins',data=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary,'Idempotency-Key':str(uuid4())}),timeout=30) as response:
    assert response.status==202;task=json.load(response)
   accepted=time.monotonic();deadline=start+60
   while True:
    with urllib.request.urlopen(urllib.request.Request(base+'/api/tasks/'+task['task_id'],headers={'X-Task-Token':task['task_token']}),timeout=10) as response:result=json.load(response)
    if result['status'] in ('SUCCEEDED','REJECTED','FAILED'):break
    assert time.monotonic()<deadline;time.sleep(.1)
   return {'code':result['result_code'],'accept_ms':(accepted-start)*1000,'end_ms':(time.monotonic()-start)*1000}
  with ThreadPoolExecutor(max_workers=10) as pool:burst=list(pool.map(concurrent_photo,range(10)))
  counts=dict(Counter(row['code'] for row in burst));assert counts=={'CHECKED_IN':1,'ALREADY_CHECKED_IN':9},counts
  evidence['results'].extend(row['code'] for row in burst)
  def p95(values):return round(sorted(values)[math.ceil(len(values)*.95)-1],1)
  evidence['synthetic_same_identity_burst']={'concurrency':10,'requests':10,'gallery_identities':2,'image_bytes':len(pixels),'codes':counts,'accept_p95_ms':p95([r['accept_ms'] for r in burst]),'end_to_end_p95_ms':p95([r['end_ms'] for r in burst]),'scope':'same AI fictional identity duplicate burst; not distinct human throughput'}
  print('PASS 10 concurrent real-model AI face tasks: one CHECKED_IN, nine ALREADY_CHECKED_IN',flush=True)
  teacher.goto(base+'/records.html?session_id='+str(session['id']));expect(teacher.locator('#summary')).to_contain_text('应到 1 人 · 已到 1 人 · 暂未到 0 人');teacher.screenshot(path=str(OUT/'ai-teacher-records.png'),full_page=True)
  student.goto(base+'/dashboard.html');expect(student.locator('#session-list')).not_to_contain_text('AI合成样本自动化测试');student.get_by_role('button',name='全部场次',exact=True).click();expect(student.locator('#session-list')).to_contain_text('已签到')
  assert not errors,errors;browser.close()
 evidence['database']=server_python(GUARD+f'f={f!r}\n'+'''
import json,numpy as np
from sqlalchemy import func
from app.models import FaceSample
with factory() as db:
 u=db.scalar(select(User).where(User.student_no==f['student_no']));face=db.scalar(select(FaceSample).where(FaceSample.user_id==u.id,FaceSample.status=='ACTIVE'));v=np.frombuffer(face.embedding,dtype='<f4')
 b=db.scalar(select(User).where(User.student_no==f['peer_no']));sids=[f['session_id'],f['second_session_id'],f['third_session_id']]
 ts=list(db.scalars(select(RecognitionTask).where((RecognitionTask.owner_user_id.in_([u.id,b.id]))|(RecognitionTask.session_id.in_(sids)))))
 result={'account_status':u.status,'face_samples':db.scalar(select(func.count()).select_from(FaceSample).where(FaceSample.user_id==u.id,FaceSample.status=='ACTIVE')),'feature_dimension':len(v),'feature_norm':float(np.linalg.norm(v)),'model_version':face.model_version,'records':db.scalar(select(func.count()).select_from(AttendanceRecord).where(AttendanceRecord.session_id.in_(sids))),'person_a_records':db.scalar(select(func.count()).select_from(AttendanceRecord).where(AttendanceRecord.user_id==u.id)),'first_roster':db.scalar(select(func.count()).select_from(SessionMember).where(SessionMember.session_id==f['session_id'])),'second_roster':db.scalar(select(func.count()).select_from(SessionMember).where(SessionMember.session_id==f['second_session_id'])),'task_codes':sorted(t.result_code for t in ts)}
engine.dispose();print(json.dumps(result))
''')
 assert evidence['database']['records']==4 and evidence['database']['person_a_records']==3 and evidence['database']['first_roster']==1 and evidence['database']['second_roster']==2 and evidence['database']['face_samples']==1 and evidence['database']['feature_dimension']==512 and abs(evidence['database']['feature_norm']-1)<1e-5
 assert evidence['database']['task_codes']==sorted(evidence['results'])
 evidence['threshold']=f['threshold'];evidence['margin']=f['margin']
 (OUT/'ai-face-results.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8');print('PASS real model synthetic-face end-to-end, frozen roster and distinct-session records',flush=True)
finally:
 server_python(GUARD+f'f={f!r}\n'+'''
import json
from app.models import FaceSample,FaceLibraryState
from app.services.uploads import stored_path
from app.services.capacity import release
from redis import Redis
paths=set();tids=[]
with factory.begin() as db:
 assert db.get(ClassRoom,f['class_id']).name=='AI fictional faces '+f['marker']
 users=list(db.scalars(select(User).where(User.student_no.in_([f['admin_no'],f['student_no'],f['peer_no']]))));ids=[u.id for u in users]
 rows=list(db.scalars(select(AttendanceSession).where(AttendanceSession.class_id==f['class_id'])));sids=[r.id for r in rows]
 assert all(row.created_by==f['admin_id'] for row in rows)
 tasks=list(db.scalars(select(RecognitionTask).where((RecognitionTask.owner_user_id.in_(ids))|(RecognitionTask.session_id.in_(sids)))))
 assert all(t.status in ('SUCCEEDED','REJECTED','FAILED') for t in tasks),'Refuse cleanup while work is active'
 for t in tasks:
  if t.image_path:paths.add(t.image_path)
  tids.append(t.id)
 faces=list(db.scalars(select(FaceSample).where(FaceSample.user_id.in_(ids))))
 for face in faces:paths.add(face.image_path)
 db.execute(delete(AttendanceRecord).where(AttendanceRecord.session_id.in_(sids)))
 db.execute(delete(RecognitionTask).where(RecognitionTask.id.in_(tids)))
 db.execute(delete(FaceSample).where(FaceSample.user_id.in_(ids)))
 db.get(FaceLibraryState,1,with_for_update=True).version+=1
 db.execute(delete(SessionMember).where(SessionMember.session_id.in_(sids)))
 db.execute(delete(AttendanceSession).where(AttendanceSession.id.in_(sids)))
 db.execute(delete(LoginSession).where(LoginSession.user_id.in_(ids)))
 db.execute(delete(User).where(User.id.in_(ids)))
 db.delete(db.get(ClassRoom,f['class_id']))
for path in paths:stored_path(settings.storage_dir,path).unlink(missing_ok=True)
r=Redis.from_url(settings.redis_url)
for tid in tids:release(r,tid)
r.close();engine.dispose();print(json.dumps({'cleanup':'complete'}))
''')
