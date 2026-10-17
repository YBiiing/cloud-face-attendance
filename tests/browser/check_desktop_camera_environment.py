"""Actual desktop runtime constraints; reads pages only, no development writes."""
import argparse
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(os.getenv('ATTENDANCE_TEST_OUTPUT',str(ROOT/'docs/verification/desktop-camera-2026-10-07')))
OUT.mkdir(parents=True,exist_ok=True)
parser=argparse.ArgumentParser();parser.add_argument('--lan-url',required=True,help='Current development LAN HTTP origin, e.g. http://192.168.31.29:8000');args=parser.parse_args()
results=[]
with sync_playwright() as p:
 browser=p.chromium.launch(channel='msedge',headless=False,args=['--use-fake-device-for-media-stream=device-count=0'])
 context=browser.new_context(viewport={'width':1366,'height':768},permissions=['camera'])
 page=context.new_page();events=[];posts=[]
 page.on('filechooser',lambda e:events.append(e));page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
 page.goto('http://127.0.0.1:8001/register.html');expect(page.locator('#register-form')).to_be_visible()
 page.get_by_role('button',name='拍照',exact=True).click();expect(page.locator('dialog [role=status]')).to_contain_text('未检测到摄像头')
 expect(page.get_by_role('button',name='拍摄',exact=True)).to_be_disabled();page.screenshot(path=str(OUT/'no-camera-device.png'),full_page=True)
 page.get_by_role('button',name='重试摄像头').click();expect(page.locator('dialog [role=status]')).to_contain_text('未检测到摄像头')
 page.get_by_role('button',name='取消',exact=True).click();expect(page.locator('dialog')).to_have_count(0)
 results.append({'name':'原生零个虚拟设备→未检测到摄像头、可重试/取消、不选择文件','passed':True})
 page.goto(args.lan_url.rstrip('/')+'/register.html');expect(page.locator('#register-form')).to_be_visible()
 assert not page.evaluate('isSecureContext')
 page.get_by_role('button',name='拍照',exact=True).click();expect(page.locator('dialog [role=status]')).to_contain_text('当前 HTTP 地址无法调用电脑摄像头')
 expect(page.locator('dialog [role=status]')).to_contain_text('localhost');expect(page.get_by_role('button',name='拍摄',exact=True)).to_be_disabled()
 page.screenshot(path=str(OUT/'lan-http-explanation.png'),full_page=True);page.get_by_role('button',name='取消',exact=True).click()
 results.append({'name':'实际开发局域网HTTP安全上下文限制显示中文原因，不跳文件选择','passed':True})
 page.goto('http://localhost:8000/register.html');expect(page.locator('#register-form')).to_be_visible();assert page.evaluate('isSecureContext')
 page.get_by_role('button',name='拍照',exact=True).click();expect(page.locator('dialog [role=status]')).to_contain_text('未检测到摄像头')
 page.get_by_role('button',name='取消',exact=True).click()
 results.append({'name':'实际开发localhost地址可连接且为安全上下文，进入原生设备检查','passed':True})
 assert not events and not posts
 results.append({'name':'全程没有触发文件选择或提交开发数据','passed':True})
 browser.close()
(OUT/'environment-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS: native no-device error/retry/cancel, LAN HTTP explanation, localhost secure context; no file chooser or API writes')
