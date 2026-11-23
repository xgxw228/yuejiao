import sys, time
sys.path.insert(0, r'D:\项目1\.workbuddy\tmp')
from cdpkit import Browser, open_page

b = Browser(500, 900)
try:
    b.cmd("Page.enable"); b.cmd("Runtime.enable")
    b.cmd("Page.navigate", {"url": "http://127.0.0.1:8000/login?logout=1"})
    time.sleep(3)
    print("url:", b.js("location.href"))
    print("csFab:", b.js("!!document.getElementById('csFab')"))
    b.js("var f=document.getElementById('csFab'); if(f) f.click();")
    time.sleep(0.5)
    b.js("var i=document.getElementById('csInput'); i.value='我家孩子今年高中毕业,有什么留学项目推荐吗?'; i.dispatchEvent(new Event('input',{bubbles:true})); document.getElementById('csForm').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));")
    prev=0
    for t in [1,3,6,10,16,25]:
        time.sleep(t-prev); prev=t
        txt = b.js("document.getElementById('csBody').innerText")
        print("t=%ds" % t, (txt or "")[-330:].replace("\n"," / "))
    b.shot("chat_probe.png")
finally:
    b.close()
