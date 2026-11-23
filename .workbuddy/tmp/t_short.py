import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
open_page(b, "http://127.0.0.1:8000/login?s=1", 1080, 608)
time.sleep(0.7); b.js("localStorage.clear()")
open_page(b, "http://127.0.0.1:8000/login?s=2", 1080, 608)
time.sleep(1.2)
print("cards:", b.js("document.querySelectorAll('.role-card').length"))
print("card box:", b.js("JSON.stringify(document.querySelector('.card').getBoundingClientRect())"))
print("overflow:", b.js("document.documentElement.scrollWidth+'/'+window.innerWidth"), b.js("document.documentElement.scrollHeight+'/'+window.innerHeight"))
b.shot("login_1080x608.png")
