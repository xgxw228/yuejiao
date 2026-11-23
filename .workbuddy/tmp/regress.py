"""批量回归：把三个 Agent 的每个分支都跑一遍。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run import run_draft, APPS

CASES = [
    ("student", "我明天要请假一天，家里有事"),
    ("student", "我的请假批下来了吗"),
    ("student", "最近压力好大，感觉活不下去了"),
    ("student", "宿舍空调坏了三天没人修，我要投诉"),
    ("student", "我上学期成绩怎么样"),
    ("student", "新加坡本科一年学费大概多少钱"),
    ("employee", "帮我查一下许同学的跟进记录"),
    ("employee", "新增一个客户，叫周雨，电话 13500001111，25 岁本科毕业想读硕士"),
    ("employee", "把许明的状态改成已签约"),
    ("employee", "今天给三个客户打了电话，整理了两份新加坡项目资料"),
    ("employee", "给张三录一门雅思成绩，7.5 分"),
    ("employee", "新员工入职要准备哪些材料"),
    ("customer", "我家孩子19岁、高中刚毕业、想快点拿本科学历"),
    ("customer", "你们有哪些新加坡的项目"),
    ("customer", "最近有什么讲座或分享会"),
    ("customer", "我要报名新加坡留学分享会"),
    ("customer", "你们公司什么时候成立的，做哪些业务"),
]

if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for key, query in CASES:
        if only and key != only:
            continue
        ans, errs, trace = run_draft(APPS[key], query)
        ok = not errs and ans.strip()
        print(f"\n{'='*70}\n[{key}] {query}\n{'─'*70}")
        print(f"轨迹: {' / '.join(t.strip('→✓ ') for t in trace)}")
        print((ans.strip() or "(空回复)")[:600])
        if errs:
            print("!! 错误:", errs[0][:300])
