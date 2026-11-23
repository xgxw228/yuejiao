import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

b = Browser()
open_page(b, "http://127.0.0.1:8000/login?l2=1", 1200, 780)
time.sleep(0.7); b.js("localStorage.clear()")
open_page(b, "http://127.0.0.1:8000/login?l2=2", 1200, 780)
time.sleep(1.0)
b.js("document.getElementById('csFab').click()")
time.sleep(0.4)
b.js("document.getElementById('csInput').value='我是周女士，电话13500001234，想了解德国双元制'; document.getElementById('csForm').requestSubmit();")
time.sleep(2.6)
print("reply:", b.js("document.querySelector('#csBody .cs-msg:last-child').textContent"))
b.shot("lead2_reply.png")
