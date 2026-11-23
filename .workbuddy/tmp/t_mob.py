import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
open_page(b, "http://127.0.0.1:8000/demo/?m=1", 390, 844)
time.sleep(1.6)
print("overflow:", b.js("document.documentElement.scrollWidth+'/'+window.innerWidth"))
print("head:", b.js("JSON.stringify(document.querySelector('.head').getBoundingClientRect())"))
print("btns:", b.js("Array.from(document.querySelectorAll('.head-right > *')).filter(e=>getComputedStyle(e).display!=='none').map(e=>e.textContent.trim().slice(0,6)+':'+Math.round(e.getBoundingClientRect().width)).join(' | ')"))
b.shot("mob_head.png")
