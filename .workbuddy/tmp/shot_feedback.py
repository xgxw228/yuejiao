import sys, json, time, urllib.request
sys.path.insert(0, r'D:\项目1\.workbuddy\tmp')
from cdpkit import Browser, open_page

B = "http://127.0.0.1:8000"

def login(u):
    req = urllib.request.Request(B+"/api/auth/login",
        data=json.dumps({"username":u,"password":"123456"}).encode(),
        headers={"Content-Type":"application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read())["data"]
    return d["token"], d["user"]

b = Browser(1440, 980)
try:
    open_page(b, B+"/")
    for who, nav, name in [("stu001","feedback","fb_student"),
                           ("emp001","feedback","fb_teacher")]:
        tok, user = login(who)
        b.js("localStorage.setItem('yj_token', %s); localStorage.setItem('yj_user', %s);" %
             (json.dumps(tok), json.dumps(json.dumps(user, ensure_ascii=False))))
        b.cmd("Page.navigate", {"url": B+"/demo/"})
        time.sleep(3)
        # 面板入口
        found = b.js("!!document.querySelector('[data-key=\"%s\"]')" % nav)
        print(who, "入口存在:", found)
        b.js("var n=document.querySelector('[data-key=\"%s\"]'); if(n) n.click();" % nav)
        time.sleep(2)
        b.shot(name+".png")
        txt = b.js("document.getElementById('panel-body').innerText")
        print(who, "面板文本:", (txt or "")[:700].replace("\n", " / "))
        # 窄屏
        b.cmd("Emulation.setDeviceMetricsOverride", {"width":390,"height":844,"deviceScaleFactor":1,"mobile":True})
        time.sleep(1)
        b.shot(name+"_390.png")
        print(who, "窄屏溢出:", b.js("document.documentElement.scrollWidth - document.documentElement.clientWidth"))
        b.cmd("Emulation.setDeviceMetricsOverride", {"width":1440,"height":980,"deviceScaleFactor":1,"mobile":False})
    errs = b.js("window.__errs || []")
    print("JS errors:", errs)
finally:
    b.close()
