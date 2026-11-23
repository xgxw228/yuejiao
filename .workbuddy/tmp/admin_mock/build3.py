# -*- coding: utf-8 -*-
"""带数据总览 + 图表分析的 4 套后台样张，全真实数据，背景不再纯白。"""
import os
OUT = os.path.dirname(os.path.abspath(__file__))

# ---- 真实数据 ----
LEADS = [('新增意向',5,'#3b82f6'),('跟进中',4,'#f59e0b'),('已签约',1,'#10b981'),('已流失',2,'#94a3b8')]
SCORE = [('<60',5),('60-69',2),('70-79',6),('80-89',11),('90+',3)]
AGENT = [('学生侧',60,'#6366f1'),('员工侧',13,'#22d3ee')]
USERS = [('学生',7),('员工',6),('家长',2)]
TICKET = [('待处理',2,'#f59e0b'),('处理中',1,'#3b82f6'),('已解决',2,'#10b981')]
KPIS = [('12','客户线索','今日 +12','blue'),('4','跟进中','转化中','plain'),
        ('73','今日对话','AI 协同','plain'),('4','未处理预警','3 高风险','red')]
ALERTS = [('2','高','情绪评估命中「活不下去」，连续表达强烈压力'),
          ('3','高','情绪评估命中「活不下去」，需立即介入'),
          ('4','高','语义判定触发，边界测试语境'),
          ('1','中','连续两周失眠、不想上课，很少参加活动')]
EVENTS = [('新加坡留学分享会',19,30),('德国双元制说明会',20,20),('香港升学规划沙龙',11,25),
          ('新加坡公立大学解析',47,100),('中德项目家长见面会',22,40)]

NAV = [('概览','◎'),('客户线索','◇'),('心理预警','△'),('行政服务','▣'),
       ('反馈工单','✉'),('学生成绩','▥'),('对话记录','≡'),('讲座活动','◉')]


def donut(items, size=132, thick=17, center=None):
    """环形图：items=[(label,value,color)]"""
    import math
    total = sum(v for _, v, _ in items)
    r = (size - thick) / 2; cx = cy = size / 2
    circ = 2 * math.pi * r
    out = [f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}">']
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="var(--track)" stroke-width="{thick}"/>')
    acc = 0
    for _, v, col in items:
        seg = v / total * circ
        dash = f'{max(0,seg-2)} {circ}'
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{col}" stroke-width="{thick}" '
                   f'stroke-dasharray="{dash}" stroke-dashoffset="{-acc}" transform="rotate(-90 {cx} {cy})"/>')
        acc += seg
    if center:
        out.append(f'<text x="{cx}" y="{cy-2}" text-anchor="middle" font-size="26" font-weight="700" '
                   f'font-family="ui-monospace,monospace" fill="var(--tx)">{center[0]}</text>')
        out.append(f'<text x="{cx}" y="{cy+16}" text-anchor="middle" font-size="10" fill="var(--mut)">{center[1]}</text>')
    out.append('</svg>')
    return ''.join(out)


def legend(items):
    return ''.join(f'<div class="lg"><i style="background:{c}"></i><span>{l}</span><b>{v}</b></div>' for l, v, c in items)


def bars_h(items, maxv=None, color='var(--ac)'):
    maxv = maxv or max(v for _, v, *_ in items)
    out = []
    for it in items:
        label, v = it[0], it[1]
        col = it[2] if len(it) > 2 else color
        pct = round(v / maxv * 100)
        out.append(f'<div class="bh"><span class="bl">{label}</span><span class="bt"><i style="width:{pct}%;background:{col}"></i></span><b>{v}</b></div>')
    return ''.join(out)


def bars_v(items, maxv=None):
    maxv = maxv or max(v for _, v in items)
    out = ['<div class="bv">']
    for label, v in items:
        h = round(v / maxv * 100)
        out.append(f'<div class="bvc"><div class="bvtrack"><i style="height:{h}%"></i></div><span>{label}</span><b>{v}</b></div>')
    out.append('</div>')
    return ''.join(out)


def nav():
    return ''.join(f'<a class="{"on" if i==0 else ""}"><span>{ic}</span>{lb}</a>' for i, (lb, ic) in enumerate(NAV))


