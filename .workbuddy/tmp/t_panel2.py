import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
# 学生
open_page(b, "http://127.0.0.1:8000/login?p2=1", 1320, 820)
time.sleep(0.7); b.js("localStorage.clear()")
open_page(b, "http://127.0.0.1:8000/login?p2=2", 1320, 820)
time.sleep(1.0)
b.js("document.querySelectorAll('#roleCards .role-card')[2].click()")
time.sleep(0.3); b.js("document.getElementById('form').requestSubmit()")
time.sleep(2.8)
print("student navs:", b.js("document.querySelectorAll('.nav').length"))
print("student badge:", b.js("(document.querySelector('.nav .nav-badge')||{}).textContent"))
b.js("document.querySelector('.nav').click()")
time.sleep(1.4)
print("student panel:", b.js("document.getElementById('panel-title').textContent"), "items", b.js("document.querySelectorAll('#panel-body .ws-item').length"), "buttons", b.js("document.querySelectorAll('#panel-body .ws-acts').length"))
b.shot("panel_student.png")
# 日志面板
b.js("document.querySelectorAll('.nav')[1].click()")
time.sleep(1.6)
print("logs panel:", b.js("document.getElementById('panel-title').textContent"), "|", b.js("document.getElementById('panel-sub').textContent"), "rows", b.js("document.querySelectorAll('#panel-body .ws-item').length"))
b.shot("panel_logs.png")
# 返回
b.js("document.getElementById('panel-back').click()")
time.sleep(0.6)
print("back: chat visible", b.js("!document.getElementById('chat').hidden"), "composer", b.js("getComputedStyle(document.querySelector('.composer')).display"))
