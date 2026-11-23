import sys, time
sys.path.insert(0, r'D:\项目1\.workbuddy\tmp')
from cdpkit import Browser

b = Browser(1440, 900)
try:
    b.cmd("Page.enable"); b.cmd("Runtime.enable")
    b.cmd("Page.navigate", {"url": "https://www.yhwins.com/"})
    time.sleep(7)
    b.js("window.scrollTo(0,0)"); time.sleep(1)
    b.shot("yh_0.png")
    for i in range(1, 7):
        b.js("window.scrollBy(0, 860)"); time.sleep(1.4)
        b.shot(f"yh_{i}.png")
    print("bodyH", b.js("document.body.scrollHeight"))
    print(b.js("""(() => {
      const s = [];
      s.push('body bg: ' + getComputedStyle(document.body).backgroundColor);
      const nav = document.querySelector('header, .header, nav');
      if (nav) { const cs = getComputedStyle(nav); s.push('nav bg: ' + cs.backgroundColor + ' h=' + nav.getBoundingClientRect().height); }
      // 找主色
      const colors = {};
      document.querySelectorAll('*').forEach(e => {
        const cs = getComputedStyle(e);
        const c = cs.backgroundColor;
        if (c && c !== 'rgba(0, 0, 0, 0)') colors[c] = (colors[c]||0)+1;
      });
      s.push('TOP bg colors: ' + JSON.stringify(Object.entries(colors).sort((a,b)=>b[1]-a[1]).slice(0,8)));
      const fs = {};
      document.querySelectorAll('h1,h2,h3,.num,strong').forEach(e=>{
        const cs = getComputedStyle(e);
        fs[cs.fontSize + '/' + cs.fontWeight + '/' + cs.color] = (fs[cs.fontSize+'/'+cs.fontWeight+'/'+cs.color]||0)+1;
      });
      s.push('HEAD font sizes: ' + JSON.stringify(Object.entries(fs).sort((a,b)=>b[1]-a[1]).slice(0,10)));
      s.push('body font: ' + getComputedStyle(document.body).fontFamily);
      return s.join('\n');
    })()"""))
finally:
    b.close()
