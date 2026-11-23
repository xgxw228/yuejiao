import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
open_page(b, "http://127.0.0.1:8000/login?sd=1", 1280, 800)
time.sleep(0.7); b.js("localStorage.clear()")
open_page(b, "http://127.0.0.1:8000/login?sd=2", 1280, 800)
time.sleep(1.0)
b.js("document.querySelectorAll('#roleCards .role-card')[1].click()")  # 班主任
time.sleep(0.3); b.js("document.getElementById('form').requestSubmit()")
time.sleep(2.8)
print("title:", b.js("document.getElementById('todo-title').textContent"),
      "| count:", b.js("document.getElementById('todo-count').textContent"))
print("todos:", b.js("document.querySelectorAll('#todos .todo').length"))
print("first:", b.js("(document.querySelector('#todos .todo')||{}).innerText"))
print("log btn:", b.js("document.getElementById('log-btn').hidden"), b.js("document.getElementById('log-count').textContent"))
print("header ws btn display:", b.js("getComputedStyle(document.getElementById('ws-btn')).display"))
b.shot("side_teacher.png")
# 通过第一条
b.js("document.querySelector('#todos .todo-a button.ok').click()")
time.sleep(2.5)
print("toast:", b.js("document.getElementById('toast').textContent"))
print("remain:", b.js("document.querySelectorAll('#todos .todo').length"))
# 打开日志
b.js("document.getElementById('log-btn').click()")
time.sleep(1.5)
print("log title:", b.js("document.getElementById('ws-title').textContent"))
print("log sub:", b.js("document.getElementById('ws-sub').textContent"))
print("log rows:", b.js("document.querySelectorAll('#ws-body .ws-item').length"))
print("log first:", b.js("(document.querySelector('#ws-body .ws-item')||{}).innerText"))
b.shot("side_logs.png")
