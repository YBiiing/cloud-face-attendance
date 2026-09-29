"""Real HTTP/Celery/ONNX smoke in isolated test DB. Seed accounts have no face.

Requires the test API at 127.0.0.1:8001 (compose.test.yaml + compose.e2e.yaml).
Only the blank-image rejection is biometric evidence; no positive face fixture.
"""
import base64
import html
import json
from pathlib import Path
import subprocess
from uuid import uuid4
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ['docker', 'compose', '-p', 'face-attendance-test', '-f', 'compose.yaml', '-f', 'compose.test.yaml', '-f', 'compose.e2e.yaml']


def server_python(code):
    result = subprocess.run(COMPOSE+['exec', '-T', 'api', 'python', '-'], input=code,
                            encoding='utf-8', cwd=ROOT, capture_output=True)
    if result.returncode:
        # Never echo setup code, credentials, or request body in exceptions.
        raise RuntimeError('Isolated fixture command failed: '+result.stderr[-1000:])
    return json.loads(result.stdout)


GUARD = '''
from app.config import Settings
from app.database import make_engine,make_session_factory
from app.models import User,ClassRoom,LoginSession,AttendanceSession,SessionMember,RecognitionTask,AttendanceRecord
from sqlalchemy import select,delete
settings=Settings.from_env()
assert settings.environment=='test' and settings.mysql_database=='face_attendance_test'
engine=make_engine(settings);factory=make_session_factory(engine)
'''


