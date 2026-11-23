"""验证登录页改版后的交互：角色卡填入、游客入口跳转。"""
import sys
import time

sys.path.insert(0, r"D:\项目1\.workbuddy\tmp")
from cdpkit import Browser, open_page

b = Browser(1440, 900)
try:
    open_page(b, "http://127.0.0.1:8000/login?logout=1")
    time.sleep(2)

    print("角色卡数量:", b.js("document.querySelectorAll('#roles .role-card').length"))
    print("通栏卡:", b.js("Array.from(document.querySelectorAll('#roles .role-card')).filter(c=>c.classList.contains('wide')).map(c=>c.dataset.role).join(',')"))

    b.js("document.querySelector('[data-role=\"teacher\"]').click()")
    time.sleep(0.3)
    print("点班主任后 用户名=", b.js("document.getElementById('username').value"),
          "| 密码=", b.js("document.getElementById('password').value"),
          "| 提示=", b.js("document.getElementById('msg').textContent"))

    b.js("document.getElementById('username').value=''")
    b.js("document.getElementById('password').value=''")
    b.js("document.getElementById('guest').click()")
    time.sleep(3.5)
    print("游客跳转后 URL:", b.js("location.pathname"))
    print("token 已写入:", bool(b.js("localStorage.getItem('yj_token')")))
    b.shot("login_guest_ok.png")
finally:
    b.close()
