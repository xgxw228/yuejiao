import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

b = Browser()
open_page(b, "http://127.0.0.1:8000/login?chk=1", 1080, 608)
time.sleep(1.2)
print("cols:", b.js("getComputedStyle(document.querySelector('.hero')).gridTemplateColumns"))
print("card box:", b.js("JSON.stringify(document.querySelector('.hero-right .card').getBoundingClientRect())"))
print("h1 box:", b.js("JSON.stringify(document.querySelector('.hero-left h1').getBoundingClientRect())"))
print("overflowX:", b.js("document.documentElement.scrollWidth + '/' + window.innerWidth"))
b.shot("ck_login_1080.png")
open_page(b, "http://127.0.0.1:8000/login?chk=2", 1440, 900)
time.sleep(1.0)
b.shot("ck_login_1440.png")
