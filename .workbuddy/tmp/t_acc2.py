import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

b = Browser()
try:
    for w, h, name in [(1440, 900, "acc_l1440.png"), (1080, 608, "acc_l1080.png"), (390, 844, "acc_l390.png")]:
        open_page(b, f"http://127.0.0.1:8000/login?z={w}", w, h)
        b.js("localStorage.clear()")
        open_page(b, f"http://127.0.0.1:8000/login?z={w}b", w, h)
        time.sleep(1.0)
        print(name, b.js("JSON.stringify((function(){var c=document.querySelector('.card').getBoundingClientRect();var r=document.getElementById('roleCards');return {card:[Math.round(c.top),Math.round(c.height)],view:%d,h:r.clientHeight,scroll:r.scrollHeight,btn:Math.round(document.getElementById('submit').getBoundingClientRect().bottom)}})())" % h))
        b.shot(name)

    # 学员视角成绩 + 手机面板
    open_page(b, "http://127.0.0.1:8000/login?s=1", 1440, 900)
    b.js("localStorage.clear()")
    open_page(b, "http://127.0.0.1:8000/login?s=2", 1440, 900)
    time.sleep(1.0)
    b.js("Array.from(document.querySelectorAll('#roleCards .role-card')).find(e=>e.dataset.account==='stu004').click()")
    time.sleep(0.3)
    b.js("document.getElementById('form').requestSubmit()")
    time.sleep(2.8)
    print("navs:", b.js("Array.from(document.querySelectorAll('#navs .nav')).map(e=>e.innerText.replace(/\\n/g,' ')).join(' | ')"))
    b.js("document.querySelectorAll('#navs .nav')[1].click()")
    time.sleep(1.5)
    print("student grades:", b.js("document.getElementById('panel-title').textContent"), "|", b.js("document.getElementById('panel-sub').textContent"))
    print("students:", b.js("Array.from(document.querySelectorAll('#panel-body .ws-item-h b')).map(e=>e.textContent).join(',')"))
    print("forms:", b.js("document.querySelectorAll('#panel-body .g-form').length"))
    b.shot("acc_grades_stu.png")

    # 手机
    open_page(b, "http://127.0.0.1:8000/demo/?m=1", 390, 844)
    time.sleep(2.0)
    print("mobile overflow:", b.js("document.documentElement.scrollWidth + '/' + innerWidth"))
    b.js("document.querySelectorAll('#navs .nav')[1].click()")
    time.sleep(1.6)
    print("mobile panel:", b.js("document.getElementById('panel-title').textContent"))
    b.shot("acc_grades_mobile.png")
finally:
    b.close()
