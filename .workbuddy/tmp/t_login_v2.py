import sys, time
sys.path.insert(0, r'D:\项目1\.workbuddy\tmp')
from cdpkit import Browser

b = Browser(1440, 900)
try:
    b.cmd("Page.enable"); b.cmd("Runtime.enable")
    b.cmd("Page.navigate", {"url": "http://127.0.0.1:8000/login?logout=1"})
    time.sleep(2.5)

    print("角色卡数量:", b.js("document.querySelectorAll('.role-card').length"))

    # 1) 点班主任卡
    b.js("document.querySelector('.role-card[data-role=\"teacher\"]').click()")
    time.sleep(0.4)
    print("填入后:", b.js("document.getElementById('username').value + ' / ' + document.getElementById('password').value"))
    print("选中态:", b.js("document.querySelector('.role-card.on').dataset.role"))

    # 2) 密码显隐
    b.js("document.getElementById('eye').click()")
    print("点眼睛后 type:", b.js("document.getElementById('password').type"))
    b.js("document.getElementById('eye').click()")

    # 3) 空用户名提交
    b.js("document.getElementById('username').value=''; document.getElementById('username').dispatchEvent(new Event('input'));")
    b.js("document.getElementById('form').requestSubmit()")
    time.sleep(0.5)
    print("空用户名提示:", b.js("document.getElementById('msg').textContent"))
    print("错误态样式:", b.js("document.getElementById('user-wrap').classList.contains('err')"))

    # 4) 错误密码
    b.js("document.getElementById('username').value='teacher001';")
    b.js("document.getElementById('password').value='wrong';")
    b.js("document.getElementById('form').requestSubmit()")
    time.sleep(1.8)
    print("错误密码提示:", b.js("document.getElementById('msg').textContent"))

    # 5) 正确登录 → 应跳转
    b.js("document.getElementById('password').value='123456';")
    b.js("document.getElementById('form').requestSubmit()")
    time.sleep(3.0)
    print("登录后 URL:", b.js("location.pathname"))
    print("token 已写入:", b.js("!!localStorage.getItem('yj_token')"))
finally:
    b.close()
