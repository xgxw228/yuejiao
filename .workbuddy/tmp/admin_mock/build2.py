# -*- coding: utf-8 -*-
"""重做：3 套信息架构真正不同的后台样张，全部真实数据。"""
import os
OUT = os.path.dirname(os.path.abspath(__file__))

NAV = [('概览','◎','12'),('客户线索','◇','12'),('心理预警','△','4'),('行政服务','▣','7'),
       ('反馈工单','✉','3'),('学生成绩','▥','27'),('对话记录','≡','73'),('讲座活动','◉','5')]

ALERTS = [
    ('2', '高', '情绪评估命中「活不下去」：最近压力好大，感觉活不下去了', '08:26'),
    ('3', '高', '情绪评估命中「活不下去」：最近压力好大，感觉活不下去了', '08:26'),
    ('1', '中', '连续两周提到失眠、不想上课，同宿舍同学反映很少参加活动', '08:11'),
]
LEADS = [
    ('许明','跟进中','138****0002','19 岁高中毕业，意向新加坡本科','2026-11-18 08:11'),
    ('陈嘉怡','新增意向','137****0003','22 岁大专毕业，想快速拿本科','2026-11-18 08:11'),
    ('刘一鸣','新增意向','136****0004','17 岁中职机电，德语零基础','2026-11-18 08:11'),
    ('张三','跟进中','135****0001','意向德国双元制，已录成绩','2026-11-18 08:16'),
    ('吴天成','已签约','139****0009','德国双元制已签约','2026-11-18 08:20'),
]
DIST = [('新增意向',5,'#2563eb'),('跟进中',4,'#f59e0b'),('已签约',1,'#16a34a'),('已流失',2,'#94a3b8')]
EVENTS = [('新加坡留学分享会','11-21 19:00',19,30),('德国双元制项目说明会','11-23 20:00',20,20),
          ('香港升学规划沙龙','11-27 14:00',11,25),('新加坡公立大学申请解析','11-30 19:00',47,100)]

CSS_BASE = '''
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;font-size:13px;-webkit-font-smoothing:antialiased}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.top{height:60px;display:flex;align-items:center;gap:12px;padding:0 24px;background:var(--panel);border-bottom:1px solid var(--bd)}
.logo{width:28px;height:28px;background:var(--ac);color:#fff;display:grid;place-items:center;font-weight:800;border-radius:var(--r)}
.top h1{font-size:14px;margin:0;font-weight:700}.crumb{color:var(--mut);font-size:11px;font-family:ui-monospace,monospace;letter-spacing:.1em}
.spacer{flex:1}.who{font-size:12px;color:var(--mut)}.top a{font-size:12px;color:var(--mut);text-decoration:none;border:1px solid var(--bd);padding:5px 12px;border-radius:var(--r)}
.wrap{display:grid;grid-template-columns:212px 1fr;min-height:calc(100vh - 60px)}
.side{background:var(--side);border-right:1px solid var(--bd);padding:16px 10px}
.side .st{font-family:ui-monospace,monospace;font-size:9.5px;letter-spacing:.16em;color:var(--mut);padding:0 12px 10px}
.side a{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:var(--r);color:var(--tx);text-decoration:none;font-size:13px;margin-bottom:2px}
.side a.on{background:var(--soft);color:var(--ac);font-weight:700}.side a:hover:not(.on){background:var(--hover)}
.side a .ic{width:15px;text-align:center;opacity:.75}.side a .n{margin-left:auto;font-family:ui-monospace,monospace;font-size:11px;color:var(--mut)}
.side a.on .n{color:var(--ac)}
.main{padding:24px 28px 40px;min-width:0;background:var(--bg)}
.mh{display:flex;align-items:flex-end;gap:12px;margin-bottom:18px}.mh h2{font-size:21px;margin:0;font-weight:750;letter-spacing:-.01em}
.mh .sub{font-size:12px;color:var(--mut);padding-bottom:3px}
.card{background:var(--panel);border:1px solid var(--bd);border-radius:var(--r);overflow:hidden}
.sec-h{display:flex;align-items:center;gap:10px;margin:22px 0 11px}
.sec-h b{font-size:13px;font-weight:700}.sec-h .line{flex:1;height:1px;background:var(--bd)}
.sec-h .more{font-size:11px;color:var(--ac);text-decoration:none}
'''


