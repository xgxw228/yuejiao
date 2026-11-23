import sys, time
sys.path.insert(0, r'D:\项目1\.workbuddy\tmp')
from cdpkit import Browser

b = Browser(1440, 980)
try:
    b.cmd("Page.enable"); b.cmd("Runtime.enable")
    b.cmd("Page.navigate", {"url": "https://www.mihoyo.com/"})
    time.sleep(8)
    for i in range(6):
        b.js("window.scrollBy(0, 640)"); time.sleep(1.0)
        b.shot(f"mh_{i}.png")
    print("bodyH:", b.js("document.body.scrollHeight"))
finally:
    b.close()
