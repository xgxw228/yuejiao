import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

b = Browser()
open_page(b, "http://127.0.0.1:8000/login", 1440, 900)
time.sleep(1)

print("roles:", b.js("document.querySelectorAll('.role-card').length"))
b.js("document.getElementById('roleCards').children[1].click()")
time.sleep(0.4)
print("filled:", b.js("document.getElementById('username').value + '/' + document.getElementById('password').value"))
print("msg:", b.js("document.getElementById('msg').textContent"))
b.shot("i_fill.png")

# 密码显隐
b.js("document.getElementById('eye').click()")
print("pwd type after eye:", b.js("document.getElementById('password').type"))

# 错误密码
b.js("document.getElementById('password').value='wrongpwd'; document.getElementById('form').requestSubmit();")
time.sleep(1.5)
print("err msg:", b.js("document.getElementById('msg').textContent"))
print("btn:", b.js("document.getElementById('submit').textContent"), b.js("document.getElementById('submit').disabled"))
b.shot("i_err.png")

# 空用户名
b.js("document.getElementById('username').value=''; document.getElementById('form').requestSubmit();")
time.sleep(0.4)
print("empty msg:", b.js("document.getElementById('msg').textContent"))

# 正确登录
b.js("document.getElementById('username').value='emp001'; document.getElementById('password').value='123456'; document.getElementById('form').requestSubmit();")
time.sleep(3)
print("after login url:", b.js("location.pathname"))

# 游客按钮
open_page(b, "http://127.0.0.1:8000/login?logout=1", 1440, 900)
time.sleep(1)
b.js("document.getElementById('heroGuest').click()")
time.sleep(3)
print("guest url:", b.js("location.pathname"))

b.close()
