import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
open_page(b, "http://127.0.0.1:8000/login?e=1", 1440, 900)
time.sleep(1.5)
print("login overflow:", b.js("document.documentElement.scrollWidth+'/'+window.innerWidth"))
b.js("window.scrollTo(0, document.body.scrollHeight)")
time.sleep(0.8)
b.shot("login_bottom.png")
open_page(b, "http://127.0.0.1:8000/?e=2", 1440, 900)
time.sleep(2.0)
print("portal videos:", b.js("document.querySelectorAll('video').length"))
