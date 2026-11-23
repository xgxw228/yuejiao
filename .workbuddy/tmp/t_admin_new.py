import sys, os, json, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

BASE = 'http://127.0.0.1:8000'

def get_token(username, password):
    data = json.dumps({'username': username, 'password': password}).encode()
    req = urllib.request.Request(BASE + '/api/auth/login', data=data,
                                 headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req).read())['data']['token']

b = Browser()
print('== 管理员登录态 ==')
token = get_token('admin', '123456')
open_page(b, BASE + '/admin', 1440, 900)
b.js("localStorage.setItem('yj_token', arguments[0])", token) if False else None
# 用 cdp 注入 token 后刷新
b.js("localStorage.setItem('yj_token', '%s')" % token)
b.js('location.reload()'); time.sleep(2.5)

print('blocked hidden:', b.js("document.getElementById('blocked').hidden"))
print('app hidden:', b.js("document.getElementById('app').hidden"))
print('me:', b.js("document.getElementById('me').textContent"))
print('行动卡:', b.js("""(function(){return ['n-alert','n-leave','n-ticket','k-lead','k-follow','k-chat','k-event']
  .map(function(id){return id+'='+document.getElementById(id).textContent}).join(' | ')})()"""))
print('预警行数:', b.js("document.querySelectorAll('#alerts .alert-row').length"))
print('分布条:', b.js("document.querySelectorAll('#dist .bar').length"),
      '| 讲座条:', b.js("document.querySelectorAll('#events .bar').length"))
b.shot('adm_new_overview.png')

print('== 跳转：点预警卡 ==')
b.js("document.querySelector('[data-goto=\"student_psych_alert\"]').click()"); time.sleep(1.5)
print('表格视图 hidden:', b.js("document.getElementById('view-table').hidden"))
print('标题:', b.js("document.getElementById('title').textContent"))
print('行数:', b.js("document.querySelectorAll('#table-box tbody tr').length"))
b.shot('adm_new_table.png')

print('== 搜索 ==')
b.js("document.getElementById('q').value='活不下去';document.getElementById('search-form').requestSubmit()"); time.sleep(1.2)
print('搜索后行数:', b.js("document.querySelectorAll('#table-box tbody tr').length"),
      '| 计数:', b.js("document.getElementById('count').textContent"))

print('== 分页（切到对话记录 73 行）==')
b.js("""Array.from(document.querySelectorAll('#tables a')).filter(function(a){return a.getAttribute('data-table')==='conversation_log'})[0].click()"""); time.sleep(1.5)
print('标题:', b.js("document.getElementById('title').textContent"),
      '| 分页:', b.js("document.getElementById('page-info').textContent"))
b.js("document.getElementById('next').click()"); time.sleep(1.2)
print('下一页:', b.js("document.getElementById('page-info').textContent"))

print('== 返回概览 ==')
b.js("document.getElementById('nav-dash').click()"); time.sleep(0.5)
print('概览 hidden:', b.js("document.getElementById('view-dash').hidden"),
      '| 表格 hidden:', b.js("document.getElementById('view-table').hidden"))

print('== 手机端 ==')
open_page(b, BASE + '/admin', 430, 900)
b.js("localStorage.setItem('yj_token', '%s')" % token)
b.js('location.reload()'); time.sleep(2.2)
print('溢出:', b.js('document.documentElement.scrollWidth-document.documentElement.clientWidth'))
b.shot('adm_new_430.png')

print('== 非管理员拦截 ==')
token2 = get_token('emp001', '123456')
open_page(b, BASE + '/admin', 1440, 900)
b.js("localStorage.setItem('yj_token', '%s')" % token2)
b.js('location.reload()'); time.sleep(2)
print('blocked hidden:', b.js("document.getElementById('blocked').hidden"),
      '| 提示:', b.js("document.getElementById('blocked-msg').textContent"))
b.close()
