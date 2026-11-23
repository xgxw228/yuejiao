# -*- coding: utf-8 -*-
"""三套新色调：墨绿 / 暖砂橙 / 靛蓝。图表结构与 H-K 完全一致，只换色调。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build3 import LEADS, SCORE, AGENT, ALERTS, EVENTS, donut, legend, bars_h, page, OUT

# 线索 4 类颜色由浅到深按业务语义：新增=主色、跟进=琥珀、签约=绿、流失=灰

def make_body(lead_colors, agent_colors):
    leads = [(l, v, c) for (l, v, _), c in zip(LEADS, lead_colors)]
    agents = [('学生', 60, agent_colors[0]), ('员工', 13, agent_colors[1])]
    events = ''.join(
        f'<div class="bh"><span class="bl" style="width:auto">{nm[:8]}</span>'
        f'<span class="bt"><i style="width:{round(cur/max*100)}%;background:var(--ac)"></i></span>'
        f'<b>{cur}</b></div>' for nm, cur, max in EVENTS)
    return f'''<div class="kpis">{__import__('build3').kpi_cards(0)}</div>
<div class="sh"><b>核心分析</b><span class="ln"></span></div>
<div class="grid3">
 <div class="panel"><h3>线索状态构成</h3><div class="hint">共 12 条 · 环形占比</div>
  <div class="donut-row">{donut(leads,128,17,('12','总线索'))}<div>{legend(leads)}</div></div></div>
 <div class="panel"><h3>成绩分段</h3><div class="hint">27 条成绩记录</div>{bars_h([(l,v) for l,v in SCORE],11)}</div>
 <div class="panel"><h3>智能体使用</h3><div class="hint">今日 73 次对话</div>
  <div class="donut-row">{donut(agents,112,15,('73','对话'))}<div>{legend(agents)}</div></div></div>
</div>
<div class="sh"><b>需要关注</b><span class="ln"></span></div>
<div class="grid2">
 <div class="panel"><h3>未处理心理预警</h3><div class="hint">3 条高风险 · 建议今日介入</div>{__import__('build3').alert_rows(4)}</div>
 <div class="panel"><h3>讲座报名进度</h3><div class="hint">即将开始的 5 场活动</div>{events}</div>
</div>'''

L_VARS = ('--bg:#f2f7f6;--top:#ffffff;--side:#f8fbfa;--card:#ffffff;--tx:#142b28;--mut:#7d9490;'
          '--bd:#dce9e6;--ac:#0d9488;--soft:#e3f5f1;--track:#e8f0ee;'
          '--hero:linear-gradient(120deg,#0f766e,#059669);--shadow:0 8px 22px rgba(13,148,136,.26);'
          '--red:#dc2626;--red-bg:#fee2e2;--red-tx:#b91c1c;--amber-bg:#fef3c7;--amber-tx:#a16207;')
L_EXTRA = 'body{background:radial-gradient(900px 380px at 88% -8%,rgba(5,150,105,.10),transparent),var(--bg)}'

M_VARS = ('--bg:#fbf7f1;--top:#fffdfa;--side:#fdfaf5;--card:#ffffff;--tx:#33261c;--mut:#9c8b7b;'
          '--bd:#eee3d5;--ac:#c2703d;--soft:#fbf0e4;--track:#f1e9df;'
          '--hero:linear-gradient(120deg,#b45309,#f59e0b);--shadow:0 8px 22px rgba(194,112,61,.26);'
          '--red:#c0392b;--red-bg:#fae4e0;--red-tx:#a93226;--amber-bg:#fdf0d5;--amber-tx:#a16207;')
M_EXTRA = 'body{background:linear-gradient(180deg,#fbf1e4 0%,#fbf8f3 240px)}'

N_VARS = ('--bg:#f3f5fa;--top:#ffffff;--side:#fafbff;--card:#ffffff;--tx:#17203a;--mut:#8791a8;'
          '--bd:#e2e7f2;--ac:#1d4ed8;--soft:#e8eeff;--track:#eaeef7;'
          '--hero:linear-gradient(120deg,#1e3a8a,#3730a3);--shadow:0 8px 22px rgba(29,78,216,.28);'
          '--red:#dc2626;--red-bg:#fee2e2;--red-tx:#b91c1c;--amber-bg:#fef3c7;--amber-tx:#a16207;')
N_EXTRA = 'body{background:radial-gradient(900px 360px at 86% -8%,rgba(29,78,216,.09),transparent),var(--bg)}'

PAGES = {
    'L': ('墨绿翡翠 · 沉静高级', L_VARS, L_EXTRA,
          make_body(['#0d9488','#d97706','#65a30d','#94a3b8'], ['#0d9488','#0891b2'])),
    'M': ('暖砂琥珀 · 教育亲和', M_VARS, M_EXTRA,
          make_body(['#d97706','#c2703d','#6f8f5e','#a8a29e'], ['#d97706','#a16207'])),
    'N': ('靛蓝统一 · 门户同系', N_VARS, N_EXTRA,
          make_body(['#2563eb','#f59e0b','#10b981','#94a3b8'], ['#3730a3','#0ea5e9'])),
}
for k, (name, vars_, extra, body) in PAGES.items():
    s = page(name, vars_, extra, body)
    open(os.path.join(OUT, 'style_%s.html' % k), 'w', encoding='utf-8').write(s)
    print(k, name, len(s))