def main():
    marker = 'E2E'+uuid4().hex[:16]
    fixture = server_python(GUARD+f"marker={marker!r}\n"+'''
import json,secrets,base64
from datetime import timedelta
from io import BytesIO
from PIL import Image
from app import clock
from app.security import hash_password
from app.services.attendance_sessions import create_session
password=secrets.token_urlsafe(24)
with factory.begin() as db:
    classroom=ClassRoom(name='自动化演示临时班级 '+marker);db.add(classroom);db.flush()
    admin=User(student_no=marker+'A',name='自动化测试管理员',password_hash=hash_password(password),role='ADMIN',status='ACTIVE')
    student=User(student_no=marker+'S',name='自动化测试学生（未录入照片）',class_id=classroom.id,password_hash=hash_password(password),status='ACTIVE')
    db.add_all([admin,student]);db.flush()
    row,_=create_session(db,admin.id,'自动化演示 · 无脸拒绝',classroom.id,clock.utc_now()-timedelta(minutes=1),clock.utc_now()+timedelta(minutes=5));db.flush()
    result=dict(admin_id=admin.id,student_id=student.id,class_id=classroom.id,session_id=row.id,session_code=row.public_code,admin_no=admin.student_no,password=password)
buffer=BytesIO();Image.new('RGB',(640,640),'white').save(buffer,format='PNG')
result['blank_png']=base64.b64encode(buffer.getvalue()).decode()
engine.dispose();print(json.dumps(result))
''')
    output = ROOT/'docs'/'verification'
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            anonymous = browser.new_context(viewport={'width': 390, 'height': 844})
            page = anonymous.new_page(); errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            base = 'http://127.0.0.1:8001'
            page.goto(base+'/checkin.html?session_code='+fixture['session_code'])
            expect(page.locator('#title')).to_have_text('自动化演示 · 无脸拒绝')
            assert not anonymous.cookies()
            page.locator('[name=photo]').set_input_files({'name': 'blank.png', 'mimeType': 'image/png', 'buffer': base64.b64decode(fixture['blank_png'])})
            page.locator('#submit').click()
            expect(page.locator('#message')).to_have_text('未检测到人脸，请重新拍摄', timeout=45000)
            assert not anonymous.cookies()
            page.screenshot(path=str(output/'week3-real-no-face.png'), full_page=True)
            page.reload(); expect(page.locator('#message')).to_have_text('未检测到人脸，请重新拍摄')
            admin = browser.new_context(viewport={'width': 390, 'height': 844})
            management = admin.new_page(); management.on('pageerror', lambda error: errors.append(str(error)))
            management.goto(base+'/login.html')
            management.locator('[name=student_no]').fill(fixture['admin_no'])
            management.locator('[name=password]').fill(fixture['password'])
            management.locator('#login-form button').click(); expect(management.locator('#message')).to_have_text('登录成功')
            management.goto(base+'/records.html?session_id='+str(fixture['session_id']))
            expect(management.locator('#summary')).to_contain_text('应到 1 人 · 已到 0 人 · 暂未到 1 人')
            expect(management.locator('#summary')).to_contain_text('处理中任务 0 个')
            management.screenshot(path=str(output/'week3-live-records.png'), full_page=True)
            for view in [page, management]:
                assert view.evaluate('document.documentElement.scrollWidth <= innerWidth')
            evidence = server_python(GUARD+f"session_id={fixture['session_id']}\n"+'''
import json
from scripts.week3_snapshot import snapshot
with factory() as db: result=snapshot(db,session_id)
engine.dispose();print(json.dumps(result,ensure_ascii=False))
''')
            assert evidence['attended'] == 0 and evidence['task_counts'] == {'REJECTED': 1}
            assert evidence['recent_tasks'][0]['result_code'] == 'NO_FACE'
            report = browser.new_page(viewport={'width': 900, 'height': 900})
            report.set_content('<html lang="zh-CN"><meta charset="utf-8"><style>body{font:18px sans-serif;padding:24px}pre{font:16px monospace;white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>隔离 MySQL 查询结果</h1><p>真实模型无脸拒绝；临时账号与场次，无真人成功签到。</p><pre>'+html.escape(json.dumps(evidence, ensure_ascii=False, indent=2))+'</pre></html>')
            report.screenshot(path=str(output/'week3-database-no-face.png'), full_page=True)
            assert not errors, errors
            browser.close()
        print('PASS: anonymous real HTTP -> Celery -> ONNX NO_FACE; roster and MySQL agree; no duplicate task after reload')
    finally:
        # Exact IDs and marker checked before touching this script's own data.
        cleanup = {key: fixture[key] for key in ['admin_id', 'student_id', 'class_id', 'session_id']}
        server_python(GUARD+f"fixture={cleanup!r}\nmarker={marker!r}\n"+'''
import json
from app.services.uploads import stored_path
from app.services.capacity import release
from redis import Redis
paths=[];task_ids=[]
with factory.begin() as db:
    ids=[fixture['admin_id'],fixture['student_id']]
    assert db.get(User,ids[0]).student_no==marker+'A'
    assert db.get(User,ids[1]).student_no==marker+'S'
    assert db.get(ClassRoom,fixture['class_id']).name=='自动化演示临时班级 '+marker
    row=db.get(AttendanceSession,fixture['session_id'])
    assert row.created_by==ids[0] and row.class_id==fixture['class_id']
    for task in db.scalars(select(RecognitionTask).where(RecognitionTask.session_id==row.id)):
        assert task.status in {'SUCCEEDED','FAILED','REJECTED'},'Refuse cleanup while task is running'
        if task.image_path:paths.append(stored_path(settings.storage_dir,task.image_path))
        task_ids.append(task.id)
    db.execute(delete(AttendanceRecord).where(AttendanceRecord.session_id==row.id))
    db.execute(delete(RecognitionTask).where(RecognitionTask.session_id==row.id))
    db.execute(delete(SessionMember).where(SessionMember.session_id==row.id))
    db.delete(row);db.flush()
    db.execute(delete(LoginSession).where(LoginSession.user_id.in_(ids)))
    db.execute(delete(User).where(User.id.in_(ids)))
    db.execute(delete(ClassRoom).where(ClassRoom.id==fixture['class_id']))
for path in paths:path.unlink(missing_ok=True)
redis=Redis.from_url(settings.redis_url)
for task_id in task_ids:release(redis,task_id)
redis.close();engine.dispose();print(json.dumps({'cleanup':'complete'}))
''')


if __name__ == '__main__':
    main()
