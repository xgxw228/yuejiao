import sys, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

W, H = 1440, 900
b = Browser()
open_page(b, "http://127.0.0.1:8000/login", W, H)
time.sleep(1)
total = b.js("document.documentElement.scrollHeight")
print("total", total)
y = 0
i = 0
while y < total - 50:
    b.js(f"window.scrollTo(0,{y})")
    time.sleep(0.9)
    b.shot(f"s_{i:02d}.png")
    y += H - 80
    i += 1
    if i > 12:
        break
b.close()
