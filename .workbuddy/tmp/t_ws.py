import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

b = Browser()
open_page(b, "http://127.0.0.1:8000/login?ws=1", 1280, 760)
time.sleep(0.8); b.js("localStorage.clear()")
open_page(b, "http://127.0.0.1:8000/login?ws=2", 1280, 760)
time.sleep(1.0)
b.js("document.querySelectorAll('#roleCards .role-card')[3].click()")  # 顾问 陈老师
time.sleep(0.3)
b.js("document.getElementById('form').requestSubmit()")
time.sleep(3.0)
print("path:", b.js("location.pathname"))
print("ws btn:", b.js("document.getElementById('ws-btn').hidden"), b.js("document.getElementById('ws-label').textContent"))
print("badge:", b.js("document.getElementById('ws-badge').hidden + '/' + document.getElementById('ws-badge').textContent"))
b.js("document.getElementById('ws-btn').click()")
time.sleep(2.0)
print("title:", b.js("document.getElementById('ws-title').textContent"))
print("sub:", b.js("document.getElementById('ws-sub').textContent"))
print("kpis:", b.js("Array.from(document.querySelectorAll('.ws-kpi')).map(e=>e.innerText.replace(/\n/g,'/')).join(' | ')"))
print("items:", b.js("document.querySelectorAll('#ws-body .ws-item').length"))
print("first:", b.js("(document.querySelector('#ws-body .ws-item')||{}).innerText?.slice(0,80)"))
b.shot("ws_consultant.png")
