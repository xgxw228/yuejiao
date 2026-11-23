import sys, os, json, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

BASE = 'http://127.0.0.1:8000'


def get_token(u, p='123456'):
    d = json.dumps({'username': u, 'password': p}).encode()
    req = urllib.request.Request(BASE + '/api/auth/login', data=d,
                                 headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req).read())['data']['token']


def enter(token, key=None, width=1440, height=900):
    open_page(b, BASE + '/demo/index.html', width, height)
    b.js("localStorage.setItem('yj_token','%s')" % token)
    b.js("location.href='/demo/index.html'")
    time.sleep(3)
    if key:
        for _ in range(15):
            if b.js("!!document.querySelector('[data-key=\"%s\"]')" % key):
                break
            time.sleep(0.5)
        b.js("document.querySelector('[data-key=\"%s\"]').click()" % key)
        time.sleep(1.8)


b = Browser()

print('== 张老师工作台 ==')
enter(get_token('emp009'))
print('headline:', b.js("(document.querySelector('.ws-headline')||document.querySelector('.headline')||{}).textContent"))
print('左栏:', b.js("Array.from(document.querySelectorAll('.nav')).map(function(n){return n.innerText.replace(/\\n/g,' ')}).join(' | ')"))
print('卡片:', b.js("Array.from(document.querySelectorAll('.ws-card')).map(function(c){return c.innerText.replace(/\\n/g,' ')}).join(' || ')"))
b.shot('tr_ws.png')

print('== 试听学员面板 ==')
enter(get_token('emp009'), 'trial')
body = b.js("document.getElementById('panel-body').innerText") or ""
print('标题/副标题:', b.js("document.getElementById('panel-title').textContent"), '|',
      b.js("document.getElementById('panel-sub').textContent"))
print('\n'.join(['  ' + x for x in body.split('\n')[:14]]))
b.shot('tr_trial_panel.png')

print('== 顾问：活动表单 ==')
ts = get_token('emp006')
enter(ts, 'activities')


def pick(title):
    b.js("""(function(){var f=document.querySelector('form.act-form');var s=f.querySelector('select[name="title"]');s.value='%s';s.dispatchEvent(new Event('change',{bubbles:true}));return true})()""" % title)
    time.sleep(0.5)
    return b.js("(function(){var f=document.querySelector('form.act-form');return [f.querySelector('select[name=\"speaker\"]').value, f.querySelector('[name=\"category\"]').value, f.querySelector('[name=\"capacity\"]').value].join(' | ')})()")


for t in ['德国双元制试听课（小班）', '德国双元制项目说明会', '新加坡本科申请分享会', '香港升学规划沙龙']:
    print(' ', t, '->', pick(t))
# 手动改主讲后再换主题：不应该被自动覆盖
b.js("""(function(){var f=document.querySelector('form.act-form');var s=f.querySelector('select[name="speaker"]');s.value='赵老师';s.dispatchEvent(new Event('change',{bubbles:true}));return 1})()""")
print('  手改赵老师后切「新加坡本科申请分享会」->', pick('新加坡本科申请分享会'), '(应保持赵老师)')
b.shot('tr_act_form.png')

print('== 顾问：班级区块 ==')
enter(ts, 'accounts')
print(b.js("Array.from(document.querySelectorAll('.cls-row')).map(function(r){return r.innerText.replace(/\\n/g,' ')}).join('\\n')"))
print('开户班级选项:', b.js("Array.from(document.querySelectorAll('select[name=\"class_id\"] option')).map(function(o){return o.textContent}).join(' / ')"))
b.shot('tr_staff_classes.png')

print('== 登录页 ==')
open_page(b, BASE + '/login', 1440, 900)
b.js("localStorage.clear()")
open_page(b, BASE + '/login', 1440, 900)
time.sleep(2)
print('角色分组:', b.js("Array.from(document.querySelectorAll('.role-group')).map(function(g){return g.textContent}).join(' | ')"))
b.shot('tr_login.png')
b.close()
