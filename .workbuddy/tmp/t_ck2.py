import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
open_page(b, "http://127.0.0.1:8000/login?v=" + str(int(time.time())), 1080, 608)
time.sleep(1.2)
print("card:", b.js("JSON.stringify(document.querySelector('.hero-right .card').getBoundingClientRect())"))
b.js("document.querySelector('.hero').style.minHeight='640px'")
b.js("window.scrollTo(0,0)")
b.shot("ck2_1080.png")
