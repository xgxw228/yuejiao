import sys, os, json, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

BASE = 'http://127.0.0.1:8000'


def get_token(u, p='123456'):
    d = json.dumps({'username': u, 'password': p}).encode()
    req = urllib.request.Request(BASE + '/api/auth/login', data=d,
                                 headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req).read())['data']['token']


b = Browser()

print('== 登录页账号矩阵 ==')
open_page(b, BASE + '/login', 1440, 900)
time.sleep(1.5)
txt = b.js("document.body.innerText")
for line in txt.split('\n'):
    if '班' in line:
        print('  ', line.strip())
b.shot('cn_login.png')

print('== 顾问：账户管理 / 班级区块 ==')
t = get_token('emp006')
open_page(b, BASE + '/demo/index.html', 1440, 900)
b.js("localStorage.setItem('yj_token', '%s')" % t)
b.js('location.reload()'); time.sleep(2.5)
b.js("""Array.from(document.querySelectorAll('[data-key]')).filter(function(e){return e.getAttribute('data-key')==='accounts'})[0].click()""")
time.sleep(1.8)
body = b.js("document.getElementById('panelBody').innerText")
print('\n'.join(['  ' + l for l in body.split('\n') if '班' in l][:12]))
b.shot('cn_staff_classes.png')

print('== 学员：我的班级 ==')
t2 = get_token('stu001')
open_page(b, BASE + '/demo/index.html', 1440, 900)
b.js("localStorage.setItem('yj_token', '%s')" % t2)
b.js('location.reload()'); time.sleep(2.5)
b.js("""Array.from(document.querySelectorAll('[data-key]')).filter(function(e){return e.getAttribute('data-key')==='myclass'})[0].click()""")
time.sleep(1.5)
print(b.js("document.getElementById('panelBody').innerText").strip().replace('\n', ' / '))
b.shot('cn_student_class.png')
b.close()
