import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
open_page(b, "http://127.0.0.1:8000/admin?lg=9", 1360, 860)
time.sleep(2.2)
b.js("document.getElementById('nav-logs').click()")
time.sleep(1.8)
print("sub:", b.js("document.getElementById('log-sub').textContent"))
print("rows:", b.js("document.querySelectorAll('#log-box .log-row').length"))
print("first3:", b.js("Array.from(document.querySelectorAll('#log-box .log-row')).slice(0,3).map(e=>e.innerText.split('\n').slice(0,3).join(' / ')).join(' || ')"))
# 筛选审批
buttons = b.js("Array.from(document.querySelectorAll('#log-filters button')).map(x=>x.textContent).join('|')")
print("filters:", buttons)
b.js("Array.from(document.querySelectorAll('#log-filters button')).find(x=>x.textContent==='请假审批').click()")
time.sleep(1.2)
print("after filter:", b.js("document.querySelectorAll('#log-box .log-row').length"), b.js("document.getElementById('log-sub').textContent"))
b.shot("admin_logs3.png")
