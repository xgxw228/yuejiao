import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
open_page(b, "http://127.0.0.1:8000/admin?lg=3", 1360, 860)
time.sleep(2.0)
b.js("document.getElementById('nav-logs').click()")
time.sleep(1.8)
print("sub:", b.js("document.getElementById('log-sub').textContent"))
print("rows:", b.js("document.querySelectorAll('#log-box .log-row').length"))
print("first:", b.js("(document.querySelector('#log-box .log-row')||{}).innerText"))
print("filters:", b.js("document.querySelectorAll('#log-filters button').length"))
b.shot("admin_logs2.png")
