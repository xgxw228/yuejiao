import sys, time
sys.path.insert(0, r'D:\项目1\.workbuddy\tmp')
from cdpkit import Browser

b = Browser(1440, 900)
try:
    b.cmd("Page.enable"); b.cmd("Runtime.enable")
    b.cmd("Page.navigate", {"url": "https://www.yhwins.com/"})
    time.sleep(7)
    for i in range(1, 8):
        b.cmd("Input.dispatchMouseEvent", {"type": "mouseWheel", "x": 720, "y": 500, "deltaX": 0, "deltaY": 820})
        time.sleep(1.5)
        b.shot(f"yhb_{i}.png")
    print("done")
finally:
    b.close()
