# -*- coding: utf-8 -*-
"""生成 4 套后台风格样张（静态），全部填入真实数据，供用户挑选。"""
import sqlite3, os, html

OUT = os.path.dirname(os.path.abspath(__file__))
c = sqlite3.connect(os.path.join(OUT, '..', '..', '..', 'backend', 'yuejiao.db'))
c.row_factory = sqlite3.Row

TABLES = [
    ('crm_lead', '客户线索', '◎', 12), ('sys_user', '用户账号', '◇', 15),
    ('student_admin_service', '行政服务', '▣', 14), ('student_psych_profile', '心理画像', '◈', 2),
    ('student_psych_alert', '心理预警', '△', 4), ('student_feedback_ticket', '反馈工单', '✉', 5),
    ('employee_daily_report', '员工日报', '▤', 8), ('student_score', '学生成绩', '▥', 27),
    ('course_project', '课程项目', '▦', 8), ('event_lecture', '讲座活动', '◉', 6),
    ('event_registration', '活动报名', '⊕', 7), ('conversation_log', '对话记录', '≡', 73),
]
STATS = [('12', '在跟线索', 'LEADS'), ('7', '待审批假条', 'PENDING'),
         ('4', '未处理预警', 'ALERTS'), ('73', '今日对话', 'CHATS')]
ROWS = [dict(r) for r in c.execute('select * from crm_lead order by id limit 7')]
c.close()

STATUS_CLS = {'跟进中': 'w', '新增意向': 'n', '已签约': 'o', '已报名': 'o',
              '待审批': 'w', '未处理': 'b', '高': 'b', '中': 'w', '已通过': 'o', '正常': 'o'}


def side():
    out = []
    for i, (name, label, icon, cnt) in enumerate(TABLES):
        on = ' on' if i == 0 else ''
        out.append(f'<button class="{on.strip()}"><span class="ic">{icon}</span><span class="lb">{label}</span><span class="n">{cnt}</span></button>')
    return ''.join(out)


def rows_html():
    out = []
    for r in ROWS:
        st = r['status']
        pill = f'<span class="pill {STATUS_CLS.get(st, "")}">{st}</span>'
        bg = (r['background_info'] or '')[:40]
        fu = (r['follow_up_history'] or '')[:34]
        out.append(
            f'<tr><td class="id">{r["id"]}</td><td class="nm">{r["customer_name"]}</td>'
            f'<td class="mono">{r["contact_info"]}</td><td class="txt">{html.escape(bg)}</td>'
            f'<td class="txt dim">{html.escape(fu)}</td><td>{pill}</td>'
            f'<td class="mono dim">{r["owner_employee_id"]}</td>'
            f'<td class="mono dim">{r["create_time"][:16]}</td></tr>')
    return ''.join(out)


def overview():
    return ''.join(
        f'<div class="ov"><div class="ovv">{v}</div><div class="ovk">{k}</div><div class="ove">{e}</div></div>'
        for v, k, e in STATS)


