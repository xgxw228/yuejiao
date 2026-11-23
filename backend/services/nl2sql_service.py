"""NL2SQL：把员工的口语查询翻译成一条可执行的 SELECT，并把 SQL 原文回给上层。

为什么不接大模型做 Text2SQL：
1. 演示要可复现 —— 同一句话必须每次都命中同一个意图，不能靠采样；
2. 安全 —— 只生成 SELECT，且只允许白名单列与参数化占位符，避免「删库」类幻觉；
3. 便宜 —— 一次查询 0 token，额度留给对话。

覆盖需求 FR-022 的七类查询：
    客户档案 / 学生成绩 / 请假审批 / 员工日报 / 投诉工单 / 心理预警 / 活动报名
外加项目课程（项目清单本身在 course_project 表里，顺手支持）。

返回结构（给 Dify 的 LLM 节点消费）：
    {intent, intent_label, sql, params, count, columns, rows, summary, hint}
"""

import re
import sqlite3
from datetime import date, timedelta
from typing import Any, Optional

from services import leave_service

# ---------------------------------------------------------------------------
# 意图词表：权重越高越专有。命中总分最高者胜出，同分按此表顺序取先者。
# ---------------------------------------------------------------------------

INTENT_RULES: list[tuple[str, str, list[tuple[str, int]]]] = [
    ("daily_report", "员工日报", [("日报", 5), ("周报", 5), ("工作总结", 4), ("汇报", 2), ("工作日志", 3)]),
    ("alert", "心理预警", [("预警", 5), ("心理", 5), ("情绪", 3), ("危机", 3), ("重点关注", 3)]),
    ("ticket", "投诉工单", [("投诉", 5), ("工单", 5), ("售后", 4), ("退费", 4), ("不满意", 3), ("反馈", 2)]),
    ("leave", "请假审批", [("请假", 5), ("销假", 4), ("事假", 4), ("病假", 4), ("待批", 4), ("审批", 2)]),
    ("student_score", "学生成绩", [("成绩", 5), ("分数", 4), ("多少分", 4), ("平均分", 4), ("挂科", 4),
                                ("绩点", 4), ("不及格", 5), ("没及格", 5), ("总分", 4), ("排名", 4),
                                ("几门", 4), ("门课", 4), ("优秀", 2), ("补考", 3)]),
    ("event", "活动报名", [("活动", 4), ("讲座", 4), ("分享会", 4), ("说明会", 4), ("名额", 4), ("报名", 3), ("到场", 3)]),
    ("crm_lead", "客户档案", [("客户", 4), ("线索", 4), ("跟进", 4), ("意向", 3), ("签约", 3), ("转化", 3), ("档案", 2)]),
    ("project", "项目课程", [("项目", 2), ("课程", 2), ("学制", 3), ("专业", 2), ("学费", 2)]),
]

LEAD_STATUS = ["新增意向", "跟进中", "已签约", "已流失"]
LEAVE_STATUS = ["待审批", "已通过", "已驳回"]
TICKET_STATUS = ["待处理", "处理中", "已解决"]
ALERT_STATUS = ["未处理", "跟进中", "已解除"]
RISK_LEVELS = ["高", "中", "低"]
EVENT_TYPES = ["线上", "线下", "宣讲会", "分享会", "说明会", "体验课"]

WRITE_HINTS = ("改成", "改为", "设为", "标记为", "设为", "流转为", "更新为", "调成")
# 请假审批类写操作（"把张三的请假批了"），与"批了吗"这种查询要区分开
LEAVE_WRITE_HINTS = ("批了", "批一下", "批准", "通过一下", "驳回", "让老师批", "帮我批")

# 课程名不一定都在库里（例如"雅思听力"这门课还没录），
# 所以这里维护一份学科词表：认得出就按它过滤，查不到就老实说"没有这门课的成绩"。
SUBJECTS = ["雅思", "托福", "德语", "英语", "数学", "物理", "化学", "程序设计",
            "经济学", "统计学", "会计", "听力", "口语", "阅读", "写作"]
SKILLS = ["听力", "口语", "阅读", "写作", "语法", "词汇"]

# 「我班上」这类说法：只有班主任自己能这么问，管理员/领导才放开全校
SELF_CLASS_HINTS = ("我班上", "我带的", "我的学生", "我们班", "我班", "我带的学生", "我负责的")
FAIL_WORDS = ("不及格", "没及格", "未及格", "低于60", "低于 60", "不到60", "挂科", "补考")
EXCELLENT_WORDS = ("90分以上", "九十分以上", "优秀")
TOTAL_WORDS = ("总分", "合计", "加起来")
RANK_WORDS = ("排名", "排第几", "第几名")
DEPART_HINTS = ("新加坡", "德国", "港澳", "中德", "专升本", "本硕")


CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _top_n(query: str) -> Optional[int]:
    """把「前三」「前 5 名」「前三名」解析成 3 / 5。"""
    m = re.search(r"前\s*([一二三四五六七八九十]|\d{1,2})", query) or re.search(
        r"([一二三四五六七八九十]|\d{1,2})\s*名", query
    )
    if not m:
        return None
    raw = m.group(1)
    n = CN_NUM.get(raw) if raw in CN_NUM else (int(raw) if raw.isdigit() else None)
    return n if n and 0 < n <= 50 else None


