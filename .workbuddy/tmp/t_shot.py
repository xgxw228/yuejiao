import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
open_page(b, "http://127.0.0.1:8000/demo/?s=9", 1320, 820)
time.sleep(1.6)
print("ws label:", b.js("document.getElementById('ws-label').textContent"))
b.js("document.getElementById('ws-btn').click()")
time.sleep(2.0)
print("title:", b.js("document.getElementById('ws-title').textContent"))
print("sec:", b.js("document.querySelector('.ws-sec-h b').textContent"))
b.shot("final_ws_staff2.png")
