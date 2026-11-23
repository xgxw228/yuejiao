"""登录 + 角色裁剪的端到端验收：登录页截图、各角色进入后的 Agent 数量与身份锁定。"""

import sys, os, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

BASE = os.environ.get("DEMO_BASE", "http://127.0.0.1:8000")


def login(b, role, shot=None):
    open_page(b, BASE + "/?logout=1")
    b.js("localStorage.clear(); location.reload();", 2.5)
    b.js(f"document.querySelector('[data-role=\"{role}\"]').click();", 0.5)
    filled = b.js("document.getElementById('username').value + ' / ' + document.getElementById('password').value")
    b.js("document.getElementById('form').requestSubmit();", 0.2)
    time.sleep(4)
    info = b.js("""JSON.stringify({
      url: location.pathname,
      me: document.getElementById('me-name').textContent + ' / ' + document.getElementById('me-role').textContent,
      agents: Array.from(document.querySelectorAll('.agent .agent-name')).map(e => e.textContent),
      selectHidden: document.getElementById('user-select').hidden,
      selectOptions: Array.from(document.getElementById('user-select').options).map(o => o.textContent),
      approveHidden: document.getElementById('approve-btn').hidden
    })""")
    if shot:
        b.shot(shot)
    return filled, info


b = Browser(width=1440, height=900)
open_page(b, BASE + "/?logout=1")
b.js("localStorage.clear(); location.reload();", 2.5)
b.shot("login_page.png")
print("登录页角色卡:", b.js("Array.from(document.querySelectorAll('.role-card .role-name')).map(e=>e.textContent).join(' | ')"))

for role, shot in [("teacher", "role_teacher.png"),
                   ("student", "role_student.png"),
                   ("admin", "role_admin.png"),
                   ("parent", "role_parent.png"),
                   ("staff", "role_staff.png")]:
    filled, info = login(b, role, shot)
    print(f"[{role}] 填入={filled} -> {info}")

# 班主任：点开审批抽屉看一眼
login(b, "teacher")
b.js("document.getElementById('approve-btn').click();", 2.0)
b.shot("login_approve_drawer.png")
print("抽屉:", b.js("document.getElementById('drawer-sub').textContent"))

b.close()
