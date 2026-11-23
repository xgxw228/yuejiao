import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

URL = "http://127.0.0.1:8000/"
b = Browser()
open_page(b, URL, 1440, 900)
time.sleep(2.5)
b.shot("p_1440.png")

print("== video state ==")
print(b.js("""(function(){return Array.from(document.querySelectorAll('video')).map(function(v,i){
  return i+':'+Math.round(v.currentTime*10)/10+'/'+Math.round(v.duration*10)/10+':'+v.readyState+':'+v.paused;}).join(' | ')})()"""))
print("active slide:", b.js("Array.from(document.querySelectorAll('.slide')).findIndex(function(s){return s.classList.contains('on')})"))
print("count:", b.js("document.getElementById('count').textContent"))

# 等一个轮播周期
time.sleep(4.0)
print("after 4s active:", b.js("Array.from(document.querySelectorAll('.slide')).findIndex(function(s){return s.classList.contains('on')})"))
print("after 4s count:", b.js("document.getElementById('count').textContent"))

# 手动下一个
b.js("document.getElementById('next').click()")
time.sleep(1.0)
print("after next:", b.js("document.getElementById('count').textContent"))

# 暂停
b.js("document.getElementById('toggle').click()")
time.sleep(0.5)
print("paused:", b.js("Array.from(document.querySelectorAll('video')).every(function(v){return v.paused})"))
b.js("document.getElementById('toggle').click()")
time.sleep(0.5)

print("== modal ==")
b.js("document.getElementById('openLogin').click()")
time.sleep(0.7)
print("modal open:", b.js("document.getElementById('modal').classList.contains('open')"))
print("roles:", b.js("document.querySelectorAll('.role-card').length"))
b.shot("p_modal.png")

# 点遮罩关闭
b.js("document.getElementById('modal').dispatchEvent(new MouseEvent('mousedown',{bubbles:true}))")
time.sleep(0.5)
print("closed by backdrop:", b.js("!document.getElementById('modal').classList.contains('open')"))

# 打开 -> 角色填充 -> 错误密码 -> 正确登录
b.js("document.getElementById('openLogin').click()")
time.sleep(0.5)
b.js("document.getElementById('roleCards').children[0].click()")
time.sleep(0.3)
print("fill:", b.js("document.getElementById('username').value"))
b.js("document.getElementById('password').value='wrong';document.getElementById('form').requestSubmit();")
time.sleep(1.3)
print("bad pwd:", b.js("document.getElementById('msg').textContent"))
b.js("document.getElementById('username').value='emp001';document.getElementById('password').value='123456';document.getElementById('form').requestSubmit();")
time.sleep(3)
print("login ->", b.js("location.pathname"))

# 游客
open_page(b, URL + "?t=1", 1440, 900)
time.sleep(1.5)
b.js("document.getElementById('openLogin').click()")
time.sleep(0.5)
b.js("document.getElementById('guest').click()")
time.sleep(3)
print("guest ->", b.js("location.pathname"))

# 多分辨率
for w, h, name in [(1366, 768, "p_1366"), (1080, 608, "p_1080"), (430, 932, "p_430")]:
    open_page(b, URL + "?r=" + name, w, h)
    time.sleep(2)
    b.shot(name + ".png")
    print(name, b.js("""(function(){var d=document.documentElement;return {
      sw:d.scrollWidth,cw:d.clientWidth,sh:d.scrollHeight,
      h1:Math.round(document.querySelector('h1').getBoundingClientRect().top),
      ctrls:Math.round(document.querySelector('.controls').getBoundingClientRect().bottom)};})()"""))

b.close()
