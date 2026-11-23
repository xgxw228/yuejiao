import sys, time
sys.path.insert(0, r'D:\项目1\.workbuddy\tmp')
from cdpkit import Browser

SITES = [
    ("https://qiantu.xdf.cn/", "ref_xdf"),
    ("https://www.eic.org.cn/", "ref_eic"),
]

for url, tag in SITES:
    b = Browser(1440, 900)
    try:
        b.cmd("Page.enable"); b.cmd("Runtime.enable")
        b.cmd("Page.navigate", {"url": url})
        time.sleep(7)
        for i in range(4):
            b.shot(f"{tag}_{i}.png")
            b.cmd("Input.dispatchMouseEvent",
                  {"type": "mouseWheel", "x": 720, "y": 500, "deltaX": 0, "deltaY": 780})
            time.sleep(1.4)
        info = b.js("""(() => {
          const q = s => document.querySelector(s);
          const nav = q('header') || q('nav');
          const nb = nav ? getComputedStyle(nav) : null;
          return JSON.stringify({
            title: document.title,
            bodyH: document.body.scrollHeight,
            navBg: nb ? nb.backgroundColor : null,
            navPos: nb ? nb.position : null,
            navH: nav ? Math.round(nav.getBoundingClientRect().height) : null,
            h1: q('h1') ? getComputedStyle(q('h1')).fontSize + ' / ' + getComputedStyle(q('h1')).fontWeight : null
          });
        })()""")
        print(tag, info)
    except Exception as e:
        print(tag, "FAIL", e)
    finally:
        b.close()
