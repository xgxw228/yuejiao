import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

b = Browser()
open_page(b, "http://127.0.0.1:8000/login?f=1", 1180, 700)
time.sleep(0.8); b.js("localStorage.clear()")

# 老师登录
open_page(b, "http://127.0.0.1:8000/login?f=2", 1180, 700)
time.sleep(1.2)
b.js("document.getElementById('username').value='teacher001'; document.getElementById('password').value='123456'; document.getElementById('form').requestSubmit();")
time.sleep(2.5)
print("1 teacher ->", b.js("location.pathname"))

# 中台点退出
b.js("document.getElementById('logout-btn').click()")
time.sleep(2.0)
print("2 logout ->", b.js("location.pathname + location.search"))
print("   videos:", b.js("document.querySelectorAll('video').length"), "modal:", b.js("document.getElementById('modal').classList.contains('open')"))
b.shot("f_portal_after_logout.png")

# 门户点登录
b.js("document.getElementById('loginLink').click()")
time.sleep(2.0)
print("3 portal login ->", b.js("location.pathname"))
print("   card right x:", b.js("document.querySelector('.hero-right .card').getBoundingClientRect().x"))

# 管理员登录
b.js("document.getElementById('roleCards').children[0].click()")
time.sleep(0.3)
b.js("document.getElementById('form').requestSubmit()")
time.sleep(2.5)
print("4 admin ->", b.js("location.pathname"))

b.js("document.getElementById('logout').click()")
time.sleep(2.0)
print("5 admin logout ->", b.js("location.pathname + location.search"))
b.shot("f_portal_after_admin_logout.png")
