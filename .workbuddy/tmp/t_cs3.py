import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page
b = Browser()
open_page(b, "http://127.0.0.1:8000/login?c3=1", 1080, 608)
time.sleep(1.0); b.js("localStorage.clear()")
b.js("document.getElementById('csFab').click()")
time.sleep(0.6)
b.shot("cs3_desktop.png")
print("note h:", b.js("JSON.stringify(document.getElementById('csPanel').querySelector('.cs-note').getBoundingClientRect())"))
print("chips rows:", b.js("Array.from(document.querySelectorAll('.cs-chip')).map(c=>Math.round(c.getBoundingClientRect().top)).join(',')"))

open_page(b, "http://127.0.0.1:8000/login?c3=2", 390, 844)
time.sleep(1.0)
b.js("document.getElementById('csFab').click()")
time.sleep(0.5)
print("fab visible:", b.js("getComputedStyle(document.getElementById('csFab')).display"))
b.shot("cs3_mobile.png")
