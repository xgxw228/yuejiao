import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
for w,h,name in ((1080,640,"1080"),(1440,900,"1440")):
    open_page(b, "http://127.0.0.1:8000/demo/?w8="+name, w, h)
    time.sleep(1.6)
    print(name, "overflow:", b.js("document.documentElement.scrollWidth+'/'+window.innerWidth"))
    print(name, "head h:", b.js("document.querySelector('.head').getBoundingClientRect().height"))
    print(name, "btn tops:", b.js("Array.from(document.querySelectorAll('.head-right .ghost-btn')).map(e=>Math.round(e.getBoundingClientRect().height)).join(',')"))
    b.shot("ws_head_%s.png" % name)
