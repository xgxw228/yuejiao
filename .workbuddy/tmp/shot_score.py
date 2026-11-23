import sys, json, time, urllib.request
sys.path.insert(0, r'D:\项目1\.workbuddy\tmp')
from cdpkit import Browser
B="http://127.0.0.1:8000"
def login(u):
    req=urllib.request.Request(B+"/api/auth/login",data=json.dumps({"username":u,"password":"123456"}).encode(),headers={"Content-Type":"application/json"},method="POST")
    return json.loads(urllib.request.urlopen(req).read())["data"]
b=Browser(1100,900)
try:
    b.cmd("Page.enable"); b.cmd("Runtime.enable")
    for who,key,name in [("emp003","students","score_teacher"),("stu006","grades","score_student")]:
        d=login(who)
        b.cmd("Page.navigate",{"url":B+"/"}); time.sleep(1.5)
        b.js("localStorage.setItem('yj_token', %s); localStorage.setItem('yj_user', %s);"%(json.dumps(d["token"]),json.dumps(json.dumps(d["user"],ensure_ascii=False))))
        b.cmd("Page.navigate",{"url":B+"/demo/"}); time.sleep(3)
        b.js("var n=document.querySelector('[data-key=\"%s\"]'); if(n) n.click();"%key)
        time.sleep(1.5)
        b.shot(name+".png")
        txt=b.js("document.getElementById('panel-body').innerText")
        print(who,(txt or "")[:420].replace("\n"," / "))
        b.cmd("Emulation.setDeviceMetricsOverride",{"width":390,"height":844,"deviceScaleFactor":1,"mobile":True}); time.sleep(0.8)
        print("  窄屏溢出:",b.js("document.documentElement.scrollWidth - document.documentElement.clientWidth"))
        b.cmd("Emulation.setDeviceMetricsOverride",{"width":1100,"height":900,"deviceScaleFactor":1,"mobile":False})
finally:
    b.close()
