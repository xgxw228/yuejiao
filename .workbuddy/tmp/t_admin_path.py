import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

BASE = 'http://127.0.0.1:8000'
b = Browser()

print('== 1. 门户首页（模拟你退出后 ?logout=1）==')
open_page(b, BASE + '/?logout=1', 1440, 900); time.sleep(1.5)
print('URL:', b.js('location.pathname + location.search'))
print('登录按钮:', b.js("!!document.getElementById('loginBtn') || !!document.querySelector('[id*=login]')"))

print('== 2. 打开登录弹窗，用 admin 登录 ==')
#  triggers
print('弹窗 id 列表:', b.js("Array.from(document.querySelectorAll('[id]')).map(function(n){return n.id}).filter(function(x){return /login|dialog|modal|open/i.test(x)}).join(', ')"))
b.js("(document.getElementById('loginBtn')||document.querySelector('.login-btn, [data-open-login]')||{}).click&&(document.getElementById('loginBtn')||document.querySelector('.login-btn, [data-open-login]')).click()")
time.sleep(0.8)
print('dialog hidden:', b.js("(document.getElementById('dialog')||{}).hidden"))
b.js("document.getElementById('username').value='admin'; document.getElementById('password').value='123456';")
b.js("document.getElementById('form').requestSubmit()")
time.sleep(2.5)
print('登录后 URL:', b.js('location.pathname'), '| token:', (b.js("localStorage.getItem('yj_token')") or '')[:12])

print('== 3. 工作台点「数据后台」==')
print('admin-link hidden:', b.js("(document.getElementById('admin-link')||{}).hidden"))
b.js("document.getElementById('admin-link').click()")
time.sleep(2.5)
print('点击后 URL:', b.js('location.pathname + location.search'))
print('blocked hidden:', b.js("(document.getElementById('blocked')||{}).hidden"))
print('app hidden:', b.js("(document.getElementById('app')||{}).hidden"))
print('body 文本前 200:', (b.js('document.body.innerText') or '')[:200].replace('\n',' | '))
b.shot('path_admin.png')
b.close()
