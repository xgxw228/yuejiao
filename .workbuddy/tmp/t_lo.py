import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
open_page(b, "http://127.0.0.1:8000/?logout=1", 1080, 608)
time.sleep(2.2)
print("modal open:", b.js("document.getElementById('modal').classList.contains('open')"))
print("headline:", b.js("document.querySelector('.h1, h1')?document.querySelector('h1').textContent.slice(0,20):'-'"))
print("videos:", b.js("document.querySelectorAll('video').length"))
b.shot("ck_logout1.png")