def kpi_cards(hero_idx=0):
    out = []
    for i, (v, k, tag, tone) in enumerate(KPIS):
        cls = 'hero' if i == hero_idx else 'plain'
        out.append(f'<div class="kc {cls} {tone}"><div class="kv">{v}</div><div class="kk">{k}</div><div class="kt">{tag}</div></div>')
    return ''.join(out)


def alert_rows(limit=4):
    out = []
    for sid, lv, msg in ALERTS[:limit]:
        cls = 'h' if lv == '高' else 'm'
        out.append(f'<div class="ar"><span class="aid">#{sid}</span><span class="risk {cls}">{lv}</span>'
                   f'<span class="amsg">{msg}</span><span class="ago">查看 →</span></div>')
    return ''.join(out)


BASE = '''
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;font-size:13px;-webkit-font-smoothing:antialiased;color:var(--tx)}
.top{height:58px;display:flex;align-items:center;gap:12px;padding:0 22px;background:var(--top);border-bottom:1px solid var(--bd)}
.logo{width:27px;height:27px;background:var(--ac);color:#fff;display:grid;place-items:center;font-weight:800;border-radius:6px;font-size:13px}
.top h1{font-size:14px;margin:0;font-weight:700}.crumb{color:var(--mut);font-size:10px;font-family:ui-monospace,monospace;letter-spacing:.1em}
.sp{flex:1}.who{font-size:11px;color:var(--mut)}.top a{font-size:11px;color:var(--mut);border:1px solid var(--bd);padding:5px 11px;border-radius:6px;text-decoration:none}
.wrap{display:grid;grid-template-columns:200px 1fr;min-height:calc(100vh - 58px)}
.side{background:var(--side);border-right:1px solid var(--bd);padding:14px 9px}
.st{font-family:ui-monospace,monospace;font-size:9px;letter-spacing:.15em;color:var(--mut);padding:0 11px 9px}
.side a{display:flex;align-items:center;gap:10px;padding:9px 11px;border-radius:6px;color:var(--tx);text-decoration:none;font-size:12.5px;margin-bottom:2px}
.side a.on{background:var(--soft);color:var(--ac);font-weight:700}.side a span{width:14px;text-align:center;opacity:.7}
.main{padding:22px 26px 36px;min-width:0}
.mh{display:flex;align-items:baseline;gap:11px;margin-bottom:16px}.mh h2{font-size:20px;margin:0;font-weight:750}.mh .sub{font-size:11px;color:var(--mut)}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.kc{padding:16px 18px;border-radius:10px;min-height:104px;position:relative;overflow:hidden}
.kc.hero{background:var(--hero);color:#fff;box-shadow:var(--shadow)}
.kc.plain{background:var(--card);border:1px solid var(--bd)}
.kv{font-family:ui-monospace,monospace;font-size:32px;font-weight:700;line-height:1}
.kk{font-size:12px;margin-top:8px;font-weight:600;opacity:.92}
.kt{font-size:9.5px;font-family:ui-monospace,monospace;margin-top:7px;opacity:.75;letter-spacing:.05em}
.kc.red .kv{color:var(--red)}.kc.hero .kv{color:#fff}
.sh{display:flex;align-items:center;gap:10px;margin:20px 0 10px}.sh b{font-size:12.5px;font-weight:700}.sh .ln{flex:1;height:1px;background:var(--bd)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.grid3{display:grid;grid-template-columns:1.1fr .95fr .95fr;gap:12px}
.panel{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:16px 18px}
.panel h3{margin:0;font-size:12.5px;font-weight:700}.panel .hint{font-size:10px;color:var(--mut);margin-top:3px}
.donut-row{display:flex;align-items:center;gap:14px;margin-top:10px}
.lg{display:flex;align-items:center;gap:7px;font-size:11px;margin:6px 0}.lg i{width:8px;height:8px;border-radius:2px;flex:none}.lg span{color:var(--mut)}.lg b{margin-left:auto;font-family:ui-monospace,monospace}
.bh{display:grid;grid-template-columns:56px 1fr 28px;gap:9px;align-items:center;font-size:11px;margin-top:11px}
.bh .bl{color:var(--mut)}.bh .bt{height:8px;background:var(--track);border-radius:99px;overflow:hidden}.bh .bt i{display:block;height:100%;border-radius:99px}.bh b{text-align:right;font-family:ui-monospace,monospace;font-weight:600}
.bv{display:flex;align-items:flex-end;gap:9px;height:120px;margin-top:14px}
.bvc{flex:1;display:flex;flex-direction:column;align-items:center;height:100%}
.bvtrack{flex:1;width:100%;display:flex;align-items:flex-end;background:var(--track);border-radius:5px;overflow:hidden}
.bvtrack i{width:100%;background:var(--ac);border-radius:5px 5px 0 0}
.bvc span{font-size:9.5px;color:var(--mut);margin-top:6px}.bvc b{font-size:10px;font-family:ui-monospace,monospace;margin-top:2px}
.ar{display:grid;grid-template-columns:38px 42px 1fr 44px;gap:10px;align-items:center;padding:11px 0;border-bottom:1px solid var(--bd);font-size:11.5px}
.ar:last-child{border-bottom:0}.aid{font-family:ui-monospace,monospace;color:var(--mut)}
.risk{font-size:10px;padding:2px 7px;border-radius:4px;font-weight:700;text-align:center}
.risk.h{background:var(--red-bg);color:var(--red-tx)}.risk.m{background:var(--amber-bg);color:var(--amber-tx)}
.amsg{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ago{color:var(--ac);text-align:right;font-size:10.5px}
.ring-mini{display:flex;align-items:center;gap:10px;margin-top:10px}
.ring-mini .rv{font-family:ui-monospace,monospace;font-size:20px;font-weight:700}
'''


