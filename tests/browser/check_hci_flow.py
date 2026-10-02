"""Role-based mobile flows with explicit fixture APIs, not biometric evidence."""
import json
import argparse
from datetime import datetime,timedelta,timezone
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit,parse_qs
from playwright.sync_api import sync_playwright,expect
from check_registration import QuietHandler


def main(width=390,height=844,output_dir=None):
    root=Path(__file__).resolve().parents[2];output=Path(output_dir) if output_dir else root/'docs/verification/hci-2026-10-02';output.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(root/'web')))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='msedge',headless=True)
            page=browser.new_page(viewport={'width':width,'height':height},is_mobile=True,has_touch=True,device_scale_factor=1);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            now=datetime.now(timezone.utc);state={'role':None,'attended':False,'created':False,'posts':0}
            rows=[{'id':1,'title':'自动化测试 · 云计算','class_name':'测试班级','status':'OPEN','attendance_status':'PENDING',
                   'starts_at':(now-timedelta(minutes=1)).isoformat(),'ends_at':(now+timedelta(minutes=10)).isoformat(),
                   'effective_end':(now+timedelta(minutes=10)).isoformat(),'checkin_path':'/checkin.html?session_code=demo','expected_count':2}]
            def api(route):
                url=urlsplit(route.request.url);path=url.path;status=200;method=route.request.method
                if path=='/api/me':
                    if state['role']:result={'user':{'id':1,'name':'测试老师' if state['role']=='ADMIN' else '测试学生','role':state['role']},'csrf_token':'fixture'}
                    else:status=401;result={'error':{'message':'请先登录'}}
                elif path=='/api/auth/login':
                    data=json.loads(route.request.post_data);assert data['password']=='abc123'
                    state['role']='ADMIN' if data['student_no']=='teacher' else 'STUDENT';result={'user':{'role':state['role']}}
                elif path=='/api/auth/logout':state['role']=None;status=204;result=None
                elif path=='/api/sessions/mine':
                    assert state['role']=='STUDENT';view=parse_qs(url.query).get('view',['pending'])[0]
                    items=[] if state['attended'] and view=='pending' else [{**rows[0],'attendance_status':'ATTENDED' if state['attended'] else 'PENDING'}]
                    result={'items':items,'total':len(items)}
                elif path=='/api/sessions' and method=='POST':
                    assert state['role']=='ADMIN';data=json.loads(route.request.post_data);assert data['class_id']==1
                    state['created']=True;status=201;result={'id':2}
                elif path=='/api/sessions':result={'items':rows,'total':1}
                elif path=='/api/sessions/demo':result={**rows[0],'server_time':now.isoformat()}
                elif path=='/api/classes':result={'items':[{'id':1,'name':'测试班级'}],'total':1}
                elif path=='/api/checkins':
                    state['posts']+=1;assert 'name="user_id"' not in route.request.post_data
                    status=202;result={'task_id':'demo-task','task_token':'fixture'}
                elif path=='/api/tasks/demo-task':state['attended']=True;result={'status':'SUCCEEDED','result_code':'CHECKED_IN'}
                elif path=='/api/faces':result={'items':[],'total':0}
                else:raise AssertionError((method,path))
                route.fulfill(status=status,content_type='application/json',body='' if result is None else json.dumps(result))
            page.route('**/api/**',api);base=f'http://127.0.0.1:{server.server_port}'
            def screenshot(name):
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                assert page.locator('input:not([type=checkbox]):not([type=file]),select').evaluate_all('(nodes)=>nodes.every(n=>parseFloat(getComputedStyle(n).fontSize)>=16)')
                nav=page.locator('[data-workspace-nav]')
                if nav.count() and nav.locator('a').count() and width<768:
                    assert nav.evaluate('(n)=>getComputedStyle(n).position')=='fixed'
                    assert nav.locator('a').evaluate_all('(nodes)=>nodes.every(n=>n.getBoundingClientRect().height>=44)')
                    page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)')
                    assert page.locator('main').evaluate('(n)=>parseFloat(getComputedStyle(n).paddingBottom)')>=100
                    page.evaluate('window.scrollTo(0,0)')
                page.screenshot(path=str(output/name),full_page=True)
            def login(account):
                page.locator('[name=student_no]').fill(account);page.locator('[name=password]').fill('abc123')
                page.get_by_role('button',name='登录',exact=True).click();expect(page).to_have_url(base+'/dashboard.html')
            page.goto(base+'/');expect(page.get_by_role('link',name='登录账户')).to_be_visible()
            page.get_by_role('link',name='登录账户').click();expect(page.locator('[name=password]')).to_have_attribute('minlength','6');screenshot('login.png')
            login('student');expect(page.locator('#role-label')).to_have_text('学生工作台');expect(page.get_by_role('link',name='去签到')).to_be_visible();screenshot('student-dashboard.png')
            assert page.get_by_role('link',name='创建签到',exact=True).count()==0
            page.goto(base+'/login.html');expect(page).to_have_url(base+'/dashboard.html')
            page.get_by_role('link',name='去签到').click();expect(page.locator('#title')).to_have_text(rows[0]['title'])
            assert page.locator('[name=photo]').get_attribute('capture') is None
            expect(page.locator('[data-camera-input]')).to_have_attribute('capture','user')
            screenshot('photo-options.png')
            with page.expect_file_chooser() as chooser:page.get_by_role('button',name='拍照',exact=True).click()
            chooser.value.set_files({'name':'camera-fixture.png','mimeType':'image/png','buffer':b'fixture'})
            expect(page.locator('[data-photo-name]')).to_contain_text('camera-fixture.png')
            assert page.locator('[name=photo]').evaluate('(input)=>input.files.length')==1
            page.get_by_role('button',name='上传并签到').click();expect(page.locator('#message')).to_have_text('签到成功')
            page.goto(base+'/dashboard.html');expect(page.locator('#list-status')).to_contain_text('暂无待签到场次')
            page.get_by_role('button',name='全部场次',exact=True).click();expect(page.locator('#session-list')).to_contain_text('已签到')
            page.get_by_role('button',name='退出登录',exact=True).click();expect(page).to_have_url(base+'/login.html')
            login('teacher');expect(page.locator('#role-label')).to_have_text('老师工作台');screenshot('teacher-dashboard.png')
            assert page.locator('input[type=file]').count()==0 and page.get_by_role('link',name='我的照片').count()==0
            assert '管理员' not in page.locator('body').inner_text()
            page.goto(base+'/faces.html');expect(page).to_have_url(base+'/dashboard.html');assert page.locator('input[type=file]').count()==0
            page.get_by_role('link',name='创建签到',exact=True).click();expect(page.locator('#session-form')).to_be_visible()
            assert page.locator('#session-list').count()==0;screenshot('teacher-create.png')
            page.locator('[name=title]').focus()
            if width<768:expect(page.locator('[data-workspace-nav]')).to_be_hidden()
            page.locator('[name=title]').blur()
            if width<768:expect(page.locator('[data-workspace-nav]')).to_be_visible()
            page.locator('[name=title]').fill('自动化测试课程');page.locator('[name=class_id]').select_option('1')
            page.get_by_role('button',name='发布签到',exact=True).click();expect(page).to_have_url(base+'/sessions.html?created=1')
            expect(page.locator('#message')).to_contain_text('签到已发布');assert state['created']
            assert page.locator('#session-form').count()==0 and page.locator('input[type=file]').count()==0;screenshot('teacher-sessions.png')
            page.get_by_role('button',name='退出登录',exact=True).click();expect(page).to_have_url(base+'/login.html')
            page.goto(base+'/dashboard.html');expect(page).to_have_url(base+'/login.html')
            assert not errors,errors;browser.close()
        print('PASS: guest/login separation, 6-character password, student session discovery/checkin, teacher navigation and no upload, separate create/list, explicit camera and album, mobile layout; fixture APIs only')
    finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--width',type=int,default=390);parser.add_argument('--height',type=int,default=844);parser.add_argument('--output',type=Path)
    args=parser.parse_args();main(args.width,args.height,args.output)
