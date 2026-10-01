r"""Browser regression for registration recovery. API responses are test fixtures.

Run on Windows: .venv\Scripts\python.exe tests/browser/check_registration.py
Requires playwright Python package and installed Microsoft Edge. No real photos.
"""
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright, expect


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    root = Path(__file__).resolve().parents[2]
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(root / 'web')))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width': 390, 'height': 844})
            # Accelerate only polling backoff in this fixture browser.
            page.add_init_script("const originalTimeout=window.setTimeout;window.setTimeout=(fn,ms,...args)=>originalTimeout(fn,ms>=1000&&ms<=8000?20:ms,...args);")
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            task = {'task_id': 'test-task', 'task_token': 'test-token'}
            state = {'polls': 0, 'posts': 0}

            def api(route):
                path = route.request.url.split('/api', 1)[1]
                status = 200
                if path.startswith('/classes'):
                    result = {'items': [{'id': 1, 'name': '测试班级'}], 'total': 1}
                elif path == '/auth/register':
                    state['posts'] += 1
                    status, result = 202, task
                    assert 'name="student_no"' in route.request.post_data
                elif path == '/tasks/test-task':
                    state['polls'] += 1
                    if state['polls'] <= 5:
                        status, result = 503, {'error': {'message': '测试查询中断'}}
                    else:
                        result = {'status': 'REJECTED', 'result_code': 'NO_FACE'}
                else:
                    raise AssertionError(path)
                route.fulfill(status=status, content_type='application/json', body=json.dumps(result))

            page.route('**/api/**', api)
            page.goto(f'http://127.0.0.1:{server.server_port}/register.html')
            page.locator('[name=name]').fill('测试')
            page.locator('[name=student_no]').fill('TEST001')
            page.locator('[name=password]').fill('test-password-only')
            page.locator('[name=class_id]').select_option('1')
            page.locator('[name=photo]').set_input_files({'name': 'test.png', 'mimeType': 'image/png', 'buffer': b'test-fixture'})
            page.locator('#submit').click()
            expect(page.locator('#message')).to_have_text('测试查询中断')
            expect(page.locator('[name=student_no]')).to_be_disabled()
            page.get_by_role('button', name='继续查询注册结果').click()
            expect(page.locator('#message')).to_have_text('未检测到人脸，请重新拍摄')
            expect(page.locator('[name=photo]')).to_be_enabled()
            expect(page.locator('[name=student_no]')).to_be_disabled()
            assert state['posts'] == 1
            page.reload()
            expect(page.locator('#submit')).to_have_text('重新上传照片')
            expect(page.locator('[name=photo]')).to_be_enabled()
            assert not errors, errors
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            browser.close()
        print('PASS: mobile layout, interrupted polling recovery, terminal retry and reload; fixture API only')
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == '__main__':
    main()
