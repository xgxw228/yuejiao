import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
# 顾问 emp008
open_page(b, "http://127.0.0.1:8000/login?p3=1", 1320, 820)
time.sleep(0.7); b.js("localStorage.clear()")
open_page(b, "http://127.0.0.1:8000/login?p3=2", 1320, 820)
time.sleep(1.0)
b.js("document.getElementById('username').value='emp008';document.getElementById('password').value='123456';document.getElementById('form').requestSubmit();")
time.sleep(2.8)
print("navs:", b.js("Array.from(document.querySelectorAll('.nav .nb b')).map(e=>e.textContent).join(' | ')"))
print("badge:", b.js("(document.querySelector('.nav .nav-badge')||{}).textContent"))
b.js("document.querySelector('.nav').click()")
time.sleep(1.5)
print("panel:", b.js("document.getElementById('panel-title').textContent"), "items", b.js("document.querySelectorAll('#panel-body .ws-item').length"))
print("follow boxes:", b.js("document.querySelectorAll('#panel-body .ws-follow').length"))
b.shot("panel_staff.png")
