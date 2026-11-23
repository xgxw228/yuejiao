import sys, time
sys.path.insert(0, r'D:\项目1\.workbuddy\tmp')
from cdpkit import Browser

BASE = "file:///D:/%E9%A1%B9%E7%9B%AE1/.workbuddy/tmp/mock/"
jobs = [
    ("a.html", "mock_A.png", None),
    ("b.html", "mock_B_closed.png", None),
    ("b.html", "mock_B_open.png", "document.body.classList.add('open')"),
    ("c.html", "mock_C_top.png", None),
    ("c.html", "mock_C_down.png", "window.scrollTo(0, window.innerHeight)"),
    ("d.html", "mock_D.png", None),
    ("e.html", "mock_E.png", None),
]
for page, out, js in jobs:
    b = Browser(1440, 900)
    try:
        b.cmd("Page.enable"); b.cmd("Runtime.enable")
        b.cmd("Page.navigate", {"url": BASE + page})
        time.sleep(2.2)
        if js:
            b.js(js); time.sleep(1.0)
        b.shot(out)
        print("ok", out)
    except Exception as e:
        print("fail", out, e)
    finally:
        b.close()
