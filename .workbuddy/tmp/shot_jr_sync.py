import sys, json, time, urllib.request
sys.path.insert(0, r'D:\项目1\.workbuddy\tmp')
from cdpkit import Browser
B="http://127.0.0.1:8000"
req=urllib.request.Request(B+"/api/auth/login",data=json.dumps({"username":"stu005","password":"123456"}).encode(),headers={"Content-Type":"application/json"},method="POST")
d=json.loads(urllib.request.urlopen(req).read())["data"]
b=Browser(1000,900)
try:
    b.cmd("Page.enable"); b.cmd("Runtime.enable")
    b.cmd("Page.navigate",{"url":B+"/"}); time.sleep(2)
    b.js("localStorage.setItem('yj_token', %s); localStorage.setItem('yj_user', %s);"%(json.dumps(d["token"]),json.dumps(json.dumps(d["user"],ensure_ascii=False))))
    b.cmd("Page.navigate",{"url":B+"/demo/"}); time.sleep(3)
    b.js("var n=document.querySelector('[data-key=\"journal\"]'); if(n) n.click();")
    time.sleep(2)
    b.shot("jr_sync_student.png")
    txt=b.js("document.getElementById('panel-body').innerText")
    print("学生端心理关怀:\n",(txt or "")[:650])
    b.cmd("Emulation.setDeviceMetricsOverride",{"width":390,"height":844,"deviceScaleFactor":1,"mobile":True}); time.sleep(1)
    print("窄屏溢出:",b.js("document.documentElement.scrollWidth - document.documentElement.clientWidth"))
finally:
    b.close()
