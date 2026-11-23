import sys, json, time, urllib.request
sys.path.insert(0, r'D:\项目1\.workbuddy\tmp')
from cdpkit import Browser, open_page

B = "http://127.0.0.1:8000"

def login(u):
    req = urllib.request.Request(B+"/api/auth/login",
        data=json.dumps({"username":u,"password":"123456"}).encode(),
        headers={"Content-Type":"application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())["data"]

b = Browser(1440, 980)
try:
    open_page(b, B+"/")
    for who, who_name, name in [("stu001","张三","jr_student"), ("emp001","李老师","jr_teacher")]:
        d = login(who)
        b.js("localStorage.setItem('yj_token', %s); localStorage.setItem('yj_user', %s);" %
             (json.dumps(d["token"]), json.dumps(json.dumps(d["user"], ensure_ascii=False))))
        b.cmd("Page.navigate", {"url": B+"/demo/"})
        time.sleep(3)
        print(who_name, "入口:", b.js("!!document.querySelector('[data-key=\"journal\"]')"))
        b.js("var n=document.querySelector('[data-key=\"journal\"]'); if(n) n.click();")
        time.sleep(2)
        b.shot(name+".png")
        txt = b.js("document.getElementById('panel-body').innerText")
        print(who_name, "面板:", (txt or "")[:620].replace("\n"," / "))
        b.cmd("Emulation.setDeviceMetricsOverride", {"width":390,"height":844,"deviceScaleFactor":1,"mobile":True})
        time.sleep(1)
        b.shot(name+"_390.png")
        print(who_name, "窄屏溢出:", b.js("document.documentElement.scrollWidth - document.documentElement.clientWidth"))
        b.cmd("Emulation.setDeviceMetricsOverride", {"width":1440,"height":980,"deviceScaleFactor":1,"mobile":False})
finally:
    b.close()
