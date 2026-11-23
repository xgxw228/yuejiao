import sys, time, json
sys.path.insert(0, r'D:\项目1\.workbuddy\tmp')
from cdpkit import Browser

b = Browser(1440, 980)
try:
    b.cmd("Page.enable")
    b.cmd("Runtime.enable")
    b.cmd("Page.navigate", {"url": "https://www.mihoyo.com/"})
    time.sleep(9)
    # 等懒加载
    for i in range(3):
        b.js("window.scrollBy(0, 700)"); time.sleep(1.2)
    b.js("window.scrollTo(0,0)"); time.sleep(1.5)
    b.shot("mihoyo_top.png")
    info = b.js("""(() => {
      const out = {};
      out.title = document.title;
      out.bodyH = document.body.scrollHeight;
      out.bg = getComputedStyle(document.body).backgroundColor;
      out.fonts = getComputedStyle(document.body).fontFamily;
      const nav = document.querySelector('nav, header, .header, #header');
      out.navHTML = nav ? nav.outerHTML.slice(0, 900) : null;
      out.navRect = nav ? JSON.stringify(nav.getBoundingClientRect()) : null;
      // 顶层区块
      out.sections = [...document.querySelectorAll('body > *, body > * > section, main > *')]
        .slice(0, 25)
        .map(e => {
          const r = e.getBoundingClientRect();
          const cs = getComputedStyle(e);
          return {tag: e.tagName, cls: (e.className||'').toString().slice(0,60),
                  h: Math.round(r.height), bg: cs.backgroundColor, bgImg: (cs.backgroundImage||'').slice(0,80)};
        });
      // 使用的字体族集合
      const fams = new Set();
      [...document.querySelectorAll('h1,h2,h3,p,a,span,div')].slice(0,400).forEach(e=>{
        const f = getComputedStyle(e).fontFamily; if (f) fams.add(f.slice(0,60));
      });
      out.fontFamilies = [...fams].slice(0, 12);
      return JSON.stringify(out, null, 1);
    })()""")
    print(info)
finally:
    b.close()