def page(name, vars_, extra, body):
    css = BASE + ':root{' + vars_ + '}' + extra
    return f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>{name}</title><style>{css}</style></head><body>
<div class="top"><div class="logo">粤</div><h1>粤教服务 · 数据后台</h1><span class="crumb">DATA / 概览</span><div class="sp"></div><span class="who">王主任 · 管理员</span><a>返回工作台</a></div>
<div class="wrap"><aside class="side"><div class="st">WORKSPACE</div>{nav()}</aside>
<main class="main"><div class="mh"><h2>数据总览</h2><span class="sub">2026-11-18 · 周三 · 实时</span></div>{body}</main></div></body></html>'''


# ===== H：柔和渐变 · 现代 SaaS（推荐候选）=====
H_VARS = ('--bg:#f4f6fb;--top:#ffffff;--side:#ffffff;--card:#ffffff;--tx:#1b2440;--mut:#8b95ab;'
          '--bd:#e8ecf5;--ac:#4f46e5;--soft:#eef0ff;--track:#eef1f7;'
          '--hero:linear-gradient(120deg,#4f46e5,#7c3aed);--shadow:0 8px 22px rgba(79,70,229,.28);'
          '--red:#dc2626;--red-bg:#fee2e2;--red-tx:#b91c1c;--amber-bg:#fef3c7;--amber-tx:#a16207;')
H_EXTRA = 'body{background:radial-gradient(900px 380px at 88% -8%,rgba(124,58,237,.09),transparent),var(--bg)}'
h_body = f'''<div class="kpis">{kpi_cards(0)}</div>
<div class="sh"><b>核心分析</b><span class="ln"></span></div>
<div class="grid3">
 <div class="panel"><h3>线索状态构成</h3><div class="hint">共 12 条 · 环形占比</div>
  <div class="donut-row">{donut(LEADS,128,17,('12','总线索'))}<div>{legend(LEADS)}</div></div></div>
 <div class="panel"><h3>成绩分段</h3><div class="hint">27 条成绩记录</div>{bars_h([(l,v) for l,v in SCORE],11)}</div>
 <div class="panel"><h3>智能体使用</h3><div class="hint">今日 73 次对话</div>
  <div class="donut-row">{donut(AGENT,112,15,('73','对话'))}<div>{legend(AGENT)}</div></div></div>
</div>
<div class="sh"><b>需要关注</b><span class="ln"></span></div>
<div class="grid2">
 <div class="panel"><h3>未处理心理预警</h3><div class="hint">3 条高风险 · 建议今日介入</div>{alert_rows(4)}</div>
 <div class="panel"><h3>讲座报名进度</h3><div class="hint">即将开始的 5 场活动</div>
  {''.join(f'<div class="bh"><span class="bl" style="width:auto">{nm[:8]}</span><span class="bt"><i style="width:{round(cur/max*100)}%;background:var(--ac)"></i></span><b>{cur}</b></div>' for nm,cur,max in EVENTS)}</div>
