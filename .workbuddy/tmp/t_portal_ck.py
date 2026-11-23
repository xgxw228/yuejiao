import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
open_page(b, "http://127.0.0.1:8000/", 1080, 608)
time.sleep(2.5)
print("videos:", b.js("document.querySelectorAll('video').length"))
print("has modal open:", b.js("document.getElementById('modal')?document.getElementById('modal').classList.contains('open'):'no-modal'"))
print("loginLink href:", b.js("document.getElementById('loginLink')?document.getElementById('loginLink').getAttribute('href'):'-'"))
b.shot("ck_portal_root.png")