TPL = '''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<title>数据后台 · {name}</title><style>
:root{{{vars}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--tx);font-family:{font};font-size:13px;-webkit-font-smoothing:antialiased}}
.mono{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}}
.top{{height:{topH}px;display:flex;align-items:center;gap:14px;padding:0 26px;background:var(--top);border-bottom:1px solid var(--bd);position:sticky;top:0;z-index:5}}
.logo{{width:30px;height:30px;background:var(--ac);color:var(--onac);display:grid;place-items:center;font-weight:800;border-radius:{radius}}}.top h1{{font-size:15px;margin:0;font-weight:700;letter-spacing:.3px}}
.tag{{font-size:10px;padding:3px 9px;background:var(--soft);color:var(--ac);border-radius:{radius};font-family:ui-monospace,monospace;letter-spacing:.1em}}
.spacer{{flex:1}}.who{{font-size:12px;color:var(--mut)}}.top a,.top button{{font:inherit;font-size:12px;color:var(--mut);border:1px solid var(--bd);background:var(--panel);padding:6px 13px;border-radius:{radius};text-decoration:none;cursor:pointer}}
.wrap{{display:grid;grid-template-columns:236px 1fr;gap:16px;padding:16px 22px;align-items:start}}
.side{{background:var(--panel);border:1px solid var(--bd);border-radius:{radius};padding:10px;position:sticky;top:{topH2}px}}
.side .st{{font-family:ui-monospace,monospace;font-size:10px;letter-spacing:.16em;color:var(--mut);padding:8px 10px 10px}}
.side button{{width:100%;display:flex;align-items:center;gap:10px;font:inherit;text-align:left;border:0;background:transparent;padding:{sidePad} 10px;border-radius:{radius};color:var(--tx);cursor:pointer}}
.side button:hover{{background:var(--hover)}}.side button.on{{background:var(--soft);color:var(--ac);font-weight:700}}
.side .ic{{width:16px;text-align:center;font-size:13px;opacity:.8}}.side .lb{{flex:1}}.side .n{{font-family:ui-monospace,monospace;font-size:11px;color:var(--mut)}}
.side button.on .n{{color:var(--ac)}}
.main{{min-width:0;background:var(--panel);border:1px solid var(--bd);border-radius:{radius};overflow:hidden}}
.ovs{{display:grid;grid-template-columns:repeat(4,1fr);border-bottom:1px solid var(--bd)}}
.ov{{padding:{ovPad} 22px;border-right:1px solid var(--bd)}}.ov:last-child{{border-right:0}}
.ovv{{font-family:ui-monospace,monospace;font-size:{ovSize}px;font-weight:700;line-height:1;color:var(--ac);letter-spacing:-.03em}}
.ovk{{font-size:12px;color:var(--tx);margin-top:9px;font-weight:600}}
.ove{{font-family:ui-monospace,monospace;font-size:9px;letter-spacing:.15em;color:var(--mut);margin-top:5px}}
.head{{display:flex;align-items:center;gap:12px;padding:13px 18px;border-bottom:1px solid var(--bd)}}
.head h2{{font-size:15px;margin:0;font-weight:700}}.head .count{{font-size:11px;color:var(--mut)}}
.search{{display:flex;align-items:center;gap:8px;border:1px solid var(--bd);background:var(--input);border-radius:{radius};padding:0 11px;height:32px}}
.search input{{border:0;background:transparent;outline:0;font:inherit;width:190px;color:var(--tx)}}.search button{{border:0;background:transparent;color:var(--mut);font:inherit;cursor:pointer}}
.tb{{overflow:auto;max-height:520px}}table{{width:100%;border-collapse:collapse;font-size:12.5px}}
thead th{{position:sticky;top:0;background:var(--th);z-index:1;text-align:left;font-weight:600;color:var(--mut);padding:10px 14px;border-bottom:1px solid var(--bd);white-space:nowrap;font-family:ui-monospace,monospace;font-size:10px;letter-spacing:.08em}}
tbody td{{padding:10px 14px;border-bottom:1px solid var(--rowbd);vertical-align:middle}}
tbody tr:hover{{background:var(--hover)}}td.id{{font-family:ui-monospace,monospace;color:var(--mut)}}td.nm{{font-weight:700}}
td.txt{{max-width:230px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--tx)}}td.dim{{color:var(--mut)}}
.pill{{display:inline-block;padding:2px 9px;font-size:11px;border-radius:{pillR};background:var(--pilln);color:var(--pillnc);white-space:nowrap}}
.pill.w{{background:var(--pillw);color:var(--pillwc)}}.pill.o{{background:var(--pillo);color:var(--pilloc)}}.pill.b{{background:var(--pillb);color:var(--pillbc)}}
.pager{{display:flex;align-items:center;gap:10px;padding:12px 18px;border-top:1px solid var(--bd);font-size:11px;color:var(--mut)}}
.pager button{{font:inherit;font-size:12px;padding:5px 13px;border:1px solid var(--bd);background:var(--panel);color:var(--tx);border-radius:{radius};cursor:pointer}}
.crumb{{font-family:ui-monospace,monospace;font-size:10px;letter-spacing:.14em;color:var(--mut);padding:0 0 0 2px}}
{css}
</style></head><body>
<div class="top"><div class="logo">粤</div><h1>粤教服务 · 数据后台</h1><span class="tag">READ ONLY</span>
<div class="spacer"></div><span class="who">管理员 · 系统运维</span><a href="#">返回工作台</a><button>退出</button></div>
<div class="wrap">
<aside class="side"><div class="st">DATA TABLES / 数据表</div>{side}</aside>
<section class="main">
<div class="ovs">{ov}</div>
<div class="head"><div><div class="crumb">TABLE / 01</div><h2>客户线索</h2></div><span class="count">共 12 行</span>
<div class="spacer"></div><form class="search"><input placeholder="关键字，逗号分隔多个词"><button>搜索</button></form></div>
<div class="tb"><table><thead><tr><th>ID</th><th>客户姓名</th><th>联系方式</th><th>背景信息</th><th>跟进记录</th><th>状态</th><th>负责人</th><th>创建时间</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<div class="pager"><span>第 1 / 1 页 · 每页 20 行</span><div class="spacer"></div><button>上一页</button><button>下一页</button></div>
</section></div></body></html>'''

