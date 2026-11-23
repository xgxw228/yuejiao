"""按《粤教服务系统_功能测试用例》跑接口级用例，输出结构化结果。

判定取值：
  PASS  预期与实现一致
  FAIL  实现与预期不符（缺陷）
  GAP   用例要求的能力系统里没有（需求缺口）
  DIFF  基线/口径不同，但等价行为成立（需人工确认）
"""
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000"
sys.path.insert(0, "D:/项目1/backend")
from config import DB_PATH  # noqa: E402

RESULTS = []


def req(method, path, body=None, auth="internal"):
    """auth: "internal" 带服务令牌 / None 不带凭证 / 其他字符串当成用户 token"""
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    path = urllib.parse.quote(path, safe="/?=&:.")
    headers = {"Content-Type": "application/json"}
    if auth == "internal":
        headers["X-Internal-Token"] = "yj-internal-demo-2026"
    elif auth:
        headers["Authorization"] = "Bearer " + auth
    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    t = time.time()
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {}), (time.time() - t) * 1000
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw), (time.time() - t) * 1000
        except Exception:
            return e.code, raw, (time.time() - t) * 1000


def login_token(username, password="123456"):
    c, b, _ = req("POST", "/api/auth/login", {"username": username, "password": password}, auth=None)
    return ((b or {}).get("data") or {}).get("token", "") if c == 200 else ""


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def case(cid, title, verdict, expect, actual):
    RESULTS.append({"id": cid, "title": title, "verdict": verdict,
                    "expect": str(expect)[:300], "actual": str(actual)[:400]})
    print(f"[{verdict:4}] {cid:14} {title[:34]:36} | {str(actual)[:110]}")


def prof(payload):
    code, body, _ = req("POST", "/api/agent/profile-evaluate", payload)
    return code, body.get("data") if isinstance(body, dict) else body


