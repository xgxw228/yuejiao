import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
open_page(b, "http://127.0.0.1:8000/demo/?s3=1", 1280, 800)
time.sleep(1.8)
print("student first:", b.js("document.querySelector('#todos .todo').innerText.replace(/\n/g,' / ')"))
b.shot("side_student2.png")
# 点第一条打开面板
b.js("document.querySelector('#todos .todo').click()")
time.sleep(1.8)
print("panel title:", b.js("document.getElementById('ws-title').textContent"))
b.shot("side_student_panel2.png")
# 关闭并打开日志
b.js("document.getElementById('ws-close').click()")
time.sleep(0.4)
b.js("document.getElementById('log-btn').click()")
time.sleep(1.6)
print("logs:", b.js("document.querySelectorAll('#ws-body .ws-item').length"), b.js("document.getElementById('ws-sub').textContent"))
b.shot("student_logs.png")
