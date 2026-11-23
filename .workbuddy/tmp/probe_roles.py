import sys, time
sys.path.insert(0, r'D:\项目1\.workbuddy\tmp')
from cdpkit import Browser

JS = """
(() => {
  const out = [];
  const box = s => {
    const e = document.querySelector(s);
    if (!e) return s + ': MISSING';
    const r = e.getBoundingClientRect();
    return s + ': y=' + Math.round(r.y + scrollY) + ' x=' + Math.round(r.x)
      + ' w=' + Math.round(r.width) + ' h=' + Math.round(r.height)
      + ' display=' + getComputedStyle(e).display
      + ' cols=' + getComputedStyle(e).gridTemplateColumns;
  };
  ['.roles-table', '.role-row.head', '.role-row:nth-child(2)', '.rr-can',
   '#login', '#roles', '.roles', '#flow'].forEach(s => out.push(box(s)));
  const rr = document.querySelector('.role-row:nth-child(2) .rr-can');
  if (rr) out.push('rr-can text: ' + rr.textContent.trim().slice(0, 40));
  out.push('inlineWidth=' + innerWidth);
  return out.join('\\n');
})()
"""

b = Browser(1440, 900)
try:
    b.cmd("Page.enable"); b.cmd("Runtime.enable")
    b.cmd("Page.navigate", {"url": "http://127.0.0.1:8000/login?logout=1"})
    time.sleep(2.6)
    print(b.js(JS))
    print("---- 全页高度", b.js("document.documentElement.scrollHeight"))
finally:
    b.close()