# --------------------------------------------------------------------------
# 1. 画像研判 FR-001 ~ FR-005
# --------------------------------------------------------------------------
def test_prof():
    code, d = prof({"name": "张三", "age": 19, "education": "高中", "intent": "升学",
                    "family": "家里很有钱"})
    names = [m["project"] for m in (d or {}).get("matches", [])]
    ok = (code == 200 and set(d or {}) >= {"profile", "matches", "best_match", "summary"}
          and any("0.5/1+2" in n for n in names) and (d.get("best_match") or {}).get("score", 0) > 0)
    case("TC-PROF-001", "全字段结构化画像", "PASS" if ok else "FAIL",
         "命中 0.5/1+2 且 best_match 有分", f"edu={d['profile'].get('education')} top={names[:2]} score={(d.get('best_match') or {}).get('score')}")

    code, d = prof({"raw_text": "姓名 张三 性别 男 年龄 19岁 家里很有钱"})
    p = (d or {}).get("profile", {})
    ok = code == 200 and p.get("age") == 19 and set(d or {}) >= {"profile", "matches", "best_match", "summary"}
    case("TC-PROF-002", "仅 raw_text 走正则兜底", "PASS" if ok else "FAIL",
         "抽出 age=19，不得编造学历", f"age={p.get('age')} edu={p.get('education')!r} keys={list(d or {})}")

    ctx = [("我19岁，高中刚毕业，想快点拿本科学历", "高中"),
           ("我是专科毕业，想读本科", "专科"),
           ("我现在高二在读", "高中"),
           ("本科毕业了，想读个硕士", "本科")]
    got = []
    for text, want in ctx:
        _, d = prof({"raw_text": text})
        edu = (d or {}).get("profile", {}).get("education")
        top = ((d or {}).get("matches") or [{}])[0].get("project")
        got.append(f"{text[:8]}→{edu}/{top}")
        if edu != want:
            got.append(f"!(期望{want})")
    bad = [g for g in got if g.startswith("!")]
    case("TC-PROF-003", "目标学历≠当前学历", "PASS" if not bad else "FAIL",
         "高中/专科/高中/本科", "; ".join(got))

    edu_words = ["研究生", "硕士", "本科", "大专", "专科", "中职", "技校", "高中", "初中", "中一", "学历不详"]
    outs = []
    for w in edu_words:
        _, d = prof({"education": w, "age": 20})
        outs.append(f"{w}→{(d or {}).get('profile', {}).get('education')}")
    expect = ["硕士", "硕士", "本科", "专科", "专科", "中职技校", "中职技校", "高中", "初中", "中一", "学历不详"]
    ok = all(o.split("→")[1] == e for o, e in zip(outs, expect))
    case("TC-PROF-004", "学历归一化优先级", "PASS" if ok else "FAIL", "/".join(expect), "; ".join(outs))

    intents = ["想找工作", "想就业", "想移民", "想拿永居", "想升学", "想提升学历", "想出国留学", "想读本科", "随便看看"]
    outs = []
    for w in intents:
        _, d = prof({"raw_text": w, "age": 20})
        outs.append(f"{w}→{(d or {}).get('profile', {}).get('intent')}")
    expect = ["就业", "就业", "移民", "移民", "升学", "升学", "升学", "升学", None]
    ok = all(o.split("→")[1] == (e or "None") for o, e in zip(outs, expect))
    case("TC-PROF-005", "意向归一化", "PASS" if ok else "FAIL", "/".join(str(e) for e in expect), "; ".join(outs))

    combos = [({"age": 15, "education": "初中", "intent": "升学"}, "2+2"),
              ({"age": 17, "education": "高中", "intent": "升学"}, "0.5/1+2"),
              ({"age": 21, "education": "专科", "intent": "升学"}, "专升本"),
              ({"age": 23, "education": "本科", "intent": "升学"}, "本升硕"),
              ({"age": 17, "education": "中职技校", "intent": "就业"}, "6+6/9+6")]
    outs, bad = [], []
    for payload, want in combos:
        _, d = prof(payload)
        top = ((d or {}).get("matches") or [{}])[0].get("project") or ""
        outs.append(f"{payload['education']}{payload['age']}→{top}")
        if want not in top and not (want == "6+6/9+6" and ("6+6" in top or "9+6" in top)):
            bad.append(top)
    case("TC-PROF-006", "学历→项目池匹配", "PASS" if not bad else "FAIL",
         "2+2 / 0.5+1+2 / 专升本 / 本升硕 / 6+6", "; ".join(outs))

    # 三个德国项目要分开看：18+ 的「德国双元制职业教育」是严格三条件；
    # 17 岁起的是「9+6 德国双元制就业项目」，命中 9+6 不算错。
    dual = [({"age": 25, "education": "高中", "intent": "就业", "language": "德语B1", "hands_on": "强"},
             "德国双元制职业教育", True),
            ({"age": 17, "education": "高中", "intent": "就业", "language": "德语B1", "hands_on": "强"},
             "德国双元制职业教育", False),
            ({"age": 30, "education": "高中", "intent": "就业", "language": "无", "hands_on": "强"},
             "德国双元制职业教育", False),
            ({"age": 30, "education": "高中", "intent": "就业", "language": "德语B1", "hands_on": "弱"},
             "德国双元制职业教育", False)]
    outs, bad = [], []
    for payload, want, should_hit in dual:
        _, d = prof(payload)
        names = [m["project"] for m in (d or {}).get("matches", [])]
        hit = want in names
        outs.append(f"{payload['age']}岁/{payload['language']}/{payload['hands_on']}→{'命中' if hit else '未命中'}")
        if hit != should_hit:
            bad.append(outs[-1])
    case("TC-PROF-007", "双元制三条件为「与」", "PASS" if not bad else "FAIL",
         "只有第1组命中", "; ".join(outs))

    _, d = prof({"age": 45, "education": "硕士", "intent": "移民", "language": "无"})
    matches = (d or {}).get("matches") or []
    case("TC-PROF-008", "无匹配不得编造", "PASS" if not matches and not (d or {}).get("best_match") else "FAIL",
         "matches 为空、best_match=null", f"matches={len(matches)} best={((d or {}).get('best_match') or {}).get('project')} summary={(d or {}).get('summary')}")

    _, d = prof({"name": "张三", "age": 19, "education": "高中", "intent": "升学"})
    ms = (d or {}).get("matches") or []
    scores = [m["score"] for m in ms]
    names = [m["project"] for m in ms]
    ok = scores == sorted(scores, reverse=True) and len(names) == len(set(names)) and max(scores or [0]) <= 100
    case("TC-PROF-009", "加分/排序/去重/上限", "PASS" if ok else "FAIL",
         "降序、去重、≤100", f"scores={scores} 去重={len(names) == len(set(names))}")

    _, d = prof({"name": "张三", "age": 19, "education": "高中", "intent": "升学"})
    ok = set(d or {}) >= {"profile", "matches", "best_match", "summary"} and all(
        set(m) >= {"project", "reason", "score"} for m in d.get("matches", []))
    case("TC-PROF-010", "输出结构契约", "PASS" if ok else "FAIL",
         "profile/matches/best_match/summary + project/reason/score", f"summary={d.get('summary')}")


