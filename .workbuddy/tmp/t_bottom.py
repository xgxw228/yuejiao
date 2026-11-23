import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
open_page(b, "http://127.0.0.1:8000/login?b=1", 1440, 900)
time.sleep(0.8); b.js("localStorage.clear()")
open_page(b, "http://127.0.0.1:8000/login?b=2", 1440, 900)
time.sleep(1.5)
b.js("window.scrollTo(0, document.body.scrollHeight)")
time.sleep(1.0)
b.shot("login_bottom2.png")
print("path:", b.js("location.pathname"))
