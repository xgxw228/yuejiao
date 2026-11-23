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
token = get_token('admin', '123456')
open_page(b, BASE + '/admin', 1440, 900)
b.js("localStorage.setItem('yj_token', '%s')" % token)
b.js('location.reload()'); time.sleep(2.5)

print('概览可见:', b.js("!document.getElementById('view-dash').hidden"))
print('成绩柱:', b.js("document.querySelectorAll('#score-bars .bar').length"))
b.shot('nm_overview.png')


def open_tbl(name):
    b.js("""Array.from(document.querySelectorAll('#tables a')).filter(function(a){return a.getAttribute('data-table')===arguments[0]})[0].click()""".replace('arguments[0]', "'%s'" % name))
    time.sleep(1.4)
    head = b.js("Array.from(document.querySelectorAll('#table-box thead th')).map(function(t){return t.textContent}).join(' | ')")
    first = b.js("Array.from(document.querySelectorAll('#table-box tbody tr')).slice(0,3).map(function(tr){return Array.from(tr.children).map(function(td){return td.textContent}).join(' / ')}).join('\\n')")
    print('==', name)
    print('表头:', head)
    print('前3行:\n' + first)
    b.shot('nm_%s.png' % name)


open_tbl('student_score')
open_tbl('student_admin_service')
open_tbl('sys_user')

print('== 搜索学生姓名 ==')
b.js("document.getElementById('q').value='吴天';document.getElementById('search-form').requestSubmit()"); time.sleep(1.2)
print('计数:', b.js("document.getElementById('count').textContent"))
print('行数:', b.js("document.querySelectorAll('#table-box tbody tr').length"))
b.shot('nm_search_user.png')

print('== 手机端成绩表 ==')
open_page(b, BASE + '/admin', 390, 844)
b.js("localStorage.setItem('yj_token', '%s')" % token)
b.js('location.reload()'); time.sleep(2.2)
b.js("""Array.from(document.querySelectorAll('#tables a')).filter(function(a){return a.getAttribute('data-table')==='student_admin_service'})[0].click()""")
time.sleep(1.2)
print('手机溢出:', b.js('document.documentElement.scrollWidth-document.documentElement.clientWidth'))
b.shot('nm_mobile_leave.png')
b.close()
