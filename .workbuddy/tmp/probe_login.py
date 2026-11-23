import sys, time
sys.path.insert(0, r'D:\项目1\.workbuddy\tmp')
from cdpkit import Browser

JS = """
(() => {
  const r = s => {
    const e = document.querySelector(s);
    if (!e) return s + ': none';
    const b = e.getBoundingClientRect(), cs = getComputedStyle(e);
    return s + ': x=' + Math.round(b.x) + ' w=' + Math.round(b.width)
         + ' y=' + Math.round(b.y) + ' h=' + Math.round(b.height)
         + ' display=' + cs.display;
  };
  const p = document.querySelector('.panel');
  const f = document.getElementById('form').getBoundingClientRect();
  return [
    r('.top'), r('.main'), r('.copy'), r('.shot'), r('.panel'), r('.foot'),
    'form: y=' + Math.round(f.y) + ' h=' + Math.round(f.height),
    'panel clientH=' + p.clientHeight + ' scrollH=' + p.scrollHeight
      + ' overflow=' + (p.scrollHeight > p.clientHeight),
    'panel scrollTop=' + p.scrollTop,
    'viewport=' + innerWidth + 'x' + innerHeight
  ].join('\\n');
})()
"""

for w, h in [(1440, 900), (1080, 608), (1366, 768), (1280, 720)]:
    b = Browser(w, h)
    try:
        b.cmd("Page.enable"); b.cmd("Runtime.enable")
        b.cmd("Page.navigate", {"url": "http://127.0.0.1:8000/login?logout=1"})
        time.sleep(2.2)
        print("=" * 20, w, "x", h)
        print(b.js(JS))
        b.shot("probe_%dx%d.png" % (w, h))
    finally:
        b.close()
