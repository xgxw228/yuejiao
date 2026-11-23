import sys, time
sys.path.insert(0, r'D:\项目1\.workbuddy\tmp')
from cdpkit import Browser

URL = "http://127.0.0.1:8000/login?logout=1"

def run(w, h, tag, shots):
    b = Browser(w, h)
    try:
        b.cmd("Page.enable"); b.cmd("Runtime.enable")
        b.cmd("Page.navigate", {"url": URL})
        time.sleep(2.6)
        print(tag, "| hero img:", b.js("(()=>{const i=document.querySelector('.hero-bg img');return i? i.naturalWidth+'x'+i.naturalHeight : 'none'})()"),
              "| docH:", b.js("document.documentElement.scrollHeight"),
              "| 横向溢出:", b.js("document.documentElement.scrollWidth > innerWidth + 1"))
        for i, (name, y) in enumerate(shots):
            b.js("window.scrollTo(0, %d)" % y)
            time.sleep(1.1)
            b.shot("%s_%s.png" % (tag, name))
        b.js("window.scrollTo(0,0)"); time.sleep(0.6)
        b.shot("%s_hero.png" % tag)
    finally:
        b.close()

# 1440x900：按视口高度切片
run(1440, 900, "v3", [("s1", 900), ("s2", 1750), ("s3", 2600), ("s4", 3500), ("s5", 4300)])
