import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
open_page(b, "http://127.0.0.1:8000/login?t=1", 1160, 740)
time.sleep(0.8); b.js("localStorage.clear()")
open_page(b, "http://127.0.0.1:8000/login?t=2", 1160, 740)
time.sleep(1.0)
b.js("document.querySelectorAll('#roleCards .role-card')[2].click()")  # 员工 陈老师
time.sleep(0.3)
b.js("document.getElementById('form').requestSubmit()")
time.sleep(3.0)
print("url:", b.js("location.pathname"))
b.shot("teal_demo.png")
b.js("document.getElementById('logout-btn').click()")
time.sleep(1.5)
