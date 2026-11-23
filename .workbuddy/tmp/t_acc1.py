import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

b = Browser()
try:
    open_page(b, "http://127.0.0.1:8000/login?acc=1", 1440, 900)
    b.js("localStorage.clear()")
    open_page(b, "http://127.0.0.1:8000/login?acc=2", 1440, 900)
    time.sleep(1.2)
    print("cards:", b.js("document.querySelectorAll('#roleCards .role-card').length"))
    print("groups:", b.js("Array.from(document.querySelectorAll('#roleCards .role-group')).map(e=>e.innerText.replace(/\\n/g,' ')).join(' | ')"))
    print("box:", b.js("JSON.stringify((function(){var r=document.getElementById('roleCards').getBoundingClientRect();var c=document.querySelector('.card').getBoundingClientRect();return {roles:[r.top,r.height,r.width],card:[c.top,c.height],scroll:document.getElementById('roleCards').scrollHeight}})())"))
    b.js("document.querySelectorAll('#roleCards .role-card')[16].scrollIntoView({block:'nearest'})")
    b.shot("acc_login_1440.png")

    # 换 1080x608 看是否可用
    open_page(b, "http://127.0.0.1:8000/login?acc=3", 1080, 608)
    time.sleep(1.0)
    print("btn visible 1080:", b.js("JSON.stringify(document.getElementById('submit').getBoundingClientRect())"))
    b.shot("acc_login_1080.png")

    # 选赵敏登录
    b.js("(function(){var t=Array.from(document.querySelectorAll('#roleCards .role-card')).find(e=>e.dataset.account==='emp003');t.click();})()")
    time.sleep(0.4)
    print("msg:", b.js("document.getElementById('msg').textContent"))
    b.js("document.getElementById('form').requestSubmit()")
    time.sleep(3.0)
    print("url:", b.js("location.pathname"))
    print("navs:", b.js("Array.from(document.querySelectorAll('#navs .nav')).map(e=>e.innerText.replace(/\\n/g,' ')).join(' | ')"))
    print("user:", b.js("document.getElementById('me-name').textContent + ' / ' + document.getElementById('me-role').textContent"))
    b.js("document.querySelectorAll('#navs .nav')[1].click()")
    time.sleep(1.6)
    print("panel:", b.js("document.getElementById('panel-title').textContent"), "|", b.js("document.getElementById('panel-sub').textContent"))
    print("students:", b.js("Array.from(document.querySelectorAll('#panel-body .ws-item > .ws-item-h b')).map(e=>e.textContent).join(',')"))
    print("forms:", b.js("document.querySelectorAll('#panel-body .g-form').length"))
    b.shot("acc_grades_zhao.png")

    # 录一条成绩：给第一个学生
    b.js("(function(){var f=document.querySelector('#panel-body .g-form');f.querySelector('[name=course]').value='德语口语';f.querySelector('[name=score]').value='88';f.querySelector('[name=semester]').value='2025-2026 第一学期';f.requestSubmit();})()")
    time.sleep(2.2)
    print("toast:", b.js("document.getElementById('toast').textContent"))
    print("first rows:", b.js("Array.from(document.querySelectorAll('#panel-body .g-row')).slice(0,6).map(e=>e.innerText.replace(/\\n/g,' ')).join(' | ')"))
    b.shot("acc_grades_saved.png")

    # 日志
    b.js("document.querySelectorAll('#navs .nav')[2].click()")
    time.sleep(1.5)
    print("log first:", b.js("document.querySelector('#panel-body .ws-item').innerText.replace(/\\n/g,' / ')"))
finally:
    b.close()
