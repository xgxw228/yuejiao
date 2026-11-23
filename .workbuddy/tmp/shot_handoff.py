import sys, time
sys.path.insert(0, r'D:\项目1\.workbuddy\tmp')
from cdpkit import Browser

b = Browser(500, 900)
try:
    b.cmd("Page.enable"); b.cmd("Runtime.enable")
    b.cmd("Page.navigate", {"url": "http://127.0.0.1:8000/login?logout=1"})
    time.sleep(3)
    b.js("var f=document.getElementById('csFab'); if(f) f.click();")
    time.sleep(0.4)
    # 先问项目，再留资（走前端本地 captureLead 分支）
    b.js("var i=document.getElementById('csInput'); i.value='我家孩子高二在读，有什么留学项目推荐？'; i.dispatchEvent(new Event('input',{bubbles:true})); document.getElementById('csForm').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));")
    time.sleep(7)
    b.js("var i=document.getElementById('csInput'); i.value='我叫王女士，电话13955556666'; i.dispatchEvent(new Event('input',{bubbles:true})); document.getElementById('csForm').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));")
    time.sleep(2)
    txt = b.js("document.getElementById('csBody').innerText")
    print("最后一条:", (txt or "").split("\n")[-4:])
    b.shot("handoff.png")
    b.cmd("Emulation.setDeviceMetricsOverride", {"width":390,"height":844,"deviceScaleFactor":1,"mobile":True})
    time.sleep(0.8)
    print("窄屏溢出:", b.js("document.documentElement.scrollWidth - document.documentElement.clientWidth"))
finally:
    b.close()
