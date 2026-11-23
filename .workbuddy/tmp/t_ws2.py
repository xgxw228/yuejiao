import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

b = Browser()
open_page(b, "http://127.0.0.1:8000/login?w2=1", 1280, 800)
time.sleep(0.7); b.js("localStorage.clear()")
open_page(b, "http://127.0.0.1:8000/login?w2=2", 1280, 800)
time.sleep(1.0)
b.js("document.querySelectorAll('#roleCards .role-card')[3].click()")
time.sleep(0.3); b.js("document.getElementById('form').requestSubmit()")
time.sleep(2.6)
b.js("document.getElementById('ws-btn').click()")
time.sleep(1.8)
b.shot("ws_staff.png")
print("kpi count:", b.js("document.querySelectorAll('.ws-kpi').length"))
print("lead0 brief:", b.js("document.querySelectorAll('#ws-body .ws-item .ws-meta')[1].textContent"))
# 写跟进
b.js("var box=document.querySelector('#ws-body .ws-follow'); box.querySelector('.note').value='已加微信，约周六到校面谈'; box.querySelector('.save').click();")
time.sleep(2.2)
print("toast:", b.js("document.getElementById('toast').textContent"))
print("history:", b.js("(document.querySelector('#ws-body .ws-details pre')||{}).textContent"))
b.shot("ws_staff_saved.png")
