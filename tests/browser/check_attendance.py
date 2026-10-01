"""UI-only regression with explicit fixture responses; not biometric evidence."""
import json
from datetime import datetime, timedelta, timezone
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit, parse_qs
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
            # Accelerate only polling backoff in this fixture browser.
            page.add_init_script("const originalTimeout=window.setTimeout;window.setTimeout=(fn,ms,...args)=>originalTimeout(fn,ms>=1000&&ms<=8000?20:ms,...args);")
            errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
            now = datetime.now(timezone.utc)
            state = {'posts': 0, 'closed': False, 'logged_in': True, 'interrupted': 0}
            outcomes = {'task-1': 'CHECKED_IN', 'task-2': 'UNKNOWN_PERSON', 'task-3': 'ALREADY_CHECKED_IN'}
            def api(route):
                url = urlsplit(route.request.url); path = url.path; status = 200
                if path.startswith('/api/sessions/'):
                    result = {'title': '浏览器测试课程', 'class_name': '测试班', 'status': 'CLOSED' if state['closed'] else 'OPEN',
                              'server_time': now.isoformat(), 'starts_at': (now-timedelta(minutes=1)).isoformat(),
                              'effective_end': (now+timedelta(minutes=5)).isoformat()}
                elif path == '/api/checkins':
                    assert not route.request.headers.get('cookie')
                    assert 'name="user_id"' not in route.request.post_data
                    state['posts'] += 1
                    result = {'task_id': f"task-{state['posts']}", 'task_token': 'fixture-token'}; status = 202
                elif path.startswith('/api/tasks/'):
                    if state['posts'] == 3 and state['interrupted'] < 5:
                        state['interrupted'] += 1
                        status, result = 503, {'error': {'message': '测试连接中断'}}
                    else:
                        code = outcomes[path.rsplit('/', 1)[1]]
                        result = {'status': 'REJECTED' if code == 'UNKNOWN_PERSON' else 'SUCCEEDED', 'result_code': code}
                elif not state['logged_in']:
                    status, result = 401, {'error': {'message': '请先登录'}}
                elif path == '/api/me':
                    result = {'user': {'role': 'ADMIN'}}
                elif path == '/api/records/sessions':
                    result = {'items': [{'id': 1, 'title': '浏览器测试课程', 'starts_at': now.isoformat()}], 'total': 1}
                elif path == '/api/records':
                    result = {'total': 2, 'session_title': '浏览器测试课程', 'summary': {'expected': 2, 'attended': 1, 'absent': 1, 'pending_tasks': 1, 'finalized': False},
                              'items': [{'name': '<img onerror=alert(1)>', 'student_no': 'TEST001', 'attended': True, 'received_at': now.isoformat()},
                                        {'name': '测试学生二', 'student_no': 'TEST002', 'attended': False}]}
                else: raise AssertionError(path)
                route.fulfill(status=status, content_type='application/json', body=json.dumps(result))
            page.route('**/api/**', api)
            base = f'http://127.0.0.1:{server.server_port}'
            page.goto(base+'/checkin.html?session_code=A')
            def upload():
                page.locator('[name=photo]').set_input_files({'name': 'test.png', 'mimeType': 'image/png', 'buffer': b'fixture'})
                page.locator('#submit').click()
            upload(); expect(page.locator('#message')).to_have_text('签到成功')
            page.reload(); expect(page.locator('#message')).to_have_text('签到成功'); assert state['posts'] == 1
            upload(); expect(page.locator('#message')).to_have_text('未识别到已录入人员')
            upload(); expect(page.locator('#message')).to_have_text('测试连接中断')
            expect(page.locator('#submit')).to_be_disabled()
            page.locator('#resume').click(); expect(page.locator('#message')).to_have_text('本场次已签到')
            state['closed'] = True; page.locator('#refresh').click()
            expect(page.locator('#submit')).to_be_disabled()
            page.goto(base+'/checkin.html?session_code=B')
            expect(page.locator('#message')).to_have_text('')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.goto(base+'/records.html?session_id=1')
            expect(page.locator('#summary')).to_contain_text('应到 2 人 · 已到 1 人 · 暂未到 1 人')
            expect(page.locator('#record-list')).to_contain_text('<img onerror=alert(1)>')
            assert page.locator('#record-list img').count() == 0
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            state['logged_in'] = False; page.locator('#refresh').click()
            expect(page.locator('#message')).to_have_text('请先登录后查看签到记录')
            expect(page.locator('#summary')).to_be_hidden()
            assert page.locator('#record-list').inner_text() == ''
            assert not errors, errors
            browser.close()
        print('PASS: anonymous UI, reload, unknown person, interrupted query, closed session, session isolation, records, logout; fixture API only')
    finally:
        server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    main()
