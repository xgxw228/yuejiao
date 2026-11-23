import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

b = Browser()
open_page(b, "http://127.0.0.1:8000/login?g=1", 1180, 700)
time.sleep(0.8); b.js("localStorage.clear()")
open_page(b, "http://127.0.0.1:8000/login?g=2", 1180, 700)
time.sleep(1.2)
b.js("document.querySelectorAll('#roleCards .role-card')[2].click()")
time.sleep(0.4)
print("acct:", b.js("document.getElementById('username').value"))
b.js("document.getElementById('form').requestSubmit()")
time.sleep(3.0)
print("1 teacher ->", b.js("location.pathname"))
print("   header:", b.js("document.querySelector('header')?document.querySelector('header').innerText.split('\n').slice(0,3).join(' | '):'-'"))
b.shot("g_demo_teacher.png")

b.js("document.getElementById('logout-btn').click()")
time.sleep(2.5)
print("2 logout ->", b.js("location.pathname + location.search"))
print("   videos:", b.js("document.querySelectorAll('video').length"),
      "| modal:", b.js("document.getElementById('modal')?document.getElementById('modal').classList.contains('open'):'-'"))
b.shot("g_portal_after_logout.png")

b.js("document.getElementById('loginLink').click()")
time.sleep(2.2)
print("3 loginLink ->", b.js("location.pathname"))
b.shot("g_login_after_return.png")
