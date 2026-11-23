import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

b = Browser()
open_page(b, "http://127.0.0.1:8000/login?w3=1", 1280, 800)
time.sleep(0.7); b.js("localStorage.clear()")
open_page(b, "http://127.0.0.1:8000/login?w3=2", 1280, 800)
time.sleep(1.0)
b.js("document.querySelectorAll('#roleCards .role-card')[1].click()")  # 班主任 李老师
time.sleep(0.3); b.js("document.getElementById('form').requestSubmit()")
time.sleep(2.6)
print("path:", b.js("location.pathname"), "| label:", b.js("document.getElementById('ws-label').textContent"))
b.js("document.getElementById('ws-btn').click()")
time.sleep(1.8)
print("title:", b.js("document.getElementById('ws-title').textContent"))
print("kpis:", b.js("Array.from(document.querySelectorAll('.ws-kpi .v')).map(e=>e.textContent).join('/')"))
print("sections:", b.js("Array.from(document.querySelectorAll('.ws-sec-h b')).map(e=>e.textContent).join(' | ')"))
print("leave items:", b.js("document.querySelectorAll('.ws-acts').length"))
b.shot("ws_teacher.png")
# 通过第一条
b.js("document.querySelector('.ws-acts button.ok').click()")
time.sleep(2.4)
print("toast:", b.js("document.getElementById('toast').textContent"))
b.shot("ws_teacher_after.png")

# 学员
open_page(b, "http://127.0.0.1:8000/login?w3=3", 1280, 800)
time.sleep(0.8); b.js("localStorage.clear()")
open_page(b, "http://127.0.0.1:8000/login?w3=4", 1280, 800)
time.sleep(1.0)
b.js("document.querySelectorAll('#roleCards .role-card')[2].click()")  # 学员 张三
time.sleep(0.3); b.js("document.getElementById('form').requestSubmit()")
time.sleep(2.6)
print("student path:", b.js("location.pathname"), "| label:", b.js("document.getElementById('ws-label').textContent"))
b.js("document.getElementById('ws-btn').click()")
time.sleep(1.8)
print("student title:", b.js("document.getElementById('ws-title').textContent"))
print("student kpis:", b.js("Array.from(document.querySelectorAll('.ws-kpi .v')).map(e=>e.textContent).join('/')"))
print("student sections:", b.js("Array.from(document.querySelectorAll('.ws-sec-h b')).map(e=>e.textContent).join(' | ')"))
b.shot("ws_student.png")