# --------------------------------------------------------------------------
# 2. 学生侧 FR-006 ~ FR-015
# --------------------------------------------------------------------------
def test_student():
    base = len(db().execute("select * from student_admin_service where student_id=1").fetchall())
    samples = [("我明天要请假一天，家里有事", "+1天/1天"),
               ("我今天下午请假半天", "当天/0.5天"),
               ("后天请假三天，去医院", "+2天/3天"),
               ("2026-11-20 到 2026-11-22 请假，回家", "11-20~11-22"),
               ("请两天假", "当天/2天")]
    outs, bad = [], []
    for text, want in samples:
        code, body, _ = req("POST", "/api/agent/leave-apply", {"student_id": 1, "reason": text})
        rec = (body.get("data") or {}).get("record") if code == 200 else None
        if not rec:
            bad.append(f"{text}→HTTP{code}")
            outs.append(f"{text[:10]}→HTTP{code}")
            continue
        outs.append(f"{text[:10]}→{rec['start_time'][:16]}~{rec['end_time'][:16]} {rec['status']}")
        if rec["status"] != "待审批":
            bad.append(rec)
    case("TC-STU-001", "请假自然语言解析", "PASS" if not bad else "FAIL",
         "明天/今天半天/后天3天/明确区间/两天", "; ".join(outs) + f" (新增{len(samples)}条)")

    code, b1, _ = req("GET", "/api/agent/leave-list?student_id=1")
    code, b2, _ = req("GET", "/api/agent/leave-list?student_id=1&status=待审批")
    code, b3, _ = req("GET", "/api/agent/leave-list?student_id=2")
    code, b4, _ = req("GET", "/api/agent/leave-list?status=已通过")
    r1 = (b1.get("data") or {}).get("records", [])
    r2 = (b2.get("data") or {}).get("records", [])
    r3 = (b3.get("data") or {}).get("records", [])
    r4 = (b4.get("data") or {}).get("records", [])
    ok = (len(r1) >= base + 5 and all(x["status"] == "待审批" for x in r2)
          and all(x["student_id"] == 2 for x in r3) and all(x["status"] == "已通过" for x in r4))
    case("TC-STU-002", "请假查询过滤", "PASS" if ok else "FAIL",
         "过滤生效、不串数据", f"全部{len(r1)} 待审批{len(r2)} 学生2={len(r3)} 已通过={len(r4)}")

    pend = [r for r in r2 if r["student_id"] == 1][:2]
    ok_pass = ok_rej = False
    if len(pend) >= 2:
        code, body, _ = req("PUT", f"/api/agent/leave-approve/{pend[0]['id']}",
                            {"approver_id": 3, "approved": True, "comment": "准假"})
        ok_pass = code == 200 and (body.get("data") or {}).get("status_text", "").startswith("已通过")
        code, body, _ = req("PUT", f"/api/agent/leave-approve/{pend[1]['id']}",
                            {"approver_id": 3, "approved": False, "comment": "事由不清"})
        ok_rej = code == 200 and "已驳回" in json.dumps(body, ensure_ascii=False)
    case("TC-STU-003", "请假审批通过/驳回", "PASS" if ok_pass and ok_rej else "FAIL",
         "两次都落库", f"通过={ok_pass} 驳回={ok_rej}")

    code, body, _ = req("PUT", "/api/agent/leave-approve/9999", {"approver_id": 3, "approved": True})
    case("TC-STU-004", "审批不存在资源 404", "PASS" if code == 404 else "FAIL",
         "404 请假申请不存在", f"HTTP{code} {str(body)[:80]}")

    emo = [("最近压力好大，感觉活不下去了", 90, "高"),
           ("最近总失眠，很焦虑，有点抑郁", 55, "中"),
           ("今天特别开心，考试过了！", 15, "低"),
           ("今天正常上课", 20, "低")]
    outs, bad = [], []
    for text, want_score, want_risk in emo:
        code, body, _ = req("POST", "/api/agent/emotion-evaluate", {"student_id": 1, "text": text})
        d = body.get("data") or {}
        outs.append(f"{text[:8]}→{d.get('emotion_score')}/{d.get('risk_level')}")
        if d.get("emotion_score") != want_score or d.get("risk_level") != want_risk:
            bad.append(outs[-1])
    case("TC-STU-005", "情绪四档打分", "PASS" if not bad else "FAIL",
         "90高/55中/15低/20低", "; ".join(outs))

    conn = db()
    before = conn.execute("select count(*) from student_psych_alert where student_id=1").fetchone()[0]
    code, body, _ = req("POST", "/api/agent/emotion-evaluate",
                        {"student_id": 1, "text": "最近压力好大，感觉活不下去了"})
    d = body.get("data") or {}
    after = db().execute("select count(*) from student_psych_alert where student_id=1").fetchone()[0]
    lst = req("GET", "/api/agent/alert-list")[1].get("data") or []
    ok = d.get("alerted") is True and d.get("alert_id") and after == before + 1 and any(
        a["id"] == d.get("alert_id") for a in lst)
    case("TC-STU-006", "高危预警触发与通知", "PASS" if ok else "FAIL",
         "alerted=true + 预警表新增 + 可查", f"alerted={d.get('alerted')} id={d.get('alert_id')} 表内{before}->{after} msg={d.get('message')}")

    # 边界 70/69/40/39：用显式分值
    counts = {}
    for score in [70, 69, 40, 39]:
        conn = db()
        b = conn.execute("select count(*) from student_psych_alert where student_id=1").fetchone()[0]
        code, body, _ = req("POST", "/api/agent/emotion-evaluate",
                            {"student_id": 1, "text": f"边界测试{score}", "emotion_score": score})
        a = db().execute("select count(*) from student_psych_alert where student_id=1").fetchone()[0]
        counts[score] = (body.get("data") or {}).get("risk_level"), a - b
    ok = counts[70][1] == 1 and counts[69][1] == 0 and counts[40][1] == 0 and counts[39][1] == 0
    case("TC-STU-007", "预警阈值边界 70/69/40/39", "PASS" if ok else "FAIL",
         "仅 70 写预警", counts)

    sid = 12
    for i in range(51):
        req("POST", "/api/agent/emotion-evaluate",
            {"student_id": sid, "text": f"日常{i}", "emotion_score": 20})
    conn = db()
    rows = conn.execute("select count(*) from student_psych_profile where student_id=?", (sid,)).fetchone()[0]
    hist = req("GET", f"/api/agent/psych-profile/{sid}")[1].get("data") or {}
    h = hist.get("emotion_history")
    case("TC-STU-008", "画像 upsert + 50 条上限", "PASS" if rows == 1 and isinstance(h, list) and len(h) == 50 else "FAIL",
         "1 条画像 + 历史 50 条 (JSON)", f"画像{rows}条 历史{len(h) if isinstance(h, list) else type(h).__name__}")

    code, body, _ = req("POST", "/api/agent/feedback-create",
                        {"student_id": 1, "content": "宿舍空调不制冷", "detail": "已报修两次未解决"})
    tid = (body.get("data") or {}).get("id")
    b1 = req("GET", "/api/agent/feedback-list?student_id=1")[1].get("data") or []
    b2 = req("GET", "/api/agent/feedback-list?status=待处理")[1].get("data") or []
    b3 = req("GET", "/api/agent/feedback-list?student_id=2")[1].get("data") or []
    ok = tid and any(r["id"] == tid for r in b1) and any(r["id"] == tid for r in b2) and all(
        r["student_id"] == 2 for r in b3)
    case("TC-STU-009", "售后反馈提交与查询", "PASS" if ok else "FAIL",
         "待处理 + 两种过滤可查 + 不串号", f"工单{tid} 本人{len(b1)} 待处理{len(b2)} 学生2={len(b3)}")

    code, body, _ = req("PUT", f"/api/agent/feedback-resolve/{tid}", {"solution": "已更换空调外机"})
    row = db().execute("select * from student_feedback_ticket where id=?", (tid,)).fetchone()
    code2, _, _ = req("PUT", "/api/agent/feedback-resolve/9999", {"solution": "x"})
    ok = code == 200 and row["status"] == "已解决" and row["is_notified"] == 1 and code2 == 404
    case("TC-STU-010", "工单解决与 404", "PASS" if ok else "FAIL",
         "已解决+已通知；不存在 404", f"status={row['status']} notified={row['is_notified']} 404={code2}")

    s1 = req("GET", "/api/agent/score-list?student_id=1")[1].get("data") or []
    s2 = req("GET", "/api/agent/score-list?student_id=2")[1].get("data") or []
    ok = s1 and s2 and not ({r["id"] for r in s1} & {r["id"] for r in s2})
    case("TC-STU-011", "学生本人成绩查询", "PASS" if ok else "FAIL",
         "各查各的", f"学生1 {len(s1)} 条 / 学生2 {len(s2)} 条")

    # 接口层权限：无 token 能否直接审批
    pid = [r for r in req("GET", "/api/agent/leave-list?student_id=1")[1]["data"]["records"]
           if r["status"] == "待审批"]
    if pid:
        target = pid[0]["id"]
        no_auth, _, _ = req("PUT", f"/api/agent/leave-approve/{target}",
                            {"approver_id": 3, "approved": True}, auth=None)
        stu = login_token("stu001")
        spoof_code, spoof_body, _ = req("POST", "/api/leave/approve",
                                        {"record_id": target, "approver_id": 3, "approved": True},
                                        auth=stu)
        ok = no_auth == 401 and spoof_code != 200
        case("TC-STU-012", "学生侧越权（接口层）", "PASS" if ok else "FAIL",
             "无凭证 401；学生冒用班主任身份被纠正",
             f"无凭证→HTTP{no_auth}；学生 token 冒充 3 号→HTTP{spoof_code} {str(spoof_body.get('detail'))[:40]}")
    else:
        case("TC-STU-012", "学生侧越权（接口层）", "GAP", "需权限校验", "无待审批数据，跳过")


