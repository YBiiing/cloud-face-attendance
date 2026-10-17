"""Headed Edge + real isolated HTTP/Celery/ONNX, native virtual video device.

Never opens the physical webcam. Camera permissions apply to temporary browser
contexts only. Requires the isolated test API at 127.0.0.1:8001.
"""
import json
import os
import sys
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright, expect
from check_live_attendance import ROOT, GUARD, server_python

BASE='http://127.0.0.1:8001'
OUT=Path(os.getenv('ATTENDANCE_TEST_OUTPUT',str(ROOT/'docs/verification/desktop-camera-2026-10-07')))
OUT.mkdir(parents=True,exist_ok=True)
rows=[]
def record(name,detail=''):
    rows.append({'name':name,'passed':True,'detail':detail})
    print('PASS '+name,flush=True)
def shot(page,name):page.screenshot(path=str(OUT/(name+'.png')),full_page=True)

def main():
    marker='CAM'+uuid4().hex[:12]
    fixture=server_python(GUARD+f'marker={marker!r}\n'+'''
import json
from datetime import timedelta
from app import clock
from app.security import hash_password
from app.services.attendance_sessions import create_session
with factory.begin() as db:
 c=ClassRoom(name='Desktop camera '+marker);db.add(c);db.flush()
 t=User(student_no=marker+'T',name='虚拟摄像头测试老师',role='ADMIN',status='ACTIVE',password_hash=hash_password('abc123'))
 s=User(student_no=marker+'S',name='虚拟摄像头测试学生',class_id=c.id,status='ACTIVE',password_hash=hash_password('abc123'))
 db.add_all([t,s]);db.flush()
 row,_=create_session(db,t.id,'虚拟摄像头无脸拒绝 '+marker,c.id,clock.utc_now()-timedelta(minutes=1),clock.utc_now()+timedelta(hours=1));db.flush()
 result=dict(class_id=c.id,teacher_id=t.id,student_no=s.student_no,session_id=row.id,code=row.public_code)
engine.dispose();print(json.dumps(result))
''')
    errors=[]
    try:
      with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=False,args=['--use-fake-device-for-media-stream'])
        context=browser.new_context(viewport={'width':1366,'height':768},permissions=['camera'])
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        choosers=[];posts=[]
        page.on('filechooser',lambda e:choosers.append(e))
        page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
        def open_camera():
            page.get_by_role('button',name='拍照',exact=True).click()
            expect(page.locator('dialog')).to_be_visible()
            page.wait_for_function("document.querySelector('dialog video').videoWidth>0")
            expect(page.get_by_role('button',name='拍摄',exact=True)).to_be_enabled()
            page.evaluate("window.observedCameraTrack=document.querySelector('dialog video').srcObject.getVideoTracks()[0]")
            assert page.evaluate('observedCameraTrack.readyState')=='live'
        def capture_confirm(name):
            before=len(posts);open_camera();assert len(choosers)==0
            shot(page,name+'-live')
            page.get_by_role('button',name='拍摄',exact=True).click()
            expect(page.locator('dialog img')).to_be_visible()
            assert page.evaluate('observedCameraTrack.readyState')=='ended'
            assert page.locator('[name=photo]').evaluate('(n)=>n.files.length')==0
            assert len(posts)==before
            shot(page,name+'-snapshot')
            page.get_by_role('button',name='使用这张照片',exact=True).click()
            expect(page.locator('dialog')).to_have_count(0)
            expect(page.locator('#preview')).to_be_visible()
            file=page.locator('[name=photo]').evaluate('(n)=>({name:n.files[0].name,type:n.files[0].type,size:n.files[0].size})')
            assert file['name'].endswith('.jpg') and file['type']=='image/jpeg' and file['size']>1000
            assert len(posts)==before
            record(name+'取景→拍摄停止轨道→确认JPEG，无文件选择或自动上传',json.dumps(file))
        page.goto(BASE+'/register.html');expect(page.locator('#register-form')).to_be_visible()
        expect(page.locator('.photo-choice')).to_contain_text('选择照片文件')
        before=len(posts);open_camera();page.get_by_role('button',name='取消',exact=True).click()
        expect(page.locator('dialog')).to_have_count(0)
        assert page.evaluate('observedCameraTrack.readyState')=='ended'
        assert page.locator('[name=photo]').evaluate('(n)=>n.files.length')==0 and len(posts)==before
        record('取消释放摄像头且不选择文件、不上传')
        open_camera();page.keyboard.press('Escape');expect(page.locator('dialog')).to_have_count(0)
        assert page.evaluate('observedCameraTrack.readyState')=='ended';record('Escape关闭释放摄像头')
        open_camera();page.get_by_role('button',name='拍摄',exact=True).click();expect(page.locator('dialog img')).to_be_visible()
        page.get_by_role('button',name='重拍',exact=True).click();page.wait_for_function("document.querySelector('dialog video').videoWidth>0")
        expect(page.locator('dialog img')).to_be_hidden();expect(page.get_by_role('button',name='拍摄',exact=True)).to_be_enabled()
        page.evaluate("window.observedCameraTrack=document.querySelector('dialog video').srcObject.getVideoTracks()[0]")
        page.get_by_role('button',name='取消',exact=True).click();assert page.evaluate('observedCameraTrack.readyState')=='ended'
        record('重拍重新取景、清除上次快照、取消释放新轨道')
        capture_confirm('注册页')
        page.locator('[name=name]').fill('虚拟摄像头无脸注册');page.locator('[name=student_no]').fill(marker+'R')
        page.locator('[name=class_id]').select_option(str(fixture['class_id']));page.locator('[name=password]').fill('abc123')
        page.locator('#submit').click();expect(page.locator('#message')).to_have_text('未检测到人脸，请重新拍摄',timeout=45000)
        record('摄像头JPEG实际注册→Celery→ONNX拒绝无脸，不误报成功');shot(page,'registration-real-no-face')
        page.reload();expect(page.locator('#submit')).to_have_text('重新上传照片')
        open_camera();page.get_by_role('button',name='取消',exact=True).click();expect(page.locator('[data-camera]')).to_be_enabled()
        assert page.locator('[name=photo]').evaluate('(n)=>n.files.length')==0;record('注册失败刷新后拍照取消仍可重试')
        page.goto(BASE+'/login.html');page.locator('[name=student_no]').fill(fixture['student_no']);page.locator('[name=password]').fill('abc123')
        page.get_by_role('button',name='登录',exact=True).click();expect(page).to_have_url(BASE+'/dashboard.html')
        page.goto(BASE+'/faces.html');expect(page.locator('#face-form')).to_be_visible();capture_confirm('照片库')
        page.get_by_role('button',name='上传照片',exact=True).click();expect(page.locator('#message')).to_have_text('未检测到人脸，请重新拍摄',timeout=45000)
        expect(page.locator('#photo-list')).to_have_text('暂无有效标准照');record('照片库摄像头JPEG真实无脸拒绝，不产生标准照')
        page.goto(BASE+'/checkin.html?session_code='+fixture['code']);expect(page.locator('#checkin-form')).to_be_visible()
        capture_confirm('签到页');page.locator('#submit').click();expect(page.locator('#message')).to_have_text('未检测到人脸，请重新拍摄',timeout=45000)
        record('签到页摄像头JPEG真实无脸拒绝，不产生签到记录');shot(page,'checkin-real-no-face')
        page.locator('[name=photo]').set_input_files([])
        open_camera();page.get_by_role('button',name='拍摄',exact=True).click();expect(page.locator('dialog img')).to_be_visible()
        page.get_by_role('button',name='取消',exact=True).click()
        assert page.locator('[name=photo]').evaluate('(n)=>n.files.length')==0;record('快照预览取消不修改表单')
        for width,height in [(1920,1080),(1366,768),(1024,768),(640,600),(390,600)]:
            page.set_viewport_size({'width':width,'height':height});open_camera()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            r=page.locator('dialog').bounding_box();assert r['x']>=0 and r['y']>=0 and r['x']+r['width']<=width+1 and r['y']+r['height']<=height+1
            expect(page.get_by_role('button',name='取消',exact=True)).to_be_in_viewport()
            shot(page,'camera-'+str(width));page.keyboard.press('Escape');record('桌面摄像头弹窗适配 '+str(width)+'x'+str(height))
        page.set_viewport_size({'width':1366,'height':768});open_camera()
        page.evaluate("addEventListener('pagehide',()=>sessionStorage.setItem('camera-track-on-leave',observedCameraTrack.readyState),{once:true})")
        page.goto(BASE+'/login.html');expect(page).to_have_url(BASE+'/dashboard.html')
        assert page.evaluate("sessionStorage.getItem('camera-track-on-leave')")=='ended';record('离开页面释放摄像头轨道')
        assert not choosers;record('整个桌面拍照流程没有触发文件选择器')
        context.close()
        denied=browser.new_context(viewport={'width':1366,'height':768})
        q=denied.new_page();q.on('pageerror',lambda e:errors.append(str(e)))
        cdp=denied.new_cdp_session(q);context_id=cdp.send('Target.getTargetInfo')['targetInfo']['browserContextId']
        cdp.send('Browser.setPermission',{'permission':{'name':'camera'},'setting':'denied','origin':BASE,'browserContextId':context_id})
        q.goto(BASE+'/register.html');expect(q.locator('#register-form')).to_be_visible();q.get_by_role('button',name='拍照',exact=True).click()
        expect(q.locator('dialog [role=status]')).to_contain_text('摄像头权限未允许');expect(q.get_by_role('button',name='重试摄像头')).to_be_visible()
        shot(q,'camera-permission-denied');record('临时浏览器拒绝摄像头权限时中文原因、重试和取消')
        cdp.send('Browser.setPermission',{'permission':{'name':'camera'},'setting':'granted','origin':BASE,'browserContextId':context_id})
        q.get_by_role('button',name='重试摄像头').click();q.wait_for_function("document.querySelector('dialog video').videoWidth>0")
        expect(q.get_by_role('button',name='拍摄',exact=True)).to_be_enabled();q.get_by_role('button',name='取消',exact=True).click();record('临时权限从拒绝恢复后可重试取景')
        with q.expect_file_chooser() as chooser:q.locator('.photo-choice').click()
        chooser.value.set_files({'name':'explicit-file.png','mimeType':'image/png','buffer':b'file-chooser-only'})
        expect(q.locator('[data-photo-name]')).to_contain_text('explicit-file.png');record('只有独立选择照片文件入口触发文件选择')
        browser.close();assert not errors;record('实际浏览器无未捕获JS异常')
    except Exception as error:
        rows.append({'name':'执行中断','passed':False,'detail':type(error).__name__+': '+str(error)[:1200]})
        raise
    finally:
        cleanup=server_python(GUARD+f'marker={marker!r}\nf={fixture!r}\n'+'''
import json
from app.services.uploads import stored_path
from app.services.capacity import release
from redis import Redis
with factory.begin() as db:
 users=db.scalars(select(User).where(User.student_no.like(marker+'%'))).all();assert all(x.student_no.startswith(marker) for x in users)
 ids=[x.id for x in users]
 tasks=db.scalars(select(RecognitionTask).where((RecognitionTask.owner_user_id.in_(ids))|(RecognitionTask.session_id==f['session_id']))).all()
 assert all(x.status in {'SUCCEEDED','FAILED','REJECTED'} for x in tasks)
 paths=[stored_path(settings.storage_dir,x.image_path) for x in tasks if x.image_path];task_ids=[x.id for x in tasks]
 assert db.get(ClassRoom,f['class_id']).name.endswith(marker)
 db.execute(delete(AttendanceRecord).where(AttendanceRecord.session_id==f['session_id']))
 db.execute(delete(RecognitionTask).where(RecognitionTask.id.in_(task_ids)))
 db.execute(delete(SessionMember).where(SessionMember.session_id==f['session_id']))
 db.execute(delete(AttendanceSession).where(AttendanceSession.id==f['session_id']))
 db.execute(delete(LoginSession).where(LoginSession.user_id.in_(ids)))
 db.execute(delete(User).where(User.id.in_(ids)));db.execute(delete(ClassRoom).where(ClassRoom.id==f['class_id']))
for path in paths:path.unlink(missing_ok=True)
r=Redis.from_url(settings.redis_url)
for task_id in task_ids:release(r,task_id)
r.close();engine.dispose();print(json.dumps(dict(users=len(ids),tasks=len(tasks),cleanup='complete')))
''')
        record('随机测试数据、图片、登录会话、任务容量精确清理',json.dumps(cleanup))
        (OUT/'results.json').write_text(json.dumps({'scope':'Headed Edge; real HTTP/Celery/ONNX; native virtual media only; no physical webcam or human photos','results':rows,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
