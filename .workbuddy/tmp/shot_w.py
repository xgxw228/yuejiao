import sys, time
sys.path.insert(0, r'D:\项目1\.workbuddy\tmp')
from cdpkit import Browser

URL = "http://127.0.0.1:8000/login?logout=1"

def run(w, h, tag, ys):
    b = Browser(w, h)
    try:
        b.cmd("Page.enable"); b.cmd("Runtime.enable")
        b.cmd("Page.navigate", {"url": URL})
        time.sleep(2.6)
        print(tag,
              "| hero:", b.js("(()=>{const i=document.querySelector('.hero-bg img');return i&&i.naturalWidth})()"),
              "| docH:", b.js("document.documentElement.scrollHeight"),
              "| 横向溢出:", b.js("document.documentElement.scrollWidth > innerWidth + 1"))
        for name, y in ys:
            b.js("window.scrollTo(0, %d)" % y)
            time.sleep(1.0)
            b.shot("%s_%s.png" % (tag, name))
        b.js("window.scrollTo(0,0)"); time.sleep(0.5)
    finally:
        b.close()

run(1440, 900, "w", [("01", 0), ("02", 700), ("03", 1250), ("04", 2050),
                     ("05", 2700), ("06", 3400), ("07", 4000), ("08", 4560)])
