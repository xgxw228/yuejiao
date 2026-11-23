import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
open_page(b, "http://127.0.0.1:8000/login?c4=1", 1180, 780)
time.sleep(1.0); b.js("localStorage.clear()")
b.js("document.getElementById('csFab').click()")
time.sleep(0.5)
b.js("document.querySelectorAll('.cs-chip')[0].click()")
time.sleep(14)
b.shot("cs_final.png")
print("note lines h:", b.js("document.querySelector('#csPanel .cs-note').getBoundingClientRect().height"))
print("msg count:", b.js("document.querySelectorAll('.cs-msg').length"))
print("typing left:", b.js("document.querySelectorAll('.cs-msg.typing').length"))
