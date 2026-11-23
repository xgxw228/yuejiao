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
b.js("localStorage.setItem('yj_token', '%s')" % token)
b.js('location.reload()'); time.sleep(2.8)

print('blocked/app hidden:', b.js("document.getElementById('blocked').hidden"), b.js("document.getElementById('app').hidden"))
print('me:', b.js("document.getElementById('me').textContent"))
print('KPI:', b.js("""(function(){return ['k-lead','k-follow','k-chat','n-alert','n-leave','n-ticket']
  .map(function(id){return id+'='+document.getElementById(id).textContent}).join(' | ')})()"""))
print('核心分析:', b.js("""(function(){return {
  distSvg:document.querySelectorAll('#dist-donut svg').length,
  distLg:document.querySelectorAll('#dist-legend .lg').length,
  scoreBars:document.querySelectorAll('#score-bars .bar').length,
  agentSvg:document.querySelectorAll('#agent-donut svg').length,
  agentLg:document.querySelectorAll('#agent-legend .lg').length,
  distTotal:document.getElementById('dist-total').textContent,
  agentTotal:document.getElementById('agent-total').textContent};})()"""))
print('预警行:', b.js("document.querySelectorAll('#alerts .alert-row').length"),
      '| 讲座条:', b.js("document.querySelectorAll('#events .bar').length"),
      '| 横向溢出:', b.js('document.documentElement.scrollWidth-document.documentElement.clientWidth'))
b.shot('l_admin_1440.png')

print('== 下钻：点预警卡 ==')
b.js("document.querySelector('[data-goto=\"student_psych_alert\"]').click()"); time.sleep(1.5)
print('表格 hidden:', b.js("document.getElementById('view-table').hidden"),
      '| 标题:', b.js("document.getElementById('title').textContent"),
      '| 行:', b.js("document.querySelectorAll('#table-box tbody tr').length"))
b.shot('l_admin_table.png')

print('== 搜索 ==')
b.js("document.getElementById('q').value='活不下去';document.getElementById('search-form').requestSubmit()"); time.sleep(1.2)
print('搜索行:', b.js("document.querySelectorAll('#table-box tbody tr').length"),
      '|', b.js("document.getElementById('count').textContent"))

print('== 分页 ==')
b.js("""Array.from(document.querySelectorAll('#tables a')).filter(function(a){return a.getAttribute('data-table')==='conversation_log'})[0].click()"""); time.sleep(1.5)
print('标题:', b.js("document.getElementById('title').textContent"),
      '|', b.js("document.getElementById('page-info').textContent"))
b.js("document.getElementById('next').click()"); time.sleep(1.2)
print('下一页:', b.js("document.getElementById('page-info').textContent"))

print('== 返回概览 ==')
b.js("document.getElementById('nav-dash').click()"); time.sleep(0.5)
print('概览/表格 hidden:', b.js("document.getElementById('view-dash').hidden"), b.js("document.getElementById('view-table').hidden"))

print('== 多分辨率 ==')
for w, h, name in [(1280, 800, 'l_admin_1280'), (430, 900, 'l_admin_430')]:
    open_page(b, BASE + '/admin', w, h)
    b.js("localStorage.setItem('yj_token', '%s')" % token)
    b.js('location.reload()'); time.sleep(2.4)
    print(name, '溢出:', b.js('document.documentElement.scrollWidth-document.documentElement.clientWidth'),
          '| 图表 svg:', b.js('document.querySelectorAll("#view-dash svg").length'))
    b.shot(name + '.png')

print('== 非管理员拦截 ==')
token2 = get_token('emp001', '123456')
open_page(b, BASE + '/admin', 1440, 900)
b.js("localStorage.setItem('yj_token', '%s')" % token2)
b.js('location.reload()'); time.sleep(2)
print('blocked hidden:', b.js("document.getElementById('blocked').hidden"),
      '|', b.js("document.getElementById('blocked-msg').textContent"))

print('== 退出 ==')
open_page(b, BASE + '/admin', 1440, 900)
b.js("localStorage.setItem('yj_token', '%s')" % token)
b.js('location.reload()'); time.sleep(1.8)
b.js("document.getElementById('logout').click()"); time.sleep(1.5)
print('退出后 token:', b.js("localStorage.getItem('yj_token')"), '| URL:', b.js('location.pathname'))
b.close()
