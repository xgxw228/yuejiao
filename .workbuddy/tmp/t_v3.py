import sys, time
sys.path.insert(0, r'D:\项目1\.workbuddy\tmp')
from cdpkit import Browser

b = Browser(1440, 900)
try:
    b.cmd("Page.enable"); b.cmd("Runtime.enable")
    b.cmd("Page.navigate", {"url": "http://127.0.0.1:8000/login?logout=1"})
    time.sleep(2.6)

    print("1) 导航初始 class:", b.js("document.getElementById('nav').className"))
    b.js("window.scrollTo(0, 400)"); time.sleep(0.6)
    print("   滚动后 class:", b.js("document.getElementById('nav').className"))

    # 锚点：点「五类身份」
    b.js("document.querySelector('.nav-links a[href=\"#roles\"]').click()"); time.sleep(1.4)
    print("2) 点导航「五类身份」后 scrollY:", b.js("Math.round(scrollY)"),
          "| 区块顶部:", b.js("Math.round(document.getElementById('roles').getBoundingClientRect().top)"),
          "| 标题未被遮挡:", b.js("document.querySelector('#roles h2').getBoundingClientRect().top > 72"))

    # 表格内容
    print("3) 身份行数:", b.js("document.querySelectorAll('.role-row').length"),
          "| 第二行可以做什么:", b.js("document.querySelectorAll('.role-row')[1].querySelector('.rr-can').textContent.slice(0,12)"))

    # 角色卡
    b.js("document.getElementById('login').scrollIntoView()"); time.sleep(1.0)
    print("4) 角色卡数量:", b.js("document.querySelectorAll('.role-card').length"))
    b.js("document.querySelector('.role-card[data-role=\"teacher\"]').click()"); time.sleep(0.5)
    print("   填入:", b.js("document.getElementById('username').value + ' / ' + document.getElementById('password').value"),
          "| 提示:", b.js("document.getElementById('msg').textContent.slice(0,20)"))

    # 密码显隐
    b.js("document.getElementById('eye').click()")
    print("5) 眼睛切换后 type:", b.js("document.getElementById('password').type"))
    b.js("document.getElementById('eye').click()")

    # 空用户名
    b.js("document.getElementById('username').value=''; document.getElementById('form').requestSubmit()")
    time.sleep(0.5)
    print("6) 空用户名提示:", b.js("document.getElementById('msg').textContent"))

    # 正常登录（点角色卡后提交）
    b.js("document.querySelector('.role-card[data-role=\"staff\"]').click()"); time.sleep(0.4)
    b.js("document.getElementById('form').requestSubmit()"); time.sleep(3.2)
    print("7) 登录后 URL:", b.js("location.pathname"), "| token:", b.js("!!localStorage.getItem('yj_token')"))
finally:
    b.close()

# 游客入口：清掉 token 后点首屏按钮
b = Browser(1440, 900)
try:
    b.cmd("Page.enable"); b.cmd("Runtime.enable")
    b.cmd("Page.navigate", {"url": "http://127.0.0.1:8000/login?logout=1"})
    time.sleep(2.6)
    b.js("document.getElementById('heroGuest').click()")
    time.sleep(3.2)
    print("8) 首屏游客按钮后 URL:", b.js("location.pathname"), "| token:", b.js("!!localStorage.getItem('yj_token')"))
finally:
    b.close()
