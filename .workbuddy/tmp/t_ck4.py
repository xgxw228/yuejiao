import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
open_page(b, "http://127.0.0.1:8000/login?v=4", 1080, 608)
time.sleep(1)
b.shot("final_login_1080.png")
b.js("document.getElementById('roleCards').children[0].click()")
time.sleep(0.3)
b.js("document.getElementById('form').requestSubmit()")
time.sleep(2.5)
print("url:", b.js("location.pathname"))
print("kpi:", b.js("document.body.innerText.match(/线索|学员|智能体/g)?'has':'no'"))
b.shot("final_admin_after.png")