STYLES = {
 'A': dict(name='浅色工业风（同主页）', font='-apple-system,"PingFang SC","Microsoft YaHei",sans-serif',
   vars='--bg:#f5f7fa;--top:#fff;--panel:#fff;--tx:#141b2d;--mut:#7a8496;--bd:#dde3ec;--ac:#2563eb;--onac:#fff;--soft:#eaf1ff;--hover:#f5f8ff;--input:#f7f9fc;--th:#fff;--rowbd:#eef1f6;--pilln:#f0f2f6;--pillnc:#5d6779;--pillw:#fff5e6;--pillwc:#a35d00;--pillo:#eaf7ee;--pilloc:#1a7a44;--pillb:#fdecec;--pillbc:#b53232',
   radius='0', topH='62', topH2='78', sidePad='10', ovPad='22', ovSize='38', pillR='0', css=''),
 'B': dict(name='深色数据控制台', font='-apple-system,"PingFang SC","Microsoft YaHei",sans-serif',
   vars='--bg:#0b1020;--top:#101830;--panel:#111a30;--tx:#e6ecf7;--mut:#7f8bab;--bd:#253356;--ac:#4ea8ff;--onac:#06101f;--soft:#16264a;--hover:#16224a;--input:#0d1529;--th:#111a30;--rowbd:#1c2947;--pilln:#1b2742;--pillnc:#9fb0d4;--pillw:#3a2f12;--pillwc:#ffc861;--pillo:#153a2c;--pilloc:#5be0a0;--pillb:#3d1c26;--pillbc:#ff7a90',
   radius='8', topH='62', topH2='78', sidePad='9', ovPad='22', ovSize='40', pillR='5', css='body{background:radial-gradient(1200px 500px at 80% -10%,rgba(78,168,255,.08),transparent),#0b1020}.ovv{text-shadow:0 0 22px rgba(78,168,255,.4)}'),
 'C': dict(name='卡片仪表盘（SaaS）', font='-apple-system,"PingFang SC","Microsoft YaHei",sans-serif',
   vars='--bg:#f1f4f9;--top:#fff;--panel:#fff;--tx:#1c2740;--mut:#8a93a6;--bd:#e7ebf2;--ac:#5b6ef5;--onac:#fff;--soft:#eef0ff;--hover:#f7f8ff;--input:#f5f7fb;--th:#fafbfe;--rowbd:#f0f2f7;--pilln:#f0f2f7;--pillnc:#5d6779;--pillw:#fff4e2;--pillwc:#b97400;--pillo:#e9f8f0;--pilloc:#1a8a50;--pillb:#fdecec;--pillbc:#c23b3b',
   radius='12', topH='64', topH2='80', sidePad='10', ovPad='20', ovSize='34', pillR='999', css='.main{border-radius:14px}.ovs{gap:0}.ov{margin:14px 0;border-right:1px solid var(--bd)}.ovv{color:#2b3550}'),
 'D': dict(name='档案细线风', font='Georgia,"Songti SC","SimSun",serif',
   vars='--bg:#faf9f5;--top:#fff;--panel:#fff;--tx:#23201b;--mut:#948d7e;--bd:#ded8c9;--ac:#9a3b2f;--onac:#fff;--soft:#f4ede4;--hover:#faf6ee;--input:#faf7f0;--th:#fff;--rowbd:#ece6d9;--pilln:#f2eee5;--pillnc:#6d6455;--pillw:#f6ead4;--pillwc:#96601a;--pillo:#e6efe2;--pilloc:#3f6b3a;--pillb:#f3e0de;--pillbc:#9a3b2f',
   radius='0', topH='60', topH2='76', sidePad='11', ovPad='24', ovSize='42', pillR='0', css='.top h1,.head h2{font-family:Georgia,"Songti SC",serif;letter-spacing:.04em}.ovv{font-family:Georgia,serif;color:#23201b}.crumb,.tag,.ove,.ove,.st{letter-spacing:.2em}'),
}

for k, st in STYLES.items():
    out = TPL.format(name=st['name'], font=st['font'], vars=st['vars'], radius=st['radius'],
        topH=st['topH'], topH2=st['topH2'], sidePad=st['sidePad'], ovPad=st['ovPad'],
        ovSize=st['ovSize'], pillR=st['pillR'], css=st['css'],
        side=side(), ov=overview(), rows=rows_html())
    path = os.path.join(OUT, 'style_%s.html' % k)
    open(path, 'w', encoding='utf-8').write(out)
    print(k, st['name'], len(out))
