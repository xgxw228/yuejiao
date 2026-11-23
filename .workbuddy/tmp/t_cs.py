import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
open_page(b, "http://127.0.0.1:8000/login?cs=1", 1080, 608)
time.sleep(1.0)
b.js("localStorage.clear()")
b.js("document.getElementById('csFab').click()")
time.sleep(0.5)
bjs = b.js
print("panel:", b.js("document.getElementById('csPanel').getBoundingClientRect().toJSON?JSON.stringify(document.getElementById('csPanel').getBoundingClientRect()):'-'"))
b.shot("cs_open.png")

b.js("document.querySelectorAll('.cs-chip')[0].click()")
time.sleep(12)
print("msgs:", b.js("document.querySelectorAll('.cs-msg').length"))
print("last:", b.js("document.querySelector('#csBody .cs-msg:last-child').textContent.slice(0,120)"))
b.shot("cs_answer.png")
