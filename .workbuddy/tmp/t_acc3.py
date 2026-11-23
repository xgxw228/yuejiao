import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page


def login_as(b, acc, w=1440, h=900):
    open_page(b, "http://127.0.0.1:8000/login?r=" + acc, w, h)
    b.js("localStorage.clear()")
    open_page(b, "http://127.0.0.1:8000/login?r=" + acc + "-2", w, h)
    time.sleep(1.0)
    b.js("Array.from(document.querySelectorAll('#roleCards .role-card')).find(e=>e.dataset.account==='%s').click()" % acc)
    time.sleep(0.3)
    b.js("document.getElementById('form').requestSubmit()")
    time.sleep(3.0)
    print("  login ->", b.js("location.pathname"), b.js("(document.getElementById('me-name')||{}).textContent"))


def navs(b):
    return b.js("Array.from(document.querySelectorAll('#navs .nav')).map(function(e){return e.innerText.split('\\n').join(' ')}).join(' | ')")


b = Browser()
try:
    print("== admin ==")
    login_as(b, "admin")
    print("navs:", navs(b))
    b.js("document.querySelectorAll('#navs .nav')[1].click()")
    time.sleep(1.8)
    print("title:", b.js("document.getElementById('panel-title').textContent"))
    print("sub:", b.js("document.getElementById('panel-sub').textContent"))
    print("cards:", b.js("document.querySelectorAll('#panel-body .ws-item').length"),
          "forms:", b.js("document.querySelectorAll('#panel-body .g-form').length"),
          "del:", b.js("document.querySelectorAll('.g-del').length"))
    b.shot("acc_grades_admin.png")

    print("== staff ==")
    login_as(b, "emp006")
    print("navs:", navs(b))
    b.shot("acc_staff_nav.png")

    print("== teacher ==")
    login_as(b, "emp001")
    print("navs:", navs(b))
    b.js("document.querySelectorAll('#navs .nav')[0].click()")
    time.sleep(1.6)
    print("leaves:", b.js("Array.from(document.querySelectorAll('#panel-body .ws-item b')).map(function(e){return e.textContent}).join(',')"))
    b.shot("acc_teacher_leaves.png")
finally:
    b.close()