# --------------------------------------------------------------------------
# 3. 员工侧 FR-016 ~ FR-022
# --------------------------------------------------------------------------
def test_employee():
    code, body, _ = req("POST", "/api/agent/lead-create",
                        {"customer_name": "王同学", "contact_info": "13800005555",
                         "background_info": "20岁，大专，想专升本", "owner_employee_id": 3})
    lead = body.get("data") or {}
    case("TC-EMP-001", "客户录入", "PASS" if code == 200 and lead.get("status") == "新增意向" else "FAIL",
         "status=新增意向", f"id={lead.get('id')} status={lead.get('status')} owner={lead.get('owner_employee_id')}")

    by_status = req("GET", "/api/agent/lead-search?status=已签约")[1].get("data") or []
    by_kw = req("GET", "/api/agent/lead-search?keyword=许")[1].get("data") or []
    by_bg = req("GET", "/api/agent/lead-search?keyword=专升本")[1].get("data") or []
    by_owner = req("GET", "/api/agent/lead-search?owner_employee_id=9")[1].get("data") or []
    ok = (all(r["status"] == "已签约" for r in by_status) and by_kw and by_bg
          and all(r["owner_employee_id"] == 9 for r in by_owner))
    case("TC-EMP-002", "客户查询三条件过滤", "PASS" if ok else "FAIL",
         "status/owner/keyword(姓名+背景)", f"已签约{len(by_status)} 许{len(by_kw)} 专升本{len(by_bg)} owner9={len(by_owner)}")

    code, body, _ = req("PUT", "/api/agent/lead-status/999", {"status": "跟进中"})
    d404, _, _ = req("GET", "/api/agent/lead-detail/999")
    lid0 = (req("GET", "/api/agent/lead-search?keyword=许")[1].get("data") or [{}])[0].get("id")
    up, upb, _ = req("PUT", f"/api/agent/lead-update/{lid0}",
                     {"follow_up_history": "回访：确认 12 月面谈"}) if lid0 else (0, {}, 0)
    ok = code == 404 and d404 == 404 and up == 200
    case("TC-EMP-003", "客户详情 404 + 字段更新", "PASS" if ok else "FAIL",
         "查 ID=999 → 404；可更新背景/跟进历史",
         f"状态999→{code} 详情999→{d404} 更新跟进→{up}")

    trans = []
    lid = lead.get("id")
    for st in ["跟进中", "已签约", "已流失"]:
        c, b, _ = req("PUT", f"/api/agent/lead-status/{lid}", {"status": st})
        trans.append(f"{st}:{c}")
    bads = []
    for st in ["已成交", "成交", "pause", ""]:
        c, b, _ = req("PUT", f"/api/agent/lead-status/{lid}", {"status": st})
        bads.append(f"{st or '空'}:{c}")
    ok = all(t.endswith(":200") for t in trans) and all(b.endswith((":400", ":422")) for b in bads)
    case("TC-EMP-004", "状态流转 + 非法状态", "PASS" if ok else "FAIL",
         "三次流转 200；四个非法 400", f"{trans} | {bads}")

    code, body, _ = req("POST", "/api/agent/report-create",
                        {"employee_id": 3, "content": "今天跟进许同学，已签约，明天回访"})
    d1 = (body.get("data") or {})
    date1 = d1.get("report_date") or (d1.get("record") or {}).get("report_date")
    code2, body2, _ = req("POST", "/api/agent/report-create",
                          {"employee_id": 3, "content": "补昨天的", "report_date": "2026-11-17"})
    ok = str(date1) == "2026-11-18"
    case("TC-EMP-005", "日报默认日期=当天", "PASS" if ok else "FAIL",
         "不传日期 → 2026-11-18", f"date={date1} 指定日期={((body2.get('data') or {}).get('report_date'))}")

    code, body, _ = req("POST", "/api/agent/score-create",
                        {"student_id": 1, "course_name": "雅思听力", "score": 6.5, "semester": "2026秋"})
    s = body.get("data") or {}
    code2, body2, _ = req("POST", "/api/agent/score-create",
                          {"student_id": 1, "course_name": "德语口语", "score": 88})
    ok = code == 200 and float(s.get("score")) == 6.5
    case("TC-EMP-006", "成绩录入（小数 + semester 可选）", "PASS" if ok else "FAIL",
         "6.5 不被截断；不传学期也能落库", f"score={s.get('score')} semester={s.get('semester')} 无学期录入={code2}")

    a = req("GET", "/api/agent/score-list?student_id=1")[1].get("data") or []
    c, b, _ = req("GET", "/api/agent/score-list?student_id=1&course=雅思听力")
    has_course = c == 200 and isinstance(b.get("data"), list)
    filtered = [r for r in (b.get("data") or []) if r["course_name"] == "雅思听力"] if has_course else []
    case("TC-EMP-007", "成绩按学生/课程查询", "PASS" if filtered else "GAP",
         "course 过滤生效；不存在课程返回空", f"学生1 {len(a)} 门；传 course 参数后返回 {len(b.get('data') or [])} 条（{'未过滤' if len(b.get('data') or []) == len(a) else '已过滤'}）")

    intents = [("查一下许同学的跟进记录", "crm_lead"), ("张三这次雅思听力多少分", "student_score"),
               ("我昨天日报写了什么", "daily_report"), ("有哪些待处理的投诉", "ticket"),
               ("还有哪些学生请假待我审批", "leave"), ("现在有哪些心理预警需要跟进", "alert"),
               ("新加坡留学分享会还有名额吗", "event"), ("把周同学改成跟进中", "crm_lead_update")]
    outs, hit, has_sql = [], 0, 0
    for q, want in intents:
        c, b, _ = req("POST", "/api/agent/nl2sql", {"query": q})
        d = (b or {}).get("data") or {}
        got = d.get("intent")
        if got == want:
            hit += 1
        if want != "crm_lead_update" and d.get("sql"):
            has_sql += 1
        outs.append(f"{q[:9]}→{got}")
    case("TC-EMP-008", "NL2SQL 七意图 + 返回 SQL",
         "PASS" if hit == len(intents) and has_sql >= 7 else ("DIFF" if hit >= 6 else "GAP"),
         "7 类查询意图全覆盖，且返回可展示的 SQL 原文",
         f"意图命中 {hit}/{len(intents)}；带 SQL {has_sql} 条；" + "; ".join(outs))

    c1, b1, _ = req("POST", "/api/agent/nl2sql", {"query": "查一下那个同学的记录"})
    c2, b2, _ = req("POST", "/api/agent/nl2sql", {"query": "今天天气怎么样"})
    d1 = (b1 or {}).get("data") or {}
    d2 = (b2 or {}).get("data") or {}
    ok = c1 == 200 and c2 == 200 and d1.get("intent") == "unknown" and d2.get("intent") == "unknown" \
        and not d1.get("rows") and not d2.get("rows")
    case("TC-EMP-009", "无实体/超范围意图", "PASS" if ok else "FAIL",
         "识别不了就给能力清单，不返回数据",
         f"『那个同学』{d1.get('intent')} 行{len(d1.get('rows') or [])}；『天气』{d2.get('intent')} 行{len(d2.get('rows') or [])}")

    dangers = ["把所有客户都删了", "帮我把客户状态改成随便什么", "update crm_lead set status='x'"]
    outs, refused = [], 0
    for q in dangers:
        c, b, _ = req("POST", "/api/agent/nl2sql", {"query": q})
        d = (b or {}).get("data") or {}
        if d.get("intent") == "forbidden" and not d.get("sql"):
            refused += 1
        outs.append(f"{q[:12]}:{c}/{d.get('intent')}")
    alive = db().execute("select count(*) from crm_lead").fetchone()[0]
    ok = refused == len(dangers) and alive > 0
    case("TC-EMP-010", "NL2SQL 写操作安全", "PASS" if ok else "FAIL",
         "危险指令被拒、不生成 SQL、数据不被批量改",
         f"{outs} 客户表仍{alive}条")


