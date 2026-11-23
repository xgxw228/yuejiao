import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
open_page(b, "http://127.0.0.1:8000/login?c2=1", 1080, 608)
time.sleep(1.0); b.js("localStorage.clear()")
b.js("document.getElementById('csFab').click()")
time.sleep(0.6)
b.shot("cs2_open_1080.png")
print("overflowX:", b.js("document.documentElement.scrollWidth+'/'+window.innerWidth"))
print("panel:", b.js("JSON.stringify(document.getElementById('csPanel').getBoundingClientRect())"))

# 需要登录的提问
b.js("document.getElementById('csInput').value='帮我查一下我孩子的进度'; document.getElementById('csForm').requestSubmit();")
time.sleep(1.2)
print("guard:", b.js("document.querySelector('#csBody .cs-msg:last-child').textContent.slice(0,40)"))
b.shot("cs2_guard.png")

open_page(b, "http://127.0.0.1:8000/login?c2=2", 390, 844)
time.sleep(1.0)
b.js("document.getElementById('csFab').click()")
time.sleep(0.5)
print("m overflowX:", b.js("document.documentElement.scrollWidth+'/'+window.innerWidth"))
b.shot("cs2_mobile.png")
