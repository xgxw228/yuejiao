import sys, time
sys.path.insert(0, r'D:\项目1\.workbuddy\tmp')
from cdpkit import Browser

for url, tag in [("https://www.yhwins.com/about.html", "about"),
                 ("https://www.yhwins.com/global.html", "global")]:
    b = Browser(1440, 900)
    try:
        b.cmd("Page.enable"); b.cmd("Runtime.enable")
        b.cmd("Page.navigate", {"url": url})
        time.sleep(6)
        b.shot(f"yh_{tag}_0.png")
        for i in range(1, 5):
            b.cmd("Input.dispatchMouseEvent", {"type": "mouseWheel", "x": 720, "y": 500, "deltaX": 0, "deltaY": 780})
            time.sleep(1.3)
            b.shot(f"yh_{tag}_{i}.png")
        print("ok", tag)
    finally:
        b.close()