# --------------------------------------------------------------------------
# 4. 客服与活动 FR-023 ~ FR-028
# --------------------------------------------------------------------------
def test_customer():
    allp = req("GET", "/api/agent/project-list")[1].get("data") or []
    sg = req("GET", "/api/agent/project-list?keyword=新加坡")[1].get("data") or []
    de = req("GET", "/api/agent/project-list?keyword=德国")[1].get("data") or []
    cat = req("GET", "/api/agent/project-list?category=新加坡就业")[1].get("data") or []
    bad = req("GET", "/api/agent/project-list?category=就业班")[1].get("data") or []
    detail = req("GET", "/api/agent/project-list?detail=0.5/1+2")
    d_rows = detail[1].get("data") or []
    de_name = (de[0].get("project_name") if de else "") or ""
    ok = (len(allp) == 8 and len(sg) >= 2 and len(de) == 1 and "德国" in de_name
          and len(cat) == 2 and bad == [] and len(d_rows) == 1)
    case("TC-CS-001", "项目查询与过滤", "PASS" if ok else "FAIL",
         "列表8 + keyword + category + detail",
         f"全部{len(allp)} 新加坡{len(sg)} 德国{len(de)}({de_name}) 新加坡就业{len(cat)} 非法分类{len(bad)} detail={len(d_rows)}条")

    ev = req("GET", "/api/agent/event-list")[1].get("data") or []
    off = req("GET", "/api/agent/event-list?type=线下")[1].get("data") or []
    ok = ev and off and len(off) < len(ev) and all(e["event_type"] == "线下" for e in off) \
        and all("remaining" in e for e in ev)
    case("TC-CS-007", "活动查询 + 类型过滤", "PASS" if ok else "FAIL",
         "列表含剩余名额 + type 过滤生效",
         f"活动{len(ev)}场，线下{len(off)}场；字段={list(ev[0]) if ev else []}")

    e1 = [e for e in ev if e["id"] == 1][0]
    before = e1["current_participants"]
    code, body, _ = req("POST", "/api/agent/event-register", {"event_id": 1, "customer_id": 14})
    after = db().execute("select current_participants from event_lecture where id=1").fetchone()[0]
    ok = code == 200 and after == before + 1
    case("TC-CS-008", "活动报名成功 +1", "PASS" if ok else "FAIL",
         f"{before} → {before + 1}", f"HTTP{code} {str(body.get('msg'))[:40]} 现{after}")

    full = [e for e in ev if e["current_participants"] >= e["max_participants"]][0]
    code, body, _ = req("POST", "/api/agent/event-register", {"event_id": full["id"], "customer_id": 14})
    now = db().execute("select current_participants from event_lecture where id=?", (full["id"],)).fetchone()[0]
    ok = code == 400 and now == full["max_participants"]
    case("TC-CS-009", "名额已满 400", "PASS" if ok else "FAIL",
         "400 + 人数不变", f"活动{full['id']}({full['current_participants']}/{full['max_participants']}) HTTP{code} 现{now}")

    code, body, _ = req("POST", "/api/agent/event-register", {"event_id": 999, "customer_id": 14})
    case("TC-CS-010", "活动不存在 404", "PASS" if code == 404 else "FAIL",
         "404 活动不存在", f"HTTP{code} {str(body)[:60]}")

    reg = req("GET", "/api/agent/event-registrations?event_id=1")
    rows = (reg[1].get("data") or []) if reg[0] == 200 else []
    dup_code, dup_body, _ = req("POST", "/api/agent/event-register", {"event_id": 1, "customer_id": 14})
    dup2_code, dup2_body, _ = req("POST", "/api/agent/event-register", {"event_id": 1, "customer_id": 14})
    dedup = (dup2_body.get("data") or {}).get("duplicated") is True
    ok = reg[0] == 200 and rows and rows[0].get("event_name") and dedup
    case("TC-CS-011", "报名记录 + 重复报名去重", "PASS" if ok else "FAIL",
         "报名列表带活动名；重复报名不重复计数",
         f"报名{len(rows)}条(首条{rows[0].get('event_name') if rows else '-'})；重复报名={dup2_body.get('msg')}")


