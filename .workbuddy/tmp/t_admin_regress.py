import sys, os, json, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

BASE = 'http://127.0.0.1:8000'


def get_token(u, p):
    data = json.dumps({'username': u, 'password': p}).encode()
    req = urllib.request.Request(BASE + '/api/auth/login', data=data,
                                 headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req).read())['data']['token']


b = Browser()
token = get_token('admin', '123456')
open_page(b, BASE + '/admin', 1440, 900)
b.js("window.__errs=[];window.addEventListener('error',function(e){window.__errs.push(String(e.message))})")
b.js("localStorage.setItem('yj_token', '%s')" % token)
b.js('location.reload()'); time.sleep(2.5)
print('概览 KPI:', b.js("""['k-lead','k-follow','n-alert','n-leave','n-ticket','k-chat']
  .map(function(i){return i+'='+document.getElementById(i).textContent}).join(' | ')"""))
print('预警条数:', b.js("document.querySelectorAll('#alerts .alert-row').length"),
      '| 成绩柱:', b.js("document.querySelectorAll('#score-bars .bar').length"),
      '| 讲座条:', b.js("document.querySelectorAll('#events .bar').length"))

print('== 线索跟进 ==')
b.js("document.getElementById('nav-leads').click()"); time.sleep(1.5)
print('线索卡数:', b.js("document.querySelectorAll('#lead-box .lead, #leads .lead').length"))
print('卡内可写控件:', b.js("document.querySelectorAll('#lead-box select, #lead-box input, #lead-box textarea').length"))
print('顾问列出现:', b.js("document.body.innerText.indexOf('何顾问')>=0"))
b.shot('rg_leads.png')

print('== 操作日志 ==')
b.js("document.getElementById('nav-logs').click()"); time.sleep(1.5)
print('日志行:', b.js("document.querySelectorAll('#log-box .log-row').length"))

print('== 逐表表头 ==')
for t in ['student_feedback_ticket', 'student_psych_alert', 'employee_daily_report', 'conversation_log', 'student_psych_profile']:
    b.js("""Array.from(document.querySelectorAll('#tables a')).filter(function(a){return a.getAttribute('data-table')===arguments[0]})[0].click()""".replace('arguments[0]', "'%s'" % t))
    time.sleep(1.2)
    print(t, '->', b.js("Array.from(document.querySelectorAll('#table-box thead th')).map(function(t){return t.textContent}).join(' | ')"),
          '| 行:', b.js("document.querySelectorAll('#table-box tbody tr').length"))

print('== 用户表 手机端 ==')
open_page(b, BASE + '/admin', 430, 900)
b.js("localStorage.setItem('yj_token', '%s')" % token)
b.js('location.reload()'); time.sleep(2.2)
b.js("""Array.from(document.querySelectorAll('#tables a')).filter(function(a){return a.getAttribute('data-table')==='sys_user'})[0].click()""")
time.sleep(1.3)
print('页面横向溢出:', b.js('document.documentElement.scrollWidth-document.documentElement.clientWidth'),
      '| 表格容器可横向滚动:', b.js("(function(){var t=document.querySelector('.tb');return t.scrollWidth>t.clientWidth})()"))
b.shot('rg_user_430.png')

print('== 老师端 / 学员端不漏 ==')
t2 = get_token('emp001', '123456')
open_page(b, BASE + '/demo/login', 1280, 800)
time.sleep(0.5)
open_page(b, BASE + '/demo/index.html', 1280, 800)
b.js("localStorage.setItem('yj_token', '%s')" % t2)
b.js('location.reload()'); time.sleep(2.5)
print('老师 headline:', b.js("(document.querySelector('.ws-headline')||{}).textContent || document.body.innerText.slice(0,80)"))
b.shot('rg_teacher.png')
b.close()
