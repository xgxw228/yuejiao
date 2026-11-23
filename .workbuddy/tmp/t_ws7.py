import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
open_page(b, "http://127.0.0.1:8000/login?w7=1", 1080, 640)
time.sleep(0.7); b.js("localStorage.clear()")
open_page(b, "http://127.0.0.1:8000/login?w7=2", 1080, 640)
time.sleep(1.0)
b.js("document.querySelectorAll('#roleCards .role-card')[1].click()")  # 班主任
time.sleep(0.3); b.js("document.getElementById('form').requestSubmit()")
time.sleep(2.6)
print("overflowX:", b.js("document.documentElement.scrollWidth+'/'+window.innerWidth"))
print("head-right:", b.js("Array.from(document.querySelectorAll('.head-right > *')).map(e=>(e.textContent||'').trim().slice(0,6)).join(' | ')"))
print("empty hint:", b.js("Array.from(document.querySelectorAll('.empty-text')).map(e=>e.textContent).join(' || ')"))
b.shot("ws_1080_teacher.png")
