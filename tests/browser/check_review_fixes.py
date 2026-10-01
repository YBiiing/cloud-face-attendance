"""Review regressions with local static files and mocked APIs; no personal data."""
import json
from datetime import datetime, timedelta, timezone
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, expect
from check_registration import QuietHandler


def main():
    root = Path(__file__).resolve().parents[2]
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(root/'web')))
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width': 390, 'height': 844})
            page.add_init_script("const originalTimeout=window.setTimeout;window.setTimeout=(fn,ms,...args)=>originalTimeout(fn,ms>=1000&&ms<=8000?20:ms,...args);")
            errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
            state = {'posts': [], 'tasks': {}, 'keys': {}, 'mode': 'failed', 'drop': False, 'unavailable': False, 'missing_polls': 0}
            now = datetime.now(timezone.utc)

            def api(route):
                path = urlsplit(route.request.url).path; method = route.request.method; status = 200
                if path == '/api/me':
                    result = {'user': {'id': 1, 'role': 'STUDENT'}, 'csrf_token': 'fixture-csrf'}
                elif path == '/api/classes': result = {'items': [{'id': 1, 'name': '测试班'}], 'total': 1}
                elif path.startswith('/api/sessions/'):
                    result = {'title': '测试课程', 'class_name': '测试班', 'status': 'OPEN', 'server_time': now.isoformat(),
                              'starts_at': (now-timedelta(minutes=1)).isoformat(), 'effective_end': (now+timedelta(minutes=10)).isoformat()}
                elif path in ['/api/faces', '/api/auth/register', '/api/checkins'] and method == 'POST':
                    key = route.request.headers['idempotency-key']; state['posts'].append((path, key))
                    if key not in state['keys']:
                        task_id = 'task-'+str(len(state['keys'])+1); state['keys'][key] = task_id
                        code = ('FACE_SAVED' if path == '/api/faces' else 'ENROLLED') if state['mode'] == 'success' else 'PROCESSING_FAILED'
                        state['tasks'][task_id] = {'status': 'SUCCEEDED' if state['mode'] == 'success' else 'FAILED', 'result_code': code}
                    result = {'task_id': state['keys'][key], 'task_token': 'fixture-token'}; status = 202
                    if state['drop']:
                        state['drop'] = False; route.abort('failed'); return
                elif path == '/api/faces': result = {'items': [], 'total': 0}
                elif path.startswith('/api/tasks/'):
                    task_id = path.rsplit('/', 1)[1]
                    if task_id not in state['tasks']:
                        state['missing_polls'] += 1; status = 404; result = {'error': {'message': '任务不存在或凭证无效'}}
                    elif state['unavailable']:
                        status = 503; result = {'error': {'message': '测试暂时不可用'}}
                    else: result = state['tasks'][task_id]
                else: raise AssertionError((method, path))
                route.fulfill(status=status, content_type='application/json', body=json.dumps(result))

            page.route('**/api/**', api); base = f'http://127.0.0.1:{server.server_port}'
            def photo():
                page.locator('[name=photo]').set_input_files({'name': 'fixture.png', 'mimeType': 'image/png', 'buffer': b'fixture-only'})
            def restore_event():
                with page.expect_navigation(wait_until='load'):
                    page.evaluate("window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true}));window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}));")
            def save_missing(key):
                page.evaluate('key=>sessionStorage.setItem(key,JSON.stringify({task_id:"missing",task_token:"invalid"}))', key)

            # Restored registration must issue a real mocked POST, not silently abort.
            page.goto(base+'/register.html'); restore_event()
            page.locator('[name=name]').fill('测试'); page.locator('[name=student_no]').fill('TEST001')
            page.locator('[name=password]').fill('test-password-only'); page.locator('[name=class_id]').select_option('1'); photo()
            page.locator('#submit').click(); expect(page.locator('#message')).to_have_text('处理失败，请稍后重试')
            assert len(state['posts']) == 1
            save_missing('registration-task'); page.reload()
            expect(page.locator('#message')).to_contain_text('保存的注册任务已失效')
            expect(page.locator('[name=student_no]')).to_be_enabled(); expect(page.locator('[name=photo]')).to_be_enabled()
            assert page.evaluate('sessionStorage.getItem("registration-task")') is None
            missing = state['missing_polls']; page.reload(); expect(page.locator('[name=class_id] option')).to_have_count(2)
            assert state['missing_polls'] == missing

            # Restored photo page can submit; a confirmed failure gets a new key.
            page.goto(base+'/faces.html'); expect(page.locator('#page-info')).to_contain_text('第 1 页'); restore_event()
            expect(page.locator('#page-info')).to_contain_text('第 1 页'); photo()
            button = page.get_by_role('button', name='上传照片', exact=True)
            button.click(); expect(page.locator('#message')).to_have_text('处理失败，请稍后重试')
            first_key = state['posts'][-1][1]; state['mode'] = 'success'
            button.click(); expect(page.locator('#message')).to_have_text('标准照已保存')
            assert state['posts'][-1][1] != first_key

            # Lost upload response is still retried with the original key.
            photo(); state['drop'] = True; count = len(state['keys'])
            button.click(); expect(button).to_be_enabled(); expect(page.locator('#message')).not_to_have_text('标准照已保存')
            lost_key = state['posts'][-1][1]
            button.click(); expect(page.locator('#message')).to_have_text('标准照已保存')
            assert state['posts'][-1][1] == lost_key and len(state['keys']) == count+1

            # Accepted task survives page restoration without another upload.
            photo(); state['unavailable'] = True; button.click()
            expect(page.locator('#message')).to_have_text('测试暂时不可用'); expect(button).to_be_disabled()
            post_count = len(state['posts']); state['unavailable'] = False; restore_event()
            expect(page.locator('#message')).to_have_text('标准照已保存'); assert len(state['posts']) == post_count
            assert page.evaluate('sessionStorage.getItem("face-task:1")') is None

            page.goto(base+'/checkin.html?session_code=A'); expect(page.locator('#title')).to_have_text('测试课程')
            save_missing('checkin-task:A'); page.reload()
            expect(page.locator('#message')).to_contain_text('保存的签到任务已失效')
            expect(page.locator('#submit')).to_be_enabled(); expect(page.locator('#resume')).to_be_hidden()
            assert page.evaluate('sessionStorage.getItem("checkin-task:A")') is None
            missing = state['missing_polls']; page.reload(); expect(page.locator('#title')).to_have_text('测试课程')
            assert state['missing_polls'] == missing
            assert not errors, errors
            browser.close()
        print('PASS: restored register/faces, terminal retry new key, lost response same key, photo task resume without upload, permanent 404 unlocks register/checkin; mock APIs only')
    finally:
        server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': main()