def build_ctx(db: sqlite3.Connection, user_id: Optional[int]) -> dict:
    """把当前登录员工整理成查询上下文，供「我班上」这类身份相关过滤使用。"""
    if not user_id:
        return {}
    row = db.execute(
        "SELECT id, real_name, user_type, employee_role, department FROM sys_user WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        return {}
    ctx = dict(row)
    ctx["is_manager"] = ctx.get("employee_role") in ("管理员", "领导")
    # 只有员工才有「我班上」的语义；学生/家长 id 传进来时不能当作班主任 id 去过滤
    ctx["is_employee"] = ctx.get("user_type") == "EMPLOYEE"
    return ctx


def _course_hint(query: str) -> Optional[str]:
    for subj in SUBJECTS:
        if subj in query:
            idx = query.index(subj) + len(subj)
            tail = query[idx:idx + 2]
            return subj + (tail if tail in SKILLS else "")
    return None


RELATIVE = {
    "今天": 0, "今日": 0, "昨天": -1, "昨日": -1, "前天": -2,
    "本周": 0, "这周": 0, "上周": -7, "最近": -7, "近一周": -7,
}


def _detect_intent(query: str) -> tuple[Optional[str], str, int]:
    """返回 (intent, label, score)。"""
    scores: list[tuple[int, int, str, str]] = []
    for order, (intent, label, words) in enumerate(INTENT_RULES):
        score = sum(w for kw, w in words if kw in query)
        if score:
            scores.append((score, -order, intent, label))
    if not scores:
        return None, "", 0
    scores.sort(reverse=True)
    best = scores[0]
    return best[2], best[3], best[0]


def _pick(query: str, candidates: list[str]) -> Optional[str]:
    """在问题里找出现过的候选词（取最长匹配，避免「跟进」抢了「跟进中」）。"""
    hits = [c for c in candidates if c and c in query]
    return max(hits, key=len) if hits else None


def _person(db: sqlite3.Connection, query: str, user_type: str) -> Optional[dict]:
    """从问题里认出具体的人：优先取全名，取不到再退到「姓 + 同学/客户」。"""
    rows = db.execute(
        "SELECT id, real_name, user_type, department FROM sys_user WHERE user_type = ?",
        (user_type,),
    ).fetchall()
    hits = [r for r in rows if r["real_name"] and r["real_name"] in query]
    if hits:
        return dict(max(hits, key=lambda r: len(r["real_name"])))

    # 「许同学」「周同学」这种只给姓的说法
    m = re.search(r"([\u4e00-\u9fa5]{1,2})(?:同学|学生|客户|先生|女士)", query)
    if m:
        surname = m.group(1)[-1]
        for r in rows:
            if r["real_name"] and r["real_name"].startswith(surname):
                return dict(r)
    return None


def _lead_person(db: sqlite3.Connection, query: str) -> Optional[dict]:
    rows = db.execute("SELECT * FROM crm_lead").fetchall()
    hits = [r for r in rows if r["customer_name"] and r["customer_name"] in query]
    if hits:
        return dict(max(hits, key=lambda r: len(r["customer_name"])))
    m = re.search(r"([\u4e00-\u9fa5]{1,2})(?:同学|客户|先生|女士|家长)", query)
    if m:
        surname = m.group(1)[-1]
        for r in rows:
            if r["customer_name"] and r["customer_name"].startswith(surname):
                return dict(r)
    return None


def _date_window(query: str) -> Optional[tuple[str, str]]:
    for word, offset in RELATIVE.items():
        if word in query:
            if word in ("本周", "这周"):
                today = date.today()
                start = today - timedelta(days=today.weekday())
                return start.isoformat(), (start + timedelta(days=7)).isoformat()
            if offset < 0:
                return (date.today() + timedelta(days=offset)).isoformat(), (
                    date.today() + timedelta(days=offset + 1)
                ).isoformat()
            return date.today().isoformat(), (date.today() + timedelta(days=1)).isoformat()
    if "本月" in query or "这个月" in query:
        today = date.today()
        first = today.replace(day=1)
        nxt = (first + timedelta(days=32)).replace(day=1)
        return first.isoformat(), nxt.isoformat()
    return None


def _fmt(sql: str, params: list[Any]) -> str:
    """把参数化 SQL 还原成可直接阅读的一行（仅用于展示，执行仍走占位符）。"""
    out = sql
    for p in params:
        literal = f"'{p}'" if isinstance(p, str) else str(p)
        out = out.replace("?", literal, 1)
    return re.sub(r"\s+", " ", out).strip()


def _rows(db: sqlite3.Connection, sql: str, params: list[Any], limit: int = 20) -> list[dict]:
    cur = db.execute(sql + f" LIMIT {limit}", params)
    return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# 多轮指代消解
#
# 现场问题：员工刚说「给张三录入 Python 成绩 92 分」，紧接着问「这是哪个学期的成绩？」。
# 这句话里没有姓名、没有课程，只有「这」——实体全在上一轮。后端拿不到上文，
# 就退化成 WHERE 1=1，把整张成绩表 20 条倒出来，还附一句「涉及多个学期」。
# 处理办法：从上文里把实体捞回来，拼成「张三 Python 这是哪个学期的成绩」再解析。
# ---------------------------------------------------------------------------

# 出现这些词，说明是在指上一轮说过的东西
FOLLOWUP_PRONOUNS = ("这", "那", "它", "他", "她", "刚才", "刚刚", "上面", "上一条", "上次", "该", "此")
# 超过这个字数的问句一般自带信息，不再往上文里找
FOLLOWUP_MAX_LEN = 16
# 群体/筛选式问法：问的是「多少人」「谁」「全部」，这时不能把主语锁到上一个人身上。
# 「这门课我班上还有谁不及格」只需补出课程，补成「张三 Python 我班上…」会查成 0 条。
GROUP_HINTS = SELF_CLASS_HINTS + FAIL_WORDS + TOTAL_WORDS + RANK_WORDS + (
    "所有", "全部", "哪些", "谁", "名单", "各", "整体", "多少名",
)
# 「那李四呢」「换成王五」是新主语，人不能从上一轮继承（否则会答成上一个人的数据）；
# 但「这门课呢」仍要继承课程名，所以只掐掉人，不掐课程。
NO_PERSON_HINTS = GROUP_HINTS + ("呢", "换成", "改成", "改为")


def _has_entity(db: sqlite3.Connection, query: str) -> bool:
    """问句里是否已经带了具体的人/课/班级——带了就不用补全。"""
    if _person(db, query, "STUDENT") or _lead_person(db, query):
        return True
    courses = [r["course_name"] for r in db.execute("SELECT DISTINCT course_name FROM student_score")]
    if _pick(query, courses) or _course_hint(query):
        return True
    if any(h in query for h in DEPART_HINTS) or re.search(r"\d{4}\s*级", query):
        return True
    return False


def _is_followup(db: sqlite3.Connection, query: str) -> bool:
    """省略式追问：句子短、带指代词、自己又不带实体。"""
    if len(query) > FOLLOWUP_MAX_LEN:
        return False
    if _has_entity(db, query):
        return False
    return any(w in query for w in FOLLOWUP_PRONOUNS)


def _entities_from_history(db: sqlite3.Connection, history: str) -> dict:
    """从上文里捞最近提到的学生 / 客户 / 课程。

    排序用 (长度, 出现位置)：先取最长的那个名字，同长再取最后出现的。
    为什么长度优先——「高等数学」里含「数学」，两门课都在库里时，
    只看位置会把课程识别成「数学」（位置更靠后），然后 LIKE '%数学%' 查出别的课。
    """
    out: dict[str, Optional[str]] = {"student": None, "lead": None, "course": None}
    if not history:
        return out

    def pick(sql: str) -> Optional[str]:
        best_name, best_key = None, (0, -1)
        for r in db.execute(sql):
            name = r[0] or ""
            idx = history.rfind(name) if name else -1
            if idx < 0:
                continue
            key = (len(name), idx)
            if key > best_key:
                best_name, best_key = name, key
        return best_name

    out["student"] = pick("SELECT real_name FROM sys_user WHERE user_type = 'STUDENT'")
    out["lead"] = pick("SELECT customer_name FROM crm_lead")
    out["course"] = pick("SELECT DISTINCT course_name FROM student_score")
    return out


def _expand_followup(
    db: sqlite3.Connection, query: str, history: Optional[str]
) -> tuple[str, Optional[dict], bool]:
    """返回 (补全后的问句, 补到的实体, 是否属于追问)。

    补不到实体时原样返回，交给上层决定「反问」还是「照常查」。
    """
    if not _is_followup(db, query):
        return query, None, False
    if not history:
        # 第一句就是「这是哪个学期的成绩」：没有上文可补，但也不能倒全表，标记出来让上层反问
        return query, None, True

    ent = _entities_from_history(db, history)
    # 群体式 / 换主语的提问只补课程：「这门课我班上还有谁不及格」≠「张三这门课不及格」
    if any(h in query for h in NO_PERSON_HINTS):
        ent["student"] = None
        ent["lead"] = None
    bits = [ent["student"] or "", ent["course"] or "", ent["lead"] or ""]
    prefix = "".join(bits).strip()
    if not prefix:
        # 是追问，但上文里没有可用的实体 → 标记出来，别让 WHERE 1=1 倒全表
        return query, ent, True
    return f"{prefix} {query}", ent, True


# 「那李四呢」「换成王五」这类：实体换了，问的还是上一轮那件事。
# 这类句子自己不带意图词，单轮解析会得到「没听出要查哪类数据」。
INHERIT_HINTS = ("呢", "那", "换", "他", "她", "同样", "还是", "也")
# 明显是新话题/闲聊，别把上一轮的意图套上去
NO_INHERIT_WORDS = ("天气", "时间", "几号", "星期", "你好", "谢谢", "你是谁", "笑话", "叫什么")


def _last_question(history: str) -> str:
    """取上文里最后一次「问：」的那句，避免多轮意图互相污染。"""
    idx = history.rfind("问：")
    seg = history[idx + 2:] if idx >= 0 else history
    return seg.split("｜")[0]


def _inherit_intent(query: str, history: Optional[str]) -> tuple[Optional[str], str, int]:
    """本轮识别不出意图时，沿用上一轮问句的意图。"""
    if not history or len(query) > 12:
        return None, "", 0
    if any(w in query for w in NO_INHERIT_WORDS):
        return None, "", 0
    if not any(w in query for w in INHERIT_HINTS):
        return None, "", 0
    return _detect_intent(_last_question(history))


# ---------------------------------------------------------------------------
# 各意图的 SQL 生成
# ---------------------------------------------------------------------------

def _q_crm_lead(db: sqlite3.Connection, query: str) -> dict:
    sql = (
        "SELECT l.id, l.customer_name, l.contact_info, l.status, "
        "u.real_name AS owner, l.background_info, l.follow_up_history, l.update_time "
        "FROM crm_lead l LEFT JOIN sys_user u ON u.id = l.owner_employee_id WHERE 1=1"
    )
    params: list[Any] = []
    conds = []

    person = _lead_person(db, query)
    if person:
        conds.append("l.customer_name = ?")
        params.append(person["customer_name"])
    status = _pick(query, LEAD_STATUS)
    if status:
        conds.append("l.status = ?")
        params.append(status)
    if "本周" in query or "最近" in query:
        conds.append("l.update_time >= date('now', 'localtime', '-7 day')")
    if conds:
        sql += " AND " + " AND ".join(conds)
    sql += " ORDER BY l.id DESC"

    rows = _rows(db, sql, params)
    if person:
        summary = f"客户【{person['customer_name']}】共 {len(rows)} 条档案"
    elif status:
        summary = f"状态为【{status}】的客户 {len(rows)} 条"
    else:
        summary = f"共 {len(rows)} 条客户档案"
    return {
        "sql": _fmt(sql, params), "params": params, "rows": rows,
        "summary": summary,
        "hint": "逐条播报客户姓名、状态、负责人、最近一次跟进内容；查单人时把背景信息也说清。",
    }


def _q_student_score(db: sqlite3.Connection, query: str, ctx: Optional[dict] = None) -> dict:
    """成绩查询：支持人、课程、班级/方向、不及格、总分、平均分、排名。"""
    ctx = ctx or {}
    params: list[Any] = []
    conds: list[str] = []

    student = _person(db, query, "STUDENT")
    if student:
        conds.append("s.student_id = ?")
        params.append(student["id"])

    # 「我班上」：班主任只看自己名下学生，管理员/领导才放开全校
    scoped = any(h in query for h in SELF_CLASS_HINTS)
    if scoped and not ctx.get("is_manager"):
        if ctx.get("id") and ctx.get("is_employee", True):
            conds.append("s.student_id IN (SELECT id FROM sys_user WHERE homeroom_teacher_id = ?)")
            params.append(ctx["id"])
        else:
            # 没有班主任身份（未登录 / 学生身份）时，宁可直接说明，也别把全校成绩倒出来
            return {
                "sql": None, "params": [], "rows": [],
                "summary": "当前身份不是班主任，查不了「我班上」的成绩",
                "hint": "说明这个身份没有班级范围，请对方给出具体学生姓名或课程再查；不要罗列全校数据。",
                "broad": False,
                "keep_summary": True,
            }

    # 年级（2025级）或方向（新加坡/德国/港澳…）
    grade = re.search(r"(\d{4})\s*级", query)
    if grade:
        conds.append("u.department LIKE ?")
        params.append(f"%{grade.group(1)}级%")
    elif not student:
        for hint in DEPART_HINTS:
            if hint in query:
                conds.append("u.department LIKE ?")
                params.append(f"%{hint}%")
                break

    courses = [r["course_name"] for r in db.execute("SELECT DISTINCT course_name FROM student_score")]
    course = _pick(query, courses) or _course_hint(query)
    if course:
        conds.append("s.course_name LIKE ?")
        params.append(f"%{course}%")

    failed = any(w in query for w in FAIL_WORDS)
    if failed:
        # 雅思是 9 分制、托福 120 分制，不能拿 60 分当及格线
        conds.append(
            "((s.course_name LIKE '%雅思%' AND s.score < 6.0) "
            "OR (s.course_name LIKE '%托福%' AND s.score < 60) "
            "OR (s.course_name NOT LIKE '%雅思%' AND s.course_name NOT LIKE '%托福%' AND s.score < 60))"
        )
    if any(w in query for w in EXCELLENT_WORDS):
        conds.append("s.score >= 90")

    where = (" WHERE 1=1 AND " + " AND ".join(conds)) if conds else " WHERE 1=1"
    base = " FROM student_score s JOIN sys_user u ON u.id = s.student_id"

    want_total = any(w in query for w in TOTAL_WORDS)
    want_rank = any(w in query for w in RANK_WORDS)
    want_avg = ("平均" in query or "均分" in query) and not want_total and not want_rank

    if want_total or want_avg or want_rank:
        # 雅思/托福是另一套量纲（9 分制 / 120 分制），不能和百分制课程混算总分和平均分，
        # 否则「张三平均 61.8 分」这种明显错误的结论就会出现。
        standardized = ("雅思" in query) or ("托福" in query)
        agg_where = where
        if not standardized and not course:
            agg_where += " AND s.course_name NOT LIKE '%雅思%' AND s.course_name NOT LIKE '%托福%'"

        if want_total:
            select = ("SELECT u.real_name AS student_name, SUM(s.score) AS total, "
                      "COUNT(*) AS courses, ROUND(AVG(s.score), 1) AS avg_score")
            order, label = " ORDER BY total DESC", "总分"
        else:
            select = ("SELECT u.real_name AS student_name, ROUND(AVG(s.score), 1) AS avg_score, "
                      "COUNT(*) AS courses, ROUND(SUM(s.score), 1) AS total")
            order, label = " ORDER BY avg_score DESC", "平均分"

        # 「前三」「前 5 名」只取这么多人（_rows 会自己拼 LIMIT，这里不要重复拼）
        top_n = _top_n(query)
        sql = select + base + agg_where + " GROUP BY s.student_id" + order
        rows = _rows(db, sql, params, limit=top_n or 20)

        if len(rows) == 1:
            r = rows[0]
            if want_total:
                summary = (f"{r['student_name']}共 {r['courses']} 门课（不含雅思/托福），"
                           f"总分 {r['total']} 分，平均 {r['avg_score']} 分")
            else:
                summary = (f"{r['student_name']}共 {r['courses']} 门课（不含雅思/托福），"
                           f"平均 {r['avg_score']} 分")
        elif rows:
            key = "total" if want_total else "avg_score"
            shown = "、".join(f"{r['student_name']} {r[key]} 分" for r in rows[:3])
            summary = f"共 {len(rows)} 名学生，按{label}排序：{shown}"
        else:
            summary = f"没有查到符合条件的{label}"
        return {
            "sql": _fmt(sql, params), "params": params, "rows": rows,
            "summary": summary,
            "hint": (f"这是按学生汇总的{label}（已排除雅思/托福这类不同量纲的科目）。"
                     "一个人时直接报数值和门数；多人时按顺序列出前几名，不要念完整张表。"),
        }

    sql = ("SELECT s.id, u.real_name AS student_name, s.course_name, s.score, s.semester"
           + base + where + " ORDER BY s.id DESC")
    rows = _rows(db, sql, params)

    if student:
        who = student["real_name"]
    elif scoped and ctx.get("id") and not ctx.get("is_manager"):
        who = f"{ctx.get('real_name') or '您'}班上的学生"
    elif scoped:
        who = "全校学生"
    else:
        who = "全部学生"
    what = f"的{course}" if course else ""
    head = f"{who}{what}{'不及格' if failed else '成绩'}记录 {len(rows)} 条"

    if failed:
        people = len({r["student_name"] for r in rows})
        summary = f"{who}{what}不及格记录 {len(rows)} 条" + (f"，涉及 {people} 名学生" if rows else "")
    elif len(rows) == 1:
        r = rows[0]
        summary = f"{r['student_name']} {r['course_name']} {r['score']} 分"
    elif rows:
        # 明细里同时含百分制课程和雅思/托福时，平均分没有意义，不能给
        mixed = any(("雅思" in (r["course_name"] or "")) or ("托福" in (r["course_name"] or "")) for r in rows)
        if mixed:
            summary = f"{head}（含雅思/托福，不同量纲不计算平均分）"
        else:
            avg = round(sum(r["score"] for r in rows) / len(rows), 1)
            summary = f"{head}，平均 {avg} 分"
    else:
        summary = head

    if failed:
        hint = "逐条列出学生姓名、课程和分数，说明未达标；没有就直说这次没有不及格记录。"
    else:
        hint = "列出学生、课程与分数；只有 1 条就直接报分数，不要罗列无关课程。"
    return {
        "sql": _fmt(sql, params), "params": params, "rows": rows,
        "summary": summary, "hint": hint,
        # 无任何过滤条件 = 把整册倒出来。正常提问没问题（「查全部成绩」），
        # 但如果是「这是哪个学期的成绩」这种没补上实体的追问，上层要改成反问。
        "broad": not conds,
    }


def _q_leave(db: sqlite3.Connection, query: str) -> dict:
    sql = (
        "SELECT a.id, u.real_name AS student_name, a.service_type, a.start_time, a.end_time, "
        "a.reason, a.status, t.real_name AS approver_name "
        "FROM student_admin_service a JOIN sys_user u ON u.id = a.student_id "
        "LEFT JOIN sys_user t ON t.id = a.approver_id WHERE 1=1"
    )
    params: list[Any] = []
    conds = []

    student = _person(db, query, "STUDENT")
    if student:
        conds.append("a.student_id = ?")
        params.append(student["id"])
    status = _pick(query, LEAVE_STATUS)
    if status:
        conds.append("a.status = ?")
        params.append(status)
    if "审批" in query and not status:
        conds.append("a.status = '待审批'")
    if conds:
        sql += " AND " + " AND ".join(conds)
    sql += " ORDER BY a.id DESC"

    rows = [leave_service.enrich(db, r) for r in _rows(db, sql, params)]
    pending = sum(1 for r in rows if r["is_pending"])
    summary = f"请假记录 {len(rows)} 条"
    if pending:
        summary += f"，其中 {pending} 条待审批"
    return {
        "sql": _fmt(sql, params), "params": params, "rows": rows,
        "summary": summary,
        "hint": "每条说清学生、起止时间、状态（含审批人姓名）；不要只报数字。",
    }


def _q_daily_report(db: sqlite3.Connection, query: str, ctx: Optional[dict] = None) -> dict:
    sql = (
        "SELECT d.id, d.report_date, u.real_name AS employee_name, d.content, d.create_time "
        "FROM employee_daily_report d LEFT JOIN sys_user u ON u.id = d.employee_id WHERE 1=1"
    )
    params: list[Any] = []
    conds = []
    emp = _person(db, query, "EMPLOYEE")
    if not emp and ctx.get("id") and re.search(r"我的|我昨天|我今天|我这周|我上周|我最近|我写", query):
        # 「我昨天日报写了什么」指的是本人的日报，不该把全公司的都倒出来
        conds.append("d.employee_id = ?")
        params.append(ctx["id"])
        emp = {"real_name": ctx.get("real_name") or "本人"}
    elif emp:
        conds.append("d.employee_id = ?")
        params.append(emp["id"])
    window = _date_window(query)
    if window:
        conds.append("d.report_date >= ? AND d.report_date < ?")
        params += list(window)
    if conds:
        sql += " AND " + " AND ".join(conds)
    sql += " ORDER BY d.report_date DESC, d.id DESC"

    rows = _rows(db, sql, params)
    who = emp["real_name"] if emp else "全部员工"
    summary = f"{who}日报 {len(rows)} 篇"
    if window:
        summary += f"（{window[0]} 起）"
    return {
        "sql": _fmt(sql, params), "params": params, "rows": rows,
        "summary": summary,
        "hint": "按日期从新到旧复述日报要点，不要整段照抄。",
    }


def _q_ticket(db: sqlite3.Connection, query: str) -> dict:
    sql = (
        "SELECT f.id, u.real_name AS student_name, f.content, f.status, f.solution, f.create_time "
        "FROM student_feedback_ticket f LEFT JOIN sys_user u ON u.id = f.student_id WHERE 1=1"
    )
    params: list[Any] = []
    conds = []
    student = _person(db, query, "STUDENT")
    if student:
        conds.append("f.student_id = ?")
        params.append(student["id"])
    status = _pick(query, TICKET_STATUS)
    if status:
        conds.append("f.status = ?")
        params.append(status)
    if "待处理" in query or "还没处理" in query or "待跟进" in query:
        if "f.status = ?" not in conds:
            conds.append("f.status = '待处理'")
    if conds:
        sql += " AND " + " AND ".join(conds)
    sql += " ORDER BY f.id DESC"

    rows = _rows(db, sql, params)
    return {
        "sql": _fmt(sql, params), "params": params, "rows": rows,
        "summary": f"投诉工单 {len(rows)} 条" + (f"（{status}）" if status else ""),
        "hint": "播报学生、事由摘要、状态；未解决的要给一个跟进建议。",
    }


def _q_alert(db: sqlite3.Connection, query: str) -> dict:
    sql = (
        "SELECT a.id, u.real_name AS student_name, a.risk_level, a.trigger_reason, "
        "a.status, a.create_time FROM student_psych_alert a "
        "LEFT JOIN sys_user u ON u.id = a.student_id WHERE 1=1"
    )
    params: list[Any] = []
    conds = []
    student = _person(db, query, "STUDENT")
    if student:
        conds.append("a.student_id = ?")
        params.append(student["id"])
    status = _pick(query, ALERT_STATUS)
    if status:
        conds.append("a.status = ?")
        params.append(status)
    if "待跟进" in query or "需要跟进" in query or "还没处理" in query:
        if "a.status = ?" not in conds:
            conds.append("a.status = '未处理'")
    if conds:
        sql += " AND " + " AND ".join(conds)
    sql += " ORDER BY a.id DESC"

    rows = _rows(db, sql, params)
    high = sum(1 for r in rows if r["risk_level"] == "高")
    summary = f"心理预警 {len(rows)} 条" + (f"，其中高风险 {high} 条" if high else "")
    return {
        "sql": _fmt(sql, params), "params": params, "rows": rows,
        "summary": summary,
        "hint": "这是敏感信息：只播报学生、风险等级、触发原因摘要与状态，不要展开细节，提醒线下跟进。",
    }


def _q_event(db: sqlite3.Connection, query: str) -> dict:
    sql = (
        "SELECT e.id, e.event_name, e.event_type, e.start_time, e.location, "
        "e.max_participants, e.current_participants, "
        "(e.max_participants - e.current_participants) AS remaining "
        "FROM event_lecture e WHERE 1=1"
    )
    params: list[Any] = []
    conds = []
    names = [r["event_name"] for r in db.execute("SELECT event_name FROM event_lecture")]

    # 「这场活动都有谁报名」——报名名单是客服最常问的，之前只能看人数不能看人
    roster_hints = ("谁报名", "报名名单", "哪些人报", "名单", "报了名")
    if any(k in query for k in roster_hints):
        target = _pick(query, names)
        rsql = (
            "SELECT r.id, l.customer_name, l.contact_info, e.event_name, e.start_time, r.status "
            "FROM event_registration r JOIN event_lecture e ON e.id = r.event_id "
            "JOIN crm_lead l ON l.id = r.customer_id WHERE 1=1"
        )
        rparams: list[Any] = []
        if target:
            rsql += " AND e.event_name LIKE ?"
            rparams.append(f"%{target}%")
        rsql += " ORDER BY e.start_time ASC, r.id DESC"
        rows = _rows(db, rsql, rparams)
        return {
            "sql": _fmt(rsql, rparams), "params": rparams, "rows": rows,
            "summary": f"报名记录 {len(rows)} 条" + (f"（{target}）" if target else ""),
            "hint": "列出报名人姓名、手机号和活动名；没有就直说这场活动还没人报名。",
        }

    name = _pick(query, names)
    etype = None
    if name:
        # 活动全名已命中，就别再按"分享会"这类词去卡类型（名字里本来就带这三个字）
        conds.append("e.event_name LIKE ?")
        params.append(f"%{name}%")
    else:
        for t in ("线上", "线下"):
            if re.search(rf"{t}(?:的|活动|讲座|场|形式)", query):
                etype = t
                conds.append("e.event_type = ?")
                params.append(t)
                break
        if not etype:
            # 「有没有分享会/说明会」按名字模糊匹配，而不是当成类型
            for hint in ("分享会", "说明会", "沙龙", "见面会", "解析", "专场"):
                if hint in query:
                    conds.append("e.event_name LIKE ?")
                    params.append(f"%{hint}%")
                    break
    if "已满" in query or "满员" in query:
        conds.append("e.current_participants >= e.max_participants")
    if "还有名额" in query or "能报名" in query:
        conds.append("e.current_participants < e.max_participants")
    if conds:
        sql += " AND " + " AND ".join(conds)
    sql += " ORDER BY e.start_time ASC"

    rows = _rows(db, sql, params)
    return {
        "sql": _fmt(sql, params), "params": params, "rows": rows,
        "summary": f"活动 {len(rows)} 场" + (f"（{name or etype}）" if (name or etype) else ""),
        "hint": "报活动名、时间、地点、剩余名额（remaining）；满员的要明说。",
    }


def _q_project(db: sqlite3.Connection, query: str) -> dict:
    sql = "SELECT * FROM course_project WHERE 1=1"
    params: list[Any] = []
    names = [r["project_name"] for r in db.execute("SELECT project_name FROM course_project")]
    name = _pick(query, names)
    if name:
        sql += " AND project_name LIKE ?"
        params.append(f"%{name}%")
    cats = [r["category"] for r in db.execute("SELECT DISTINCT category FROM course_project")]
    cat = _pick(query, [c for c in cats if c])
    if cat:
        sql += " AND category = ?"
        params.append(cat)
    rows = _rows(db, sql, params)
    return {
        "sql": _fmt(sql, params), "params": params, "rows": rows,
        "summary": f"项目 {len(rows)} 个",
        "hint": "讲项目名、适合人群、学制与特点，不要念全部字段。",
    }


HANDLERS = {
    "crm_lead": _q_crm_lead,
    "student_score": _q_student_score,
    "leave": _q_leave,
    "daily_report": _q_daily_report,
    "ticket": _q_ticket,
    "alert": _q_alert,
    "event": _q_event,
    "project": _q_project,
}


def run(
    db: sqlite3.Connection,
    query: str,
    ctx: Optional[dict] = None,
    history: Optional[str] = None,
) -> dict:
    """返回 {intent, intent_label, sql, rows, count, summary, hint, ...}。

    识别不出意图、或意图是写操作时，不执行任何 SQL，直接给出可读的说明。
    history 是同一会话最近几轮的问+答摘要，用于把「那门课」「这个学期」这类
    指代词还原成具体实体；不传则退化为单轮查询。
    """
    query = (query or "").strip()
    if not query:
        return {
            "intent": "unknown", "intent_label": "未识别", "sql": None, "rows": [],
            "count": 0, "summary": "没有收到有效问题",
            "hint": "请让对方补充：想查谁、查什么（客户/成绩/请假/日报/投诉/预警/活动）。",
        }

    # 指代补全必须在意图识别之前：补全后「这是哪个学期的成绩」才认得出人，
    # 否则下游只能生成一条没有过滤条件的 SELECT。
    original_query = query
    query, followup_ent, is_followup = _expand_followup(db, query, history)

    # 破坏性 / 非查询指令：一律拒绝，连 SQL 都不生成
    lowered = query.lower()
    if any(k in query for k in ("删", "清空", "抓取", "改表", "建表", "随便")) or any(
        k in lowered for k in ("drop ", "delete ", "truncate", "update ", "insert ", "alter ", "select * from")
    ):
        return {
            "intent": "forbidden", "intent_label": "危险指令", "sql": None, "rows": [],
            "count": 0,
            "summary": "已拒绝：系统只支持查询，不执行删除、批量修改或直接写 SQL 的指令",
            "hint": "明确告知对方这条指令被拒绝；如需改数据，走对应的业务功能（改客户状态、审批请假），且一次只处理一条。",
        }

    intent, label, score = _detect_intent(query)
    if not intent or score < 2:
        # 「那李四呢」这种换人追问本身没有意图词，沿用上一轮的问法
        intent, label, score = _inherit_intent(original_query, history)
    if not intent or score < 2:
        return {
            "intent": "unknown", "intent_label": "未识别", "sql": None, "rows": [],
            "count": 0,
            "summary": "没听出要查哪类数据",
            "hint": "可查：客户档案、学生成绩、请假审批、员工日报、投诉工单、心理预警、活动名额。请让对方说得更具体。",
        }

    # 写操作：这里只做识别，不执行，避免「查一下」被当成「改一下」
    if intent == "leave" and any(k in query for k in LEAVE_WRITE_HINTS):
        return {
            "intent": "leave_approve", "intent_label": "请假审批（写操作）",
            "sql": None, "rows": [], "count": 0,
            "summary": "识别为审批操作：请假只能由班主任或管理员在审批面板处理",
            "hint": "不要声称已批准；告诉对方到页面右上角「请假审批」面板处理，或先帮他查待审批列表。",
        }

    if any(h in query for h in WRITE_HINTS) and intent == "ticket":
        return {
            "intent": "ticket_update", "intent_label": "工单流转（写操作）",
            "sql": None, "rows": [], "count": 0,
            "summary": "识别为工单状态变更，属于写操作",
            "hint": "不要声称已解决；说明需要负责老师在后台处理，可先列出该工单当前状态。",
        }

    if intent == "crm_lead" and any(h in query for h in WRITE_HINTS):
        target = _lead_person(db, query)
        new_status = _pick(query, LEAD_STATUS)
        if new_status and not target:
            return {
                "intent": "crm_lead_update", "intent_label": "客户状态流转",
                "sql": None, "rows": [], "count": 0,
                "summary": "没有找到这位客户，状态没有修改",
                "hint": "如实说没匹配到客户，请对方提供更完整的姓名；不要编造客户或声称已修改。",
            }
        if new_status:
            return {
                "intent": "crm_lead_update", "intent_label": "客户状态流转",
                "sql": None, "rows": [], "count": 0,
                "summary": (
                    f"识别为写操作：把【{target['customer_name'] if target else '该客户'}】"
                    f"改为【{new_status}】"
                ),
                "hint": "这是修改数据的操作，不要在这里执行；请走「客户状态流转」分支完成，再向员工确认结果。",
            }

    # 这两类要用身份上下文：「我班上」按班主任收范围，「我的日报」按本人收范围
    if intent == "student_score":
        result = _q_student_score(db, query, ctx)
    elif intent == "daily_report":
        result = _q_daily_report(db, query, ctx)
    else:
        result = HANDLERS[intent](db, query)

    # 是追问、但上文里一个实体都没捞到：这时候执行下去只能是 WHERE 1=1 把整册倒出来。
    # 与其答非所问地播报 20 条，不如反问一句要查谁。
    if result.get("broad") and is_followup and query == original_query:
        return {
            "intent": intent, "intent_label": label, "sql": None, "sql_line": None,
            "params": [], "rows": [], "count": 0,
            "summary": "没听出要查哪位学生、哪门课的成绩",
            "hint": (
                "这是承接上一轮的追问，但上文里没有可用的学生或课程。"
                "请反问一句「你想看哪位学生、哪门课的成绩？」，"
                "不要说「没有查到」，更不要罗列全表。"
            ),
            "need_clarify": True,
            "query": original_query,
            "resolved_query": None,
            "history_used": bool(history),
        }

    if not result["rows"] and not result.get("keep_summary"):
        result["summary"] = "没有查到符合条件的记录"
        result["hint"] = ("如实说没有查到，不要编造数据，也不要提「查到 0 条」；"
                          "可以提示对方换个条件（换人、换课程、去掉状态限制）。")
    if query != original_query:
        # 让模型知道自己是靠上文补全理解的，回答要落在这一条上
        result["hint"] += (
            f"（这句是承接上文的追问，已按【{query}】理解；"
            "rows 已按录入时间倒序，第一条就是刚刚在聊的那条，先直接答它，"
            "只有确实需要区分学期时才补一句更早的记录。）"
        )

    result.update({
        "intent": intent,
        "intent_label": label,
        "count": len(result["rows"]),
        "query": original_query,
        # 补全后的问句：和原问句不同就说明用了上文
        "resolved_query": query if query != original_query else None,
        "history_used": bool(history),
        # 现成的展示行：模型只需原样照抄，避免它自己拼「查询语句：」四个字却拼出空行
        "sql_line": f"查询语句：{result['sql']}" if result.get("sql") else None,
    })
    return result
