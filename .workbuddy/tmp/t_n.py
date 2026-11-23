import sys, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

URL = "http://127.0.0.1:8000/login"
shots = [(1440, 900, "n_1440"), (1366, 768, "n_1366"), (1080, 608, "n_1080"),
         (430, 900, "n_430"), (900, 1200, "n_900")]

b = Browser()
for w, h, name in shots:
    open_page(b, URL, w, h)
    time.sleep(1.2)
    b.shot(f"{name}.png")
    info = b.js("""(function(){var d=document.documentElement;
      return {sw:d.scrollWidth, cw:d.clientWidth, sh:d.scrollHeight,
        hero:document.querySelector('.hero').getBoundingClientRect().height};})()""")
    print(name, info)

# 整页长图
open_page(b, URL, 1440, 900)
time.sleep(1)
b.cmd("Emulation.setDeviceMetricsOverride", {"width":1440,"height":900,"deviceScaleFactor":1,"mobile":False})
h = b.js("document.documentElement.scrollHeight")
b.cmd("Emulation.setDeviceMetricsOverride", {"width":1440,"height":int(h),"deviceScaleFactor":1,"mobile":False})
time.sleep(1.5)
b.js("window.scrollTo(0,document.body.scrollHeight)"); time.sleep(1.2)
b.js("window.scrollTo(0,0)"); time.sleep(0.8)
b.shot("n_full.png")
print("full height", h)
b.close()
