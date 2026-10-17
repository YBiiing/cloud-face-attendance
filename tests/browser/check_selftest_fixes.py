"""Mobile feedback/link regressions with explicit API fixtures, no biometric claims."""
import argparse,json,struct,zlib
from datetime import datetime,timedelta,timezone
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
from check_registration import QuietHandler


def main(engine='chromium',output=None):
    root=Path(__file__).resolve().parents[2];out=Path(output) if output else root/'.tmp/selftest-ui';out.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(root/'web')));thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    def chunk(kind,data):return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff)
    pixels=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',640,640,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\xff'*1920)*640))+chunk(b'IEND',b'')
    base=f'http://127.0.0.1:{server.server_port}';now=datetime.now(timezone.utc);state={'role':'ADMIN','mode':'CHECKED_IN','posts':0};errors=[]
    row={'id':1,'title':'移动端课程反馈验证','class_name':'测试班','status':'OPEN','server_time':now.isoformat(),'starts_at':(now-timedelta(minutes=1)).isoformat(),'ends_at':(now+timedelta(hours=1)).isoformat(),'effective_end':(now+timedelta(hours=1)).isoformat(),'expected_count':50,'checkin_path':'/checkin.html?session_code=fixture'}
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='msedge',headless=True) if engine=='chromium' else getattr(p,engine).launch(headless=True)
            page=browser.new_page(viewport={'width':320,'height':568});page.on('pageerror',lambda e:errors.append(str(e)))
            page.add_init_script("Object.defineProperty(navigator,'clipboard',{value:{writeText:async()=>{throw new Error('fixture clipboard denial')}}});")
            def api(route):
                path=urlsplit(route.request.url).path;method=route.request.method;status=200
                if path=='/api/me':
                    if state['role']:result={'user':{'id':1,'name':'测试老师','role':state['role']},'csrf_token':'fixture'}
                    else:status=401;result={'error':{'message':'请登录'}}
                elif path=='/api/sessions':result={'items':[row],'total':1}
                elif path=='/api/sessions/fixture':result=row
                elif path=='/api/classes':result={'items':[{'id':1,'name':'测试班'}],'total':1}
                elif path in ['/api/checkins','/api/auth/register'] and method=='POST':state['posts']+=1;status=202;result={'task_id':'fixture-'+str(state['posts']),'task_token':'fixture'}
                elif path.startswith('/api/tasks/'):
                    code=state['mode'];result={'status':'SUCCEEDED' if code in ['CHECKED_IN','ENROLLED'] else 'REJECTED','result_code':code}
                else:raise AssertionError((method,path))
                route.fulfill(status=status,content_type='application/json',body=json.dumps(result))
            page.route('**/api/**',api)
            page.goto(base+'/sessions.html');expect(page.get_by_role('link',name='打开签到页面')).to_have_attribute('href',base+row['checkin_path'])
            expect(page.get_by_role('link',name='打开签到页面')).to_have_attribute('rel','noopener')
            page.get_by_role('button',name='复制签到链接').click();link=page.get_by_label('本场签到链接');expect(link).to_be_visible();expect(link).to_have_value(base+row['checkin_path']);assert link.evaluate('n=>n.readOnly')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(out/(engine+'-teacher-links.png')),full_page=True)
            def photo(name):page.locator('[name=photo]').set_input_files({'name':name,'mimeType':'image/png','buffer':pixels})
            def visible_feedback():
                page.wait_for_function("(()=>{let r=document.querySelector('#message').getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;})()")
            state['role']=None;page.goto(base+row['checkin_path']);photo('first.png');page.locator('#submit').click();expect(page.locator('#message')).to_have_text('签到成功');visible_feedback();page.screenshot(path=str(out/(engine+'-feedback.png')))
            photo('next.png');expect(page.locator('#message')).to_have_text('照片已更换，请提交');assert state['posts']==1
            state['mode']='UNKNOWN_PERSON';page.locator('#submit').click();expect(page.locator('#message')).to_have_text('未识别到已录入人员');visible_feedback()
            page.goto(base+'/register.html');page.locator('[name=name]').fill('测试');page.locator('[name=student_no]').fill('FIXTURE');page.locator('[name=class_id]').select_option('1');page.locator('[name=password]').fill('abc123');photo('register.png');state['mode']='NO_FACE';page.locator('#submit').click();expect(page.locator('#message')).to_have_text('未检测到人脸，请重新拍摄');visible_feedback()
            photo('retry.png');expect(page.locator('#message')).to_have_text('照片已更换，请提交');assert not errors,errors;browser.close()
        print('PASS '+engine+': teacher links/copy fallback, visible terminal feedback, changed photo clears old result')
    finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--engine',choices=['chromium','webkit','firefox'],default='chromium');parser.add_argument('--output',type=Path);args=parser.parse_args();main(args.engine,args.output)