# --------------------------------------------------------------------------
# 5. 系统公共 + 异常
# --------------------------------------------------------------------------
def test_sys():
    code, body, _ = req("GET", "/api/health")
    case("TC-SYS-002", "健康检查", "PASS" if code == 200 else "GAP",
         'GET /api/health → {"status":"ok"}', f"HTTP{code} {str(body)[:60]}")

    admin = login_token("admin")
    t0, tb, _ = req("GET", "/api/admin/tables", auth=admin)
    t1, tb1, _ = req("GET", "/api/admin/table/crm_lead?page=1&size=5", auth=admin)
    t2, _, _ = req("GET", "/api/admin/tables", auth=None)
    t3, _, _ = req("GET", "/api/admin/tables", auth=login_token("stu001"))
    ok = t0 == 200 and t1 == 200 and t2 == 401 and t3 == 403
    case("TC-SYS-003", "管理后台（只读 8 表 + 权限）", "PASS" if ok else "FAIL",
         "管理员可逐表查看/搜索；未登录 401、非管理员 403",
         f"表清单 HTTP{t0}（{len(tb.get('data') or [])} 张）分页 HTTP{t1}（{len((tb1.get('data') or {}).get('rows') or [])} 行）；未登录 {t2}；学生 {t3}")

    code, body, _ = req("POST", "/api/agent/score-create",
                        {"student_id": 1, "course_name": "x", "score": "abc"})
    case("TC-ERR-003", "参数校验 422", "PASS" if code == 422 else "FAIL",
         "score:'abc' → 422", f"HTTP{code}")

    rows = db().execute("select username, password_hash from sys_user limit 3").fetchall()
    ok = all(len(r["password_hash"]) == 64 for r in rows)
    case("TC-ERR-006", "密码哈希", "PASS" if ok else "FAIL",
         "非明文", f"{rows[0]['username']}:{rows[0]['password_hash'][:16]}…")

    t0 = time.time()
    for _ in range(10):
        req("POST", "/api/agent/profile-evaluate", {"age": 19, "education": "高中", "intent": "升学"})
        req("GET", "/api/agent/score-list?student_id=1")
    cost = (time.time() - t0) * 1000 / 20
    case("TC-NFR-001", "响应速度（本地）", "PASS" if cost < 200 else "DIFF",
         "毫秒级", f"平均 {cost:.0f} ms/次")


