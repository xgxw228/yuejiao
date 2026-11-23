"""端到端验收：学生提交请假 → 班主任在面板审批 → 学生查询看到审批人与意见。"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdpkit import Browser, open_page

BASE = os.environ.get("DEMO_BASE", "http://127.0.0.1:8000")

b = Browser()
open_page(b, BASE + "/demo/")

# 1. 学生张三提交一条跨月请假
b.js("document.querySelectorAll('.agent')[0].click();", 0.6)
b.js("""
  (function(){
    var t=document.getElementById('input');
    t.value='12月26号到28号要请假，回家参加姐姐的婚礼';
    document.getElementById('send').click();
  })();
""")
time.sleep(15)
b.shot("approve_1_apply.png")
print("① 学生提交:", b.js("document.querySelector('.msg.bot:last-of-type .bubble').innerText"))

# 2. 切到李老师，打开审批面板
b.js("document.querySelectorAll('.agent')[1].click();", 0.8)
b.js("""(function(){var s=document.getElementById('user-select');s.value='3';s.dispatchEvent(new Event('change'));})();""", 1.0)
b.js("document.getElementById('approve-btn').click();", 1.8)
b.shot("approve_2_panel.png")

# 3. 填意见并通过第一条（张三那条应排在最前面？按开始时间排序，体检 11-25 更早，所以取 name 含张三的卡片）
b.js("""
  (function(){
    var cards=document.querySelectorAll('.lv-card');
    for (var i=0;i<cards.length;i++){
      if (cards[i].innerText.indexOf('张三')===0 || cards[i].querySelector('.lv-name').innerText.indexOf('张三')>=0){
        cards[i].querySelector('.lv-comment').value='婚礼属家事，准假 3 天，返校后补交行程单。';
        cards[i].querySelector('button[data-act=ok]').click();
        return 'clicked';
      }
    }
    return 'not found';
  })();
""")
time.sleep(2.4)
b.shot("approve_3_done.png")
print("② 审批提示:", b.js("document.getElementById('toast').innerText"))
print("   面板待审批:", b.js("document.querySelector('.dr-stat b').innerText"))

# 4. 切回张三查询状态
b.js("document.getElementById('drawer-close').click();", 0.4)
b.js("document.querySelectorAll('.agent')[0].click();", 0.8)
b.js("""
  (function(){
    var t=document.getElementById('input');
    t.value='我的请假批了吗';
    document.getElementById('send').click();
  })();
""")
time.sleep(13)
b.shot("approve_4_query.png")
print("③ 学生查询:", b.js("document.querySelector('.msg.bot:last-of-type .bubble').innerText"))

b.close()