def head(title, crumb='DATA / 概览'):
    nav = ''.join(f'<a class="{"on" if i==0 else ""}"><span class="ic">{ic}</span>{lb}<span class="n">{n}</span></a>'
                  for i,(lb,ic,n) in enumerate(NAV))
    return f'''<div class="top"><div class="logo">粤</div><h1>粤教服务 · 数据后台</h1><span class="crumb">{crumb}</span>
<div class="spacer"></div><span class="who">管理员 · 梁老师</span><a href="#">返回工作台</a></div>
<div class="wrap"><aside class="side"><div class="st">WORKSPACE / 工作区</div>{nav}</aside>
<main class="main"><div class="mh"><h2>{title}</h2><span class="sub">2026 年 11 月 18 日 · 周三</span></div>'''


def foot():
    return '</main></div>'


def page(name, vars_, radius, extra, body):
    css = CSS_BASE.replace('var(--r)', radius) + f':root{{{vars_}}}' + extra
    return f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>{name}</title><style>{css}</style></head><body>{body}{foot()}</body></html>'''


# ============ E：Linear 式「行动优先」 ============
E_EXTRA = '''
.todo{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.todo .t{padding:16px 18px;border:1px solid var(--bd);border-left-width:3px;background:var(--panel);border-radius:var(--r)}
.todo .t.red{border-left-color:#dc2626}.todo .t.amber{border-left-color:#d97706}.todo .t.blue{border-left-color:#2563eb}
.todo .num{font-family:ui-monospace,monospace;font-size:31px;font-weight:700;line-height:1;color:var(--tx)}
.todo .lb{font-size:12.5px;font-weight:650;margin-top:8px}.todo .ds{font-size:11px;color:var(--mut);margin-top:4px}
.todo .go{display:inline-block;font-size:11px;color:var(--ac);margin-top:11px;text-decoration:none;font-weight:600}
.alert-row{display:grid;grid-template-columns:56px 70px 1fr 110px;gap:12px;align-items:center;padding:12px 16px;border-bottom:1px solid var(--bd)}
.alert-row:last-child{border-bottom:0}.alert-row .sid{font-family:ui-monospace,monospace;font-size:11px;color:var(--mut)}
.risk{font-size:10.5px;padding:2px 8px;border-radius:var(--r);font-weight:700;display:inline-block}
.risk.h{background:#fee2e2;color:#b91c1c}.risk.m{background:#fef3c7;color:#a16207}
.alert-row .msg{font-size:12.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.alert-row .tm{font-family:ui-monospace,monospace;font-size:10.5px;color:var(--mut);text-align:right}
.alert-row .act{font-size:11px;color:var(--ac);text-align:right;text-decoration:none;font-weight:600}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.kp{padding:15px 17px;border:1px solid var(--bd);border-radius:var(--r);background:var(--panel)}
.kp .v{font-family:ui-monospace,monospace;font-size:29px;font-weight:700;line-height:1}.kp .k{font-size:11.5px;color:var(--mut);margin-top:7px}
.kp .tag{font-size:9.5px;font-family:ui-monospace,monospace;letter-spacing:.1em;color:var(--ac);margin-top:6px;display:block}
.dist{padding:16px 18px}.bar{display:grid;grid-template-columns:62px 1fr 30px;gap:10px;align-items:center;margin:11px 0;font-size:11.5px}
.bar .track{height:7px;background:#eef1f6;border-radius:99px;overflow:hidden}.bar .fill{height:100%;border-radius:99px}
.bar .pct{font-family:ui-monospace,monospace;color:var(--mut);font-size:10.5px;text-align:right}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
'''
e_body = head('今天要处理什么', 'DATA / 行动台') + '''
<div class="todo">
  <div class="t red"><div class="num">4</div><div class="lb">未处理心理预警</div><div class="ds">其中 3 条高风险 · 含自伤表述</div><a class="go" href="#">查看预警 →</a></div>
  <div class="t amber"><div class="num">7</div><div class="lb">待审批行政服务</div><div class="ds">全部为请假申请 · 最早 11-18</div><a class="go" href="#">去审批 →</a></div>
  <div class="t blue"><div class="num">3</div><div class="lb">未结反馈工单</div><div class="ds">2 条待处理 · 1 条处理中</div><a class="go" href="#">查看工单 →</a></div>
</div>
<div class="sec-h"><b>需要立即关注</b><span class="line"></span><a class="more" href="#">全部 4 条 →</a></div>
<div class="card">
''' + ''.join(f'''<div class="alert-row"><span class="sid">#{i}</span><span><span class="risk {"h" if lv=="高" else "m"}">{lv}风险</span></span>
<span class="msg">{msg}</span><span class="tm">{tm} · 未处理</span><a class="act" href="#">处理 →</a></div>''' for i,lv,msg,tm in ALERTS) + '''
</div>
<div class="sec-h"><b>业务速览</b><span class="line"></span></div>
<div class="kpis">
  <div class="kp"><div class="v">12</div><div class="k">客户线索</div><span class="tag">今日新增 12</span></div>
  <div class="kp"><div class="v">4</div><div class="k">跟进中线索</div><span class="tag">占比 33%</span></div>
  <div class="kp"><div class="v">73</div><div class="k">今日对话</div><span class="tag">3 类智能体</span></div>
  <div class="kp"><div class="v">5</div><div class="k">即将开始讲座</div><span class="tag">最近 11-21</span></div>
</div>
<div class="two" style="margin-top:12px">
  <div class="card dist"><div style="font-size:12px;font-weight:700">线索状态分布</div>
''' + ''.join(f'''<div class="bar"><span>{lb}</span><span class="track"><span class="fill" style="width:{n*17}%;background:{col}"></span></span><span class="pct">{n}</span></div>''' for lb,n,col in DIST) + '''
  </div>
  <div class="card dist"><div style="font-size:12px;font-weight:700">近期讲座 · 报名</div>
''' + ''.join(f'''<div class="bar" style="grid-template-columns:1fr 84px 34px"><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{nm}</span><span class="track"><span class="fill" style="width:{int(cur/max*100)}%;background:#2563eb"></span></span><span class="pct">{cur}</span></div>''' for nm,dt,cur,max in EVENTS) + '''
  </div>
</div>'''

# ============ F：Stripe/Vercel 式「经营驾驶舱」 ============
F_EXTRA = '''
.hero-kpi{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.hero-kpi .k{padding:20px 22px;border:1px solid var(--bd);border-radius:var(--r);background:var(--panel)}
.hero-kpi .lab{font-size:11px;color:var(--mut);letter-spacing:.02em}
.hero-kpi .val{font-family:ui-monospace,monospace;font-size:40px;font-weight:700;line-height:1.1;margin-top:9px;letter-spacing:-.03em}
.hero-kpi .chg{font-size:10.5px;color:#16a34a;margin-top:8px;font-weight:600}
.hero-kpi .chg.warn{color:#d97706}.hero-kpi .chg.bad{color:#dc2626}
.panel{padding:20px 22px}
.dist2{margin-top:16px}
.dist2 .row{display:grid;grid-template-columns:78px 1fr 44px;gap:12px;align-items:center;margin:13px 0;font-size:12px}
.dist2 .track{height:9px;background:#f0f2f7;border-radius:99px;overflow:hidden}
.dist2 .fill{height:100%;border-radius:99px;display:block}
.dist2 .pct{font-family:ui-monospace,monospace;font-size:11px;color:var(--mut);text-align:right}
.tbl{width:100%;border-collapse:collapse;font-size:12px}
.tbl th{text-align:left;font-family:ui-monospace,monospace;font-size:9.5px;letter-spacing:.1em;color:var(--mut);padding:10px 14px;border-bottom:1px solid var(--bd)}
.tbl td{padding:11px 14px;border-bottom:1px solid var(--bd)}
.tbl tr:last-child td{border-bottom:0}
.pill{font-size:10.5px;padding:2px 9px;border-radius:99px;background:#f1f3f8;color:#5b6478;white-space:nowrap}
.pill.w{background:#fef3c7;color:#a16207}.pill.o{background:#dcfce7;color:#15803d}.pill.b{background:#fee2e2;color:#b91c1c}
'''
f_body = head('经营概览', 'DATA / 概览') + '''
<div class="hero-kpi">
  <div class="k"><div class="lab">客户线索</div><div class="val">12</div><div class="chg">↑ 今日新增 12 · 全部为今日录入</div></div>
  <div class="k"><div class="lab">已签约</div><div class="val">1</div><div class="chg warn">转化率 8.3% · 4 条跟进中</div></div>
  <div class="k"><div class="lab">未处理预警</div><div class="val" style="color:#dc2626">4</div><div class="chg bad">3 条高风险 · 需立即介入</div></div>
  <div class="k"><div class="lab">今日对话</div><div class="val">73</div><div class="chg">3 类智能体协同处理</div></div>
</div>
<div class="sec-h"><b>结构分析</b><span class="line"></span></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
  <div class="card panel"><div style="font-size:13px;font-weight:700">线索状态分布</div><div style="font-size:11px;color:var(--mut);margin-top:4px">共 12 条 · 按状态聚合</div>
  <div class="dist2">
''' + ''.join(f'''<div class="row"><span>{lb}</span><span class="track"><span class="fill" style="width:{n/12*100}%;background:{col}"></span></span><span class="pct">{n} / 12</span></div>''' for lb,n,col in DIST) + '''
  </div></div>
  <div class="card panel"><div style="font-size:13px;font-weight:700">待办事项</div><div style="font-size:11px;color:var(--mut);margin-top:4px">按紧急程度排序</div>
  <div class="dist2">
   <div class="row"><span style="color:#b91c1c;font-weight:700">高风险预警</span><span class="track"><span class="fill" style="width:75%;background:#dc2626"></span></span><span class="pct">3</span></div>
   <div class="row"><span>待审批请假</span><span class="track"><span class="fill" style="width:88%;background:#f59e0b"></span></span><span class="pct">7</span></div>
   <div class="row"><span>待处理工单</span><span class="track"><span class="fill" style="width:50%;background:#2563eb"></span></span><span class="pct">3</span></div>
   <div class="row"><span>跟进中线索</span><span class="track"><span class="fill" style="width:33%;background:#64748b"></span></span><span class="pct">4</span></div>
  </div></div>
</div>
<div class="sec-h"><b>最近线索</b><span class="line"></span><a class="more" href="#">查看全部 12 条 →</a></div>
<div class="card"><table class="tbl"><thead><tr><th>客户</th><th>状态</th><th>联系方式</th><th>背景</th><th>录入时间</th></tr></thead><tbody>
''' + ''.join(f'''<tr><td style="font-weight:700">{nm}</td><td><span class="pill {"w" if st=="跟进中" else "o" if st=="已签约" else ""}">{st}</span></td><td class="mono">{ph}</td><td style="color:var(--mut)">{bg}</td><td class="mono" style="color:var(--mut)">{tm}</td></tr>''' for nm,st,ph,bg,tm in LEADS) + '''
</tbody></table></div>'''

# ============ G：Notion/飞书式「数据库工作台」 ============
G_EXTRA = '''
.filters{display:flex;gap:8px;align-items:center;margin-bottom:14px;flex-wrap:wrap}
.chip{font-size:11.5px;padding:6px 13px;border:1px solid var(--bd);border-radius:var(--r);background:var(--panel);cursor:pointer}
.chip.on{background:var(--ac);color:#fff;border-color:var(--ac);font-weight:700}
.view{display:flex;border:1px solid var(--bd);border-radius:var(--r);overflow:hidden;margin-left:8px}
.view span{font-size:11px;padding:6px 12px;background:var(--panel);border-right:1px solid var(--bd)}
.view span.on{background:var(--soft);color:var(--ac);font-weight:700}
.gwrap{display:grid;grid-template-columns:1fr;gap:14px}
.gcard{padding:18px 20px}
.gcard h3{margin:0;font-size:14px;font-weight:700}.gcard .desc{font-size:11px;color:var(--mut);margin-top:4px}
.grid-tbl{width:100%;border-collapse:collapse;margin-top:16px;font-size:12px}
.grid-tbl th{text-align:left;font-size:10px;color:var(--mut);font-weight:600;padding:8px 10px;border-bottom:1px solid var(--bd);border-top:1px solid var(--bd)}
.grid-tbl td{padding:9px 10px;border-bottom:1px solid var(--bd)}
.tag{font-size:10.5px;padding:2px 9px;border-radius:99px;background:#f1f3f8;color:#5b6478}
.tag.w{background:#fef3c7;color:#a16207}.tag.o{background:#dcfce7;color:#15803d}
.avatar{display:inline-grid;place-items:center;width:22px;height:22px;border-radius:50%;background:#e0e7ff;color:#4338ca;font-size:10px;margin-right:6px}
.gcards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:16px}
.icard{border:1px solid var(--bd);border-radius:var(--r);padding:15px 16px;background:var(--panel)}
.icard .t{font-size:13px;font-weight:700}.icard .m{font-size:11px;color:var(--mut);margin-top:6px}
.icard .foot{display:flex;align-items:center;gap:8px;margin-top:12px;font-size:10.5px;color:var(--mut)}
.prog{height:5px;background:#eef1f6;border-radius:99px;overflow:hidden;margin-top:10px}.prog i{display:block;height:100%;background:var(--ac)}
'''
g_body = head('数据工作台', 'DATA / 工作台') + '''
<div class="filters">
  <span class="chip on">全部 12</span><span class="chip">新增意向 5</span><span class="chip">跟进中 4</span><span class="chip">已签约 1</span><span class="chip">已流失 2</span>
  <span class="view"><span class="on">▤ 表格</span><span>▦ 看板</span></span>
</div>
<div class="gwrap">
 <div class="card gcard"><h3>客户线索 <span style="font-size:11px;color:var(--mut);font-weight:400">/ crm_lead</span></h3><div class="desc">按状态筛选 · 点击行查看跟进详情</div>
 <table class="grid-tbl"><thead><tr><th>☑</th><th>客户名称</th><th>状态</th><th>负责人</th><th>背景信息</th><th>创建时间</th></tr></thead><tbody>
''' + ''.join(f'''<tr><td style="color:var(--mut)">☐</td><td style="font-weight:700">{nm}</td><td><span class="tag {"w" if st=="跟进中" else "o" if st=="已签约" else ""}">{st}</span></td><td><span class="avatar">李</span>李顾问</td><td style="color:var(--mut)">{bg}</td><td class="mono" style="color:var(--mut);font-size:10.5px">{tm}</td></tr>''' for nm,st,ph,bg,tm in LEADS) + '''
</tbody></table></div>
 <div class="gcard" style="padding:0"><div class="sec-h" style="margin:0 0 12px"><b>工作区步调</b><span class="line"></span></div>
 <div class="gcards">
  <div class="icard"><div class="t">心理预警</div><div class="m">4 条未处理 · 3 条高风险</div><div class="prog"><i style="width:80%;background:#dc2626"></i></div><div class="foot">需今日介入</div></div>
  <div class="icard"><div class="t">行政服务</div><div class="m">7 条请假待审批</div><div class="prog"><i style="width:55%;background:#f59e0b"></i></div><div class="foot">7 / 14 待处理</div></div>
  <div class="icard"><div class="t">反馈工单</div><div class="m">3 条未解决</div><div class="prog"><i style="width:40%;background:#2563eb"></i></div><div class="foot">3 / 5 未解决</div></div>
 </div></div>
</div>'''

PAGES = {
 'E': ('行动优先工作台（Linear 式）', '--bg:#f7f8fa;--panel:#fff;--side:#fff;--tx:#1c2333;--mut:#8a93a4;--bd:#e6e9f0;--ac:#2563eb;--soft:#eef3ff;--hover:#f7f9ff', '6px', E_EXTRA, e_body),
 'F': ('经营驾驶舱（Stripe / Vercel 式）', '--bg:#f6f7fb;--panel:#fff;--side:#fff;--tx:#171f35;--mut:#8a93a8;--bd:#e6e9f1;--ac:#4f46e5;--soft:#eef0ff;--hover:#f7f8ff', '10px', F_EXTRA, f_body),
 'G': ('数据库工作台（Notion / 飞书式）', '--bg:#fbfbfc;--panel:#fff;--side:#fff;--tx:#202124;--mut:#9aa0aa;--bd:#e8e8ec;--ac:#2563eb;--soft:#e8f0fe;--hover:#f6f8fd', '6px', G_EXTRA, g_body),
}
for k,(name,vars_,r,extra,body) in PAGES.items():
    s = page(name, vars_, r, extra, body)
    open(os.path.join(OUT,'style_%s.html'%k),'w',encoding='utf-8').write(s)
    print(k, name, len(s))