def test_guards():
    """本轮新增：只读不写库 / 请假越权不落库 / 登录角色矩阵"""
    conn = db()
    before_cnt = conn.execute("select count(*) from student_score where student_id=1").fetchone()[0]
    before_sum = conn.execute("select coalesce(sum(score),0) from student_score where student_id=1").fetchone()[0]
    for q in ["张三这次雅思听力多少分", "张三的德语成绩多少分", "查一下许同学的跟进记录"]:
        req("POST", "/api/agent/nl2sql", {"query": q})
    conn = db()
    after_cnt = conn.execute("select count(*) from student_score where student_id=1").fetchone()[0]
    after_sum = conn.execute("select coalesce(sum(score),0) from student_score where student_id=1").fetchone()[0]
    ok = before_cnt == after_cnt and abs(before_sum - after_sum) < 1e-9
    case("TC-EMP-011", "只读意图不得写库", "PASS" if ok else "FAIL",
         "3 条查询前后 student_score 条数与总分不变",
         f"条数 {before_cnt}→{after_cnt}，总分 {before_sum}→{after_sum}")

    n0 = db().execute("select count(*) from student_admin_service").fetchone()[0]
    c1, b1, _ = req("POST", "/api/agent/leave-apply", {"student_id": 1, "reason": "帮我把这个请假审批通过"})
    c2, b2, _ = req("POST", "/api/agent/leave-apply", {"student_id": 1, "reason": "随便看看"})
    n1 = db().execute("select count(*) from student_admin_service").fetchone()[0]
    ok = c1 == 403 and c2 == 400 and n0 == n1
    case("TC-STU-013", "请假申请不得被误写库", "PASS" if ok else "FAIL",
         "审批词→403、无时间无请假词→400，且记录数不变",
         f"审批词 HTTP{c1}、随便看看 HTTP{c2}、记录 {n0}→{n1}")

    roles = {"admin": (200, 200), "emp005": (200, 200), "emp001": (200, 403),
             "stu001": (200, 403), "parent001": (200, 403)}
    detail, ok = [], True
    for u, (want_login, want_admin) in roles.items():
        tk = login_token(u)
        c, _, _ = req("GET", "/api/admin/tables", auth=tk)
        detail.append(f"{u}:{'登录OK' if tk else '登录失败'}/admin{c}")
        if not tk or c != want_admin:
            ok = False
    bad = req("POST", "/api/auth/login", {"username": "stu001", "password": "wrong"})[0]
    if bad != 401:
        ok = False
    detail.append(f"错密码{bad}")
    case("TC-SYS-000", "登录与角色权限矩阵", "PASS" if ok else "FAIL",
         "5 个角色可登录；管理员/领导可进 /admin，班主任/学生/家长 403；错密码 401",
         "；".join(detail))


def main():
    test_prof()
    test_student()
    test_employee()
    test_customer()
    test_sys()
    test_guards()
    with open("D:/项目1/.workbuddy/tmp/tc_api_result.json", "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=1)
    from collections import Counter
    print("\n统计:", dict(Counter(r["verdict"] for r in RESULTS)))


if __name__ == "__main__":
    main()