</div>'''

# ===== I：深色驾驶舱 · Data Ops =====
I_VARS = ('--bg:#0b1020;--top:#101830;--side:#0e1628;--card:#121c33;--tx:#e8eefb;--mut:#8593b3;'
          '--bd:#253356;--ac:#4ea8ff;--soft:#16264a;--track:#1c2947;'
          '--hero:linear-gradient(120deg,#3b82f6,#06b6d4);--shadow:0 8px 26px rgba(14,165,233,.25);'
          '--red:#ff6b7d;--red-bg:#3a1e2b;--red-tx:#ff9aaa;--amber-bg:#3a2f12;--amber-tx:#ffc861;')
I_EXTRA = 'body{background:radial-gradient(1000px 420px at 82% -10%,rgba(78,168,255,.12),transparent),var(--bg)} .kv{text-shadow:0 0 18px rgba(78,168,255,.35)}'
i_body = f'''<div class="kpis">{kpi_cards(0)}</div>
<div class="sh"><b>核心分析</b><span class="ln"></span></div>
<div class="grid3">
 <div class="panel"><h3>线索状态构成</h3><div class="hint">共 12 条 · 环形占比</div>
  <div class="donut-row">{donut(LEADS,128,17,('12','总线索'))}<div>{legend(LEADS)}</div></div></div>
 <div class="panel"><h3>成绩分段</h3><div class="hint">27 条成绩记录</div>{bars_h([(l,v) for l,v in SCORE],11)}</div>
 <div class="panel"><h3>智能体使用</h3><div class="hint">今日 73 次对话</div>
  <div class="donut-row">{donut(AGENT,112,15,('73','对话'))}<div>{legend(AGENT)}</div></div></div>
</div>
<div class="sh"><b>需要关注</b><span class="ln"></span></div>
<div class="grid2">
 <div class="panel"><h3>未处理心理预警</h3><div class="hint">3 条高风险 · 建议今日介入</div>{alert_rows(4)}</div>
 <div class="panel"><h3>讲座报名进度</h3><div class="hint">即将开始的 5 场活动</div>
  {''.join(f'<div class="bh"><span class="bl" style="width:auto">{nm[:8]}</span><span class="bt"><i style="width:{round(cur/max*100)}%;background:var(--ac)"></i></span><b>{cur}</b></div>' for nm,cur,max in EVENTS)}</div>
</div>'''

# ===== J：浅蓝灰 · 清爽商务（3平1渐变，柱状图主打）=====
J_VARS = ('--bg:#eef3f8;--top:#ffffff;--side:#f7fafd;--card:#ffffff;--tx:#16233a;--mut:#7d8ba3;'
          '--bd:#dce5f0;--ac:#2563eb;--soft:#e5efff;--track:#e9eef5;'
          '--hero:linear-gradient(120deg,#0ea5e9,#2563eb);--shadow:0 8px 22px rgba(37,99,235,.25);'
          '--red:#dc2626;--red-bg:#fee2e2;--red-tx:#b91c1c;--amber-bg:#fef3c7;--amber-tx:#a16207;')
J_EXTRA = 'body{background:linear-gradient(180deg,#e6eef8 0%,#f4f7fb 220px)} .panel{border-radius:8px}'
j_body = f'''<div class="kpis">{kpi_cards(1)}</div>
<div class="sh"><b>核心分析</b><span class="ln"></span></div>
<div class="grid3">
 <div class="panel"><h3>成绩分段分布</h3><div class="hint">27 条 · 柱状对比</div>{bars_v(SCORE)}</div>
 <div class="panel"><h3>线索状态构成</h3><div class="hint">共 12 条 · 环形占比</div>
  <div class="donut-row">{donut(LEADS,120,16,('12','线索'))}<div>{legend(LEADS)}</div></div></div>
 <div class="panel"><h3>用户角色</h3><div class="hint">15 个账号</div>
  <div class="donut-row">{donut([(l,v,{'学生':'#2563eb','员工':'#0ea5e9','家长':'#94a3b8'}[l]) for l,v in USERS],108,15,('15','用户'))}<div>{legend([(l,v,{'学生':'#2563eb','员工':'#0ea5e9','家长':'#94a3b8'}[l]) for l,v in USERS])}</div></div></div>
</div>
<div class="sh"><b>需要关注</b><span class="ln"></span></div>
<div class="grid2">
 <div class="panel"><h3>未处理心理预警</h3><div class="hint">3 条高风险 · 建议今日介入</div>{alert_rows(4)}</div>
 <div class="panel"><h3>工单处理状态</h3><div class="hint">共 5 条反馈工单</div>
  <div class="donut-row">{donut(TICKET,118,16,('5','工单'))}<div>{legend(TICKET)}</div></div></div>
</div>'''

# ===== K：米白档案 · 稳重报告风（细线 + 低饱和图表）=====
K_VARS = ('--bg:#f6f4ee;--top:#fffdf8;--side:#faf8f2;--card:#fffdf8;--tx:#29251e;--mut:#938b7b;'
          '--bd:#e5dfd2;--ac:#9a3b2f;--soft:#f3ece1;--track:#ebe4d7;'
          '--hero:linear-gradient(120deg,#8a3b2f,#b4613f);--shadow:0 6px 18px rgba(138,59,47,.2);'
          '--red:#b53232;--red-bg:#f3e0de;--red-tx:#9a3b2f;--amber-bg:#f6ead4;--amber-tx:#96601a;')
K_EXTRA = 'body{background:#f6f4ee} h2,h3{font-family:Georgia,"Songti SC",serif}.kc,.panel{border-radius:2px}'
k_body = f'''<div class="kpis">{kpi_cards(0)}</div>
<div class="sh"><b>核心分析</b><span class="ln"></span></div>
<div class="grid3">
 <div class="panel"><h3>线索状态构成</h3><div class="hint">共 12 条 · 环形占比</div>
  <div class="donut-row">{donut([(l,v,{'新增意向':'#9a3b2f','跟进中':'#c08a3e','已签约':'#6f8f5e','已流失':'#a9a196'}[l]) for l,v,_ in LEADS],128,17,('12','总线索'))}<div>{legend([(l,v,{'新增意向':'#9a3b2f','跟进中':'#c08a3e','已签约':'#6f8f5e','已流失':'#a9a196'}[l]) for l,v,_ in LEADS])}</div></div></div>
 <div class="panel"><h3>成绩分段</h3><div class="hint">27 条成绩记录</div>{bars_h([(l,v) for l,v in SCORE],11,'#9a3b2f')}</div>
 <div class="panel"><h3>智能体使用</h3><div class="hint">今日 73 次对话</div>
  <div class="donut-row">{donut([('学生',60,'#9a3b2f'),('员工',13,'#c08a3e')],112,15,('73','对话'))}<div>{legend([('学生',60,'#9a3b2f'),('员工',13,'#c08a3e')])}</div></div></div>
</div>
<div class="sh"><b>需要关注</b><span class="ln"></span></div>
<div class="grid2">
 <div class="panel"><h3>未处理心理预警</h3><div class="hint">3 条高风险 · 建议今日介入</div>{alert_rows(4)}</div>
 <div class="panel"><h3>讲座报名进度</h3><div class="hint">即将开始的 5 场活动</div>
  {''.join(f'<div class="bh"><span class="bl" style="width:auto">{nm[:8]}</span><span class="bt"><i style="width:{round(cur/max*100)}%;background:#9a3b2f"></i></span><b>{cur}</b></div>' for nm,cur,max in EVENTS)}</div>
</div>'''

PAGES = {
 'H': ('柔和渐变 · 现代 SaaS', H_VARS, H_EXTRA, h_body),
 'I': ('深色驾驶舱 · Data Ops', I_VARS, I_EXTRA, i_body),
 'J': ('浅蓝灰 · 清爽商务', J_VARS, J_EXTRA, j_body),
 'K': ('米白档案 · 稳重报告', K_VARS, K_EXTRA, k_body),
}
for k,(name,vars_,extra,body) in PAGES.items():
    s = page(name, vars_, extra, body)
    open(os.path.join(OUT, 'style_%s.html'%k),'w',encoding='utf-8').write(s)
    print(k, name, len(s))
