"""我的工作台：按登录身份只返回"这个人能看的东西"。

四种身份看到的内容完全不同，但都走同一个接口，后端按 role 分流：

- 管理员：全局概览（线索 / 待审批 / 未处理工单），并给数据后台入口
- 班主任：自己名下学生的待审批请假、成绩预警、未处理工单
- 顾问：客户线索池（登录页客服留资都落在这里），可写跟进 / 改状态
- 学员：自己的成绩、请假、反馈工单

所有过滤条件都由 token 里的 uid 推出来，前端不能传 id 查别人。
"""

import json
import re
import sqlite3
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from database import get_db
from models.base import ResponseModel
from services import (
    alert_engine,
    auth_service,
    class_service,
    leave_service,
    log_service,
    profile_engine,
)

router = APIRouter()

LEAD_STATUSES = ["新增意向", "跟进中", "已签约", "已流失"]
TICKET_OPEN = ("待处理", "处理中")

# 学生反馈：学生选一个类型提交，班主任按类型看、回复、结案
FB_CATEGORIES = ["课程教学", "老师沟通", "住宿生活", "报修设施", "教务流程", "其他"]
FB_STATUSES = ("待处理", "处理中", "已解决")
FB_DONE = "已解决"

# 学生心理周记：比情绪评估多记睡眠 / 压力源 / 持续时长，班主任跟进
JR_TAGS = ("平静", "低落", "焦虑", "烦躁", "疲惫", "其他")
JR_SLEEPS = ("良好", "一般", "较差")
JR_SOURCES = ("学业", "人际", "家庭", "就业", "经济", "其他")
JR_DURATIONS = ("今天", "几天", "一两周", "一个月以上")
JR_STATUSES = ("待跟进", "跟进中", "已跟进")
JR_DONE = "已跟进"
JR_ALERT_SCORE = 70  # 与 FR-011 一致：自评分值达到这条线就提醒班主任


# ---------------------------------------------------------------------------
# 公共小工具
# ---------------------------------------------------------------------------
def _me(db: sqlite3.Connection, authorization: Optional[str]) -> dict:
    payload = auth_service.read_token(authorization)
    if not payload:
        raise HTTPException(status_code=401, detail="请先登录")
    user = auth_service.profile(db, payload.get("uid"))
    if not user:
        raise HTTPException(status_code=401, detail="登录信息已失效，请重新登录")
    return user


def _short(ts: Optional[str]) -> str:
    """2026-11-19 03:18:40 → 11-19 03:18"""
    return (ts or "")[5:16]


def _days(start: Optional[str], end: Optional[str]) -> int:
    try:
        import datetime as _dt

        a = _dt.datetime.strptime((start or "")[:19], "%Y-%m-%d %H:%M:%S")
        b = _dt.datetime.strptime((end or "")[:19], "%Y-%m-%d %H:%M:%S")
        return max(1, (b - a).days + (1 if (b - a).seconds else 0))
    except Exception:
        return 1


# 雅思 9 分制、托福 120 分制，和百分制课程不是一套量纲：
# 既不能混进班级/个人均分，也不能按 60 分判不及格（雅思 6.5 已算不错）。
_LANGUAGE_TESTS = ("雅思", "托福", "IELTS", "TOEFL")


def _is_language_test(course: Optional[str]) -> bool:
    return any(k in (course or "") for k in _LANGUAGE_TESTS)


def _score_scale(course: Optional[str]) -> str:
    """返回这门课的量纲标签，供前端展示（百分制不显示，避免干扰）。"""
    name = course or ""
    if "雅思" in name or "IELTS" in name:
        return "9 分制"
    if "托福" in name or "TOEFL" in name:
        return "120 分制"
    return ""


def _level(score: Optional[float], course: Optional[str] = None) -> str:
    if score is None:
        return "暂无"
    if _is_language_test(course):
        # 语言成绩按自己的量纲评级，不参与 60 分及格线
        if "雅思" in (course or "") or "IELTS" in (course or ""):
            if score >= 8:
                return "优秀"
            if score >= 7:
                return "良好"
            if score >= 6:
                return "及格"
            return "待提升"
        # 托福 120 分制
        if score >= 110:
            return "优秀"
        if score >= 90:
            return "良好"
        if score >= 60:
            return "及格"
        return "待提升"
    if score >= 85:
        return "优秀"
    if score >= 75:
        return "良好"
    if score >= 60:
        return "及格"
    return "待提升"


def _brief(bg: Optional[str]) -> str:
    """线索背景压成一行：优先取"意向 / 对话摘要"。"""
    text = (bg or "").strip()
    if not text:
        return "—"
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    picked = [
        ln
        for ln in lines
        if ln.startswith(("意向", "对话摘要", "年龄")) and not ln.endswith("未填写")
    ]
    text = " · ".join(picked) if picked else " · ".join(lines)
    text = text.replace("意向：", "意向 ").replace("对话摘要：", "")
    # 姓名和电话已经单独展示，摘要里去掉，免得一行全是重复信息
    text = re.sub(r"1\d{10}", "", text)
    text = re.sub(r"(电话|手机号|手机|联系方式)[：:]?", "", text)
    text = re.sub(r"[，,、]{2,}", "，", text).strip(" ·，,")
    return text[:120] or "—"


def _lead_rows(
    db: sqlite3.Connection, limit: int = 30, owner_id: Optional[int] = None
) -> list[dict]:
    where, args = "", []
    if owner_id is not None:
        where = "WHERE l.owner_employee_id = ? "
        args.append(owner_id)
    rows = db.execute(
        "SELECT l.*, u.real_name AS owner_name FROM crm_lead l "
        "LEFT JOIN sys_user u ON u.id = l.owner_employee_id "
        + where
        + "ORDER BY l.update_time DESC, l.id DESC LIMIT ?",
        args + [limit],
    ).fetchall()
    return [
        {
            "id": r["id"],
            "name": r["customer_name"] or "未留名",
            "phone": r["contact_info"] or "—",
            "status": r["status"] or "新增意向",
            "source": "在线客服" if "在线客服" in (r["background_info"] or "") else "其他来源",
            "brief": _brief(r["background_info"]),
            "owner": r["owner_name"] or "未分配",
            "time": _short(r["update_time"] or r["create_time"]),
            "history": (r["follow_up_history"] or "").strip()[-400:],
        }
        for r in rows
    ]


def _lead_counts(db: sqlite3.Connection) -> dict:
    counts = {st: 0 for st in LEAD_STATUSES}
    for r in db.execute("SELECT status, COUNT(*) AS n FROM crm_lead GROUP BY status"):
        if r["status"] in counts:
            counts[r["status"]] = r["n"]
    counts["全部"] = sum(counts.values())
    return counts


# ---------------------------------------------------------------------------
# 各身份的负载
# ---------------------------------------------------------------------------
def _admin_payload(db: sqlite3.Connection, me: dict) -> dict:
    counts = _lead_counts(db)
    pending = db.execute(
        "SELECT COUNT(*) FROM student_admin_service WHERE status = '待审批'"
    ).fetchone()[0]
    tickets = db.execute(
        "SELECT COUNT(*) FROM student_feedback_ticket WHERE status IN ('待处理','处理中')"
    ).fetchone()[0]
    students = db.execute("SELECT COUNT(*) FROM sys_user WHERE user_type = 'STUDENT'").fetchone()[0]

    leaves = [
        {
            "id": r["id"],
            "student": r["real_name"],
            "period": f"{_short(r['start_time'])} → {_short(r['end_time'])}",
            "days": _days(r["start_time"], r["end_time"]),
            "reason": r["reason"] or "—",
            "status": r["status"],
        }
        for r in db.execute(
            "SELECT v.*, u.real_name FROM student_admin_service v "
            "JOIN sys_user u ON u.id = v.student_id "
            "WHERE v.status = '待审批' ORDER BY v.start_time"
        )
    ]
    return {
        "headline": f"全校 {students} 名学员 · {pending} 条请假待批 · {counts['全部']} 条线索",
        "cards": [
            {"label": "客户线索", "value": counts["全部"], "hint": f"新增 {counts['新增意向']} · 跟进中 {counts['跟进中']}"},
            {"label": "待批请假", "value": pending, "hint": "全校范围"},
            {"label": "未结工单", "value": tickets, "hint": "待处理 + 处理中"},
            {"label": "在读学员", "value": students, "hint": "含各方向"},
        ],
        "sections": [
            {"key": "leaves", "kind": "leave", "title": "待审批请假", "hint": "可直接批，也可到数据后台看全量", "items": leaves},
            {"key": "leads", "kind": "lead", "title": "最新线索", "hint": "客服留资会排在最前", "items": _lead_rows(db, 6)},
        ],
        "footer": {"label": "打开数据后台", "href": "/admin", "text": "图表、12 张数据表、线索跟进都在后台"},
        "can_follow": True,
    }


def _trial_payload(db: sqlite3.Connection, me: dict, cls: sqlite3.Row) -> dict:
    """活动项目老师：班上是试听名单，不是正式学员。

    名单来自客户线索：有联系方式、且不是「已流失」。已流失的客户学生不纳入班级，
    这里只报一个「未入班」数量，不显示姓名。
    """
    members = class_service.trial_members(db, cls["id"])
    pending, signed = members["pending"], members["signed"]
    total = len(pending) + len(signed)
    label = me["real_name"] if me["real_name"].endswith("老师") else f"{me['real_name']} 老师"
    excluded = db.execute("SELECT COUNT(*) FROM crm_lead WHERE class_id IS NULL").fetchone()[0]
    return {
        "class_name": cls["name"],
        "class_id": cls["id"],
        "class_kind": class_service.KIND_TRIAL,
        "headline": (
            f"{label} · {cls['name']} · 待签约 {len(pending)} 人 · 已签约 {len(signed)} 人"
        ),
        "cards": [
            {"label": "我的班级", "value": cls["name"], "hint": f"试听学员 {total} 人在班"},
            {"label": "待签约", "value": len(pending), "hint": "试听 / 跟进中的意向学员"},
            {"label": "已签约", "value": len(signed), "hint": "已签约，可转正式班"},
            {"label": "未入班", "value": int(excluded or 0), "hint": "已流失或没留电话，不纳入班级"},
        ],
        "sections": [
            {
                "key": "trial_pending",
                "kind": "trial",
                "title": "待签约学员",
                "hint": "有联系方式的意向学员，试听课后按这个名单逐个联系",
                "items": pending,
            },
            {
                "key": "trial_signed",
                "kind": "trial",
                "title": "已签约学员",
                "hint": "已签约，转正式班后由方向班主任带",
                "items": signed,
            },
        ],
        "footer": None,
        "can_follow": False,
    }


def _fb_item(r: sqlite3.Row) -> dict:
    """一条学生反馈。

    学生端只看得到自己的那条（含老师回复），老师端才带学生姓名和处理人；
    两边共用一个结构，前端少写一套渲染。
    """
    keys = r.keys()

    def pick(name: str) -> str:
        return (r[name] or "") if name in keys else ""

    return {
        "id": r["id"],
        "student": pick("real_name"),
        "username": pick("username"),
        "class_name": pick("class_name"),
        "category": pick("category") or "其他",
        "content": r["content"] or "",
        "detail": pick("detail"),
        "status": r["status"] or "待处理",
        "reply": pick("solution"),
        "time": _short(r["create_time"]),
        "handle_time": _short(pick("handle_time")),
        "handler": pick("handler_name"),
    }


def _fb_rows(
    db: sqlite3.Connection, where: str, args: list, limit: int = 40
) -> list[dict]:
    return [
        _fb_item(r)
        for r in db.execute(
            "SELECT t.*, u.real_name, u.username, c.name AS class_name, "
            "  h.real_name AS handler_name "
            "FROM student_feedback_ticket t "
            "JOIN sys_user u ON u.id = t.student_id "
            "LEFT JOIN school_class c ON c.id = u.class_id "
            "LEFT JOIN sys_user h ON h.id = t.handler_id "
            "WHERE " + where + " ORDER BY "
            "  CASE t.status WHEN '待处理' THEN 0 WHEN '处理中' THEN 1 ELSE 2 END, "
            "  t.create_time DESC LIMIT ?",
            args + [limit],
        )
    ]


def _jr_item(r: sqlite3.Row) -> dict:
    keys = r.keys()

    def pick(name: str) -> str:
        return (r[name] or "") if name in keys else ""

    return {
        "id": r["id"],
        "student": pick("real_name"),
        "username": pick("username"),
        "class_name": pick("class_name"),
        "mood_tag": pick("mood_tag") or "平静",
        "mood_score": r["mood_score"] if "mood_score" in keys else None,
        "sleep": pick("sleep"),
        "stress_source": pick("stress_source"),
        "duration": pick("duration"),
        "content": r["content"] or "",
        "status": r["status"] or "待跟进",
        "reply": pick("handle_note"),
        "time": _short(r["create_time"]),
        "handle_time": _short(pick("handle_time")),
        "handler": pick("handler_name"),
    }


def _jr_rows(
    db: sqlite3.Connection, where: str, args: list, limit: int = 40
) -> list[dict]:
    return [
        _jr_item(r)
        for r in db.execute(
            "SELECT j.*, u.real_name, u.username, c.name AS class_name, "
            "  h.real_name AS handler_name "
            "FROM student_psych_journal j JOIN sys_user u ON u.id = j.student_id "
            "LEFT JOIN school_class c ON c.id = u.class_id "
            "LEFT JOIN sys_user h ON h.id = j.handler_id "
            "WHERE " + where + " ORDER BY "
            "  CASE j.status WHEN '待跟进' THEN 0 WHEN '跟进中' THEN 1 ELSE 2 END, "
            "  COALESCE(j.mood_score, 0) DESC, j.create_time DESC LIMIT ?",
            args + [limit],
        )
    ]


def _alert_item(r: sqlite3.Row) -> dict:
    """预警一句话：学生说了什么 + 命中了什么词。

    trigger_reason 存的是「情绪评估命中[自杀]，原话：我向自杀」这种内部记录，
    老师要看的是学生原话，所以拆开给：quote 是原话，basis 是命中依据。
    """
    # 没有「原话：」的老记录（人工登记 / 种子数据），整段就是描述，不再重复给依据
    reason = r["trigger_reason"] or ""
    basis, quote = "", reason
    if "原话：" in reason:
        head, quote = reason.split("原话：", 1)
        hit = re.search(r"\[([^\]]+)\]", head)
        # 「情绪评估命中[自杀]」对老师是黑话，换成「命中「自杀」」
        basis = f"命中「{hit.group(1)}」" if hit else head.strip("，, ")
    return {
        "id": r["id"],
        "student": r["real_name"],
        "username": r["username"],
        "risk": r["risk_level"] or "中",
        "status": r["status"] or "未处理",
        "quote": (quote or reason).strip(),
        "basis": basis,
        "time": (r["create_time"] or "")[5:16],
        "note": r["handle_note"] or "",
        "handle_time": (r["handle_time"] or "")[5:16],
        "handler": r["handler_name"] or "",
    }


def _teacher_payload(db: sqlite3.Connection, me: dict) -> dict:
    cls = class_service.teacher_class(db, me["id"])
    if cls and (cls["kind"] or class_service.KIND_NORMAL) == class_service.KIND_TRIAL:
        return _trial_payload(db, me, cls)
    class_name = cls["name"] if cls else ""
    students = [
        dict(r)
        for r in db.execute(
            "SELECT u.id, u.real_name, u.username, u.contact_info, u.department, "
            "  (SELECT ROUND(AVG(s.score),1) FROM student_score s WHERE s.student_id = u.id "
            "     AND s.course_name NOT LIKE '%雅思%' AND s.course_name NOT LIKE '%托福%' "
            "     AND s.course_name NOT LIKE '%IELTS%' AND s.course_name NOT LIKE '%TOEFL%') AS avg_score, "
            "  (SELECT COUNT(*) FROM student_score s WHERE s.student_id = u.id AND s.score < 60 "
            "     AND s.course_name NOT LIKE '%雅思%' AND s.course_name NOT LIKE '%托福%' "
            "     AND s.course_name NOT LIKE '%IELTS%' AND s.course_name NOT LIKE '%TOEFL%') AS low, "
            "  (SELECT COUNT(*) FROM student_admin_service v WHERE v.student_id = u.id AND v.status = '待审批') AS pending, "
            "  (SELECT COUNT(*) FROM student_psych_alert a WHERE a.student_id = u.id "
            "     AND COALESCE(a.status,'未处理') <> '已处理') AS alerts, "
            "  (SELECT COUNT(*) FROM student_psych_journal j WHERE j.student_id = u.id "
            "     AND COALESCE(j.status,'待跟进') <> '已跟进') AS journals "
            "FROM sys_user u WHERE u.homeroom_teacher_id = ? AND u.user_type = 'STUDENT' "
            "AND COALESCE(u.status,'正常') <> '已删除' ORDER BY u.id",
            (me["id"],),
        )
    ]
    ids = [s["id"] for s in students] or [0]
    holes = ",".join("?" * len(ids))

    leaves = [
        {
            "id": r["id"],
            "student": r["real_name"],
            "period": f"{_short(r['start_time'])} → {_short(r['end_time'])}",
            "days": _days(r["start_time"], r["end_time"]),
            "reason": r["reason"] or "—",
            "status": r["status"],
        }
        for r in db.execute(
            f"SELECT v.*, u.real_name FROM student_admin_service v "
            f"JOIN sys_user u ON u.id = v.student_id "
            f"WHERE v.student_id IN ({holes}) AND v.status = '待审批' "
            f"ORDER BY v.start_time",
            ids,
        )
    ]
    # 学生反馈：本班学生提交的，待处理排最前；已解决的进「处理记录」折叠区。
    # 处理人是本班班主任（学生反馈的是课程/住宿/教务，班主任最清楚该找谁）。
    fb_open: list[dict] = []
    fb_done: list[dict] = []
    fb_all = _fb_rows(db, f"t.student_id IN ({holes})", ids, limit=30)
    fb_open = [x for x in fb_all if x["status"] != FB_DONE]
    fb_done = [x for x in fb_all if x["status"] == FB_DONE][:5]

    # 心理周记：本班学生写的详细状态，待跟进优先、分值高的排前面；
    # 写周记时分值 >= 70 的那条也会同时出现在「心理预警」里，两边不重复建记录。
    jr_all = _jr_rows(db, f"j.student_id IN ({holes})", ids, limit=30)
    jr_open = [x for x in jr_all if x["status"] != JR_DONE]
    jr_done = [x for x in jr_all if x["status"] == JR_DONE][:5]

    scored = [s for s in students if s["avg_score"] is not None]
    avg = round(sum(s["avg_score"] for s in scored) / len(scored), 1) if scored else None
    weak = sum(1 for s in students if (s["avg_score"] or 100) < 75)

    # 心理预警：只有本班班主任看得到，学生端任何接口都不返回。
    # 每条单独列（同一学生连发几条也各占一行），高危排最前，再按时间倒序。
    alert_rows = db.execute(
        "SELECT a.*, u.real_name, u.username, h.real_name AS handler_name "
        "FROM student_psych_alert a JOIN sys_user u ON u.id = a.student_id "
        "LEFT JOIN sys_user h ON h.id = a.handler_id "
        "WHERE u.homeroom_teacher_id = ? ORDER BY "
        "  CASE a.risk_level WHEN '高' THEN 0 WHEN '中' THEN 1 ELSE 2 END, "
        "  CASE COALESCE(a.status,'未处理') WHEN '未处理' THEN 0 WHEN '跟进中' THEN 1 ELSE 2 END, "
        "  a.create_time DESC",
        (me["id"],),
    ).fetchall()
    alerts = [_alert_item(r) for r in alert_rows if (r["status"] or "未处理") != "已处理"]
    alert_history = [_alert_item(r) for r in alert_rows if (r["status"] or "未处理") == "已处理"][:5]
    high = sum(1 for a in alerts if a["risk"] == "高")

    teacher_label = me["real_name"] if me["real_name"].endswith("老师") else f"{me['real_name']} 老师"
    return {
        "class_name": class_name,
        "class_id": cls["id"] if cls else None,
        "class_kind": class_service.KIND_NORMAL,
        "headline": (
            f"{teacher_label} · {class_name or '未分配班级'} · "
            f"名下 {len(students)} 名学生 · {len(leaves)} 条请假待批"
            + (f" · {len(alerts)} 条心理预警" + (f"（{high} 条高危）" if high else "") if alerts else "")
            + (f" · {len(fb_open)} 条反馈待回复" if fb_open else "")
            + (f" · {len(jr_open)} 条心理周记待跟进" if jr_open else "")
        ),
        "cards": [
            {
                "label": "我的班级",
                "value": class_name or "—",
                "hint": (f"{len(students)} 名学生 · 均分 {avg}" if avg is not None else f"{len(students)} 名学生")
                if class_name else "找顾问分配班级",
            },
            {"label": "待批请假", "value": len(leaves), "hint": "只看自己班上"},
            {"label": "心理预警", "value": len(alerts), "hint": f"高危 {high} 条 · 需当面确认" if high else "本班学生情绪异常"},
            {
                "label": "班级均分",
                "value": avg if avg is not None else "—",
                "hint": f"{weak} 人低于 75 · 不含语言成绩",
            },
            {"label": "学生反馈", "value": len(fb_open), "hint": f"待回复 · 已结案 {len(fb_done)} 条"},
            {"label": "心理周记", "value": len(jr_open), "hint": f"待跟进 · 已跟进 {len(jr_done)} 条"},
        ],
        "alerts": alerts,
        "alert_history": alert_history,
        "feedback": fb_open,
        "feedback_history": fb_done,
        "journals": jr_open,
        "journal_history": jr_done,
        "journal_options": {
            "tags": list(JR_TAGS), "sleeps": list(JR_SLEEPS),
            "sources": list(JR_SOURCES), "durations": list(JR_DURATIONS),
        },
        "sections": [
            {"key": "leaves", "kind": "leave", "title": "待我审批的请假", "hint": "通过 / 驳回都留痕", "items": leaves},
            {
                "key": "students",
                "kind": "student",
                "title": "我的学生",
                "hint": f"{class_name or '未分配班级'} · 均分低于 75 的会标黄",
                "items": [
                    {
                        "id": s["id"],
                        "name": s["real_name"],
                        "username": s["username"],
                        "contact": s["contact_info"] or "",
                        "class_name": class_name,
                        "dept": s["department"] or "—",
                        "avg": s["avg_score"],
                        "level": _level(s["avg_score"]),
                        "low": s["low"],
                        "pending": s["pending"],
                        "alerts": s["alerts"],
                        "journals": s["journals"],
                    }
                    for s in students
                ],
            },
            {
                "key": "feedback",
                "kind": "feedback",
                "title": "学生反馈",
                "hint": "本班学生提交，回复后学生会看到",
                "items": fb_open,
            },
        ],
        "footer": None,
        "can_follow": False,
    }


def _staff_payload(db: sqlite3.Connection, me: dict) -> dict:
    """顾问只能看到自己名下的线索（越权由后端挡，前端拿不到别人的）。"""
    rows = _lead_rows(db, 60, owner_id=me["id"])
    counts = {st: sum(1 for r in rows if r["status"] == st) for st in LEAD_STATUSES}
    fresh = [r for r in rows if r["status"] == "新增意向"]

    return {
        "headline": f"{me['real_name']} · 名下 {len(rows)} 条线索，其中 {len(fresh)} 条新增意向待联系",
        "cards": [
            {"label": "我的线索", "value": len(rows), "hint": "只显示负责人是你"},
            {"label": "新增意向", "value": counts["新增意向"], "hint": "优先联系"},
            {"label": "跟进中", "value": counts["跟进中"], "hint": "已接触未签约"},
            {"label": "已签约", "value": counts["已签约"], "hint": f"流失 {counts['已流失']} 条"},
        ],
        "sections": [
            {
                "key": "leads",
                "kind": "lead",
                "title": "线索池",
                "hint": "登录页客服留资会带「在线客服」标记，按最近更新排序",
                "items": rows,
            }
        ],
        "footer": None,
        "can_follow": True,
    }


def _student_payload(db: sqlite3.Connection, me: dict) -> dict:
    scores = [
        {
            "course": r["course_name"],
            "score": r["score"],
            "level": _level(r["score"], r["course_name"]),
            "scale": _score_scale(r["course_name"]),
            "semester": r["semester"] or "—",
        }
        for r in db.execute(
            "SELECT * FROM student_score WHERE student_id = ? ORDER BY id", (me["id"],)
        )
    ]
    leaves = [
        {
            "id": r["id"],
            "student": "我",
            "period": f"{_short(r['start_time'])} → {_short(r['end_time'])}",
            "days": _days(r["start_time"], r["end_time"]),
            "reason": r["reason"] or "—",
            "status": r["status"],
        }
        for r in db.execute(
            "SELECT * FROM student_admin_service WHERE student_id = ? "
            "ORDER BY start_time DESC LIMIT 8",
            (me["id"],),
        )
    ]
    # 学生只看自己的反馈：老师回复了（solution 有内容）就会显示在面板里
    fb_all = _fb_rows(db, "t.student_id = ?", [me["id"]], limit=20)
    fb_open = [x for x in fb_all if x["status"] != FB_DONE]
    fb_done = [x for x in fb_all if x["status"] == FB_DONE]
    tickets = fb_all

    # 心理周记：学生自己写的详细状态 + 班主任的回复，都在心理关怀面板里看
    jr_all = _jr_rows(db, "j.student_id = ?", [me["id"]], limit=20)
    jr_open = [x for x in jr_all if x["status"] != JR_DONE]

    # 画像概览：把「最新标签 / 分值 / 最近交互 / 历史情绪」直接给学生看，
    # 和周记放在一起，省得他再翻别的页面（FR-010 的学生侧口径）。
    prof = db.execute(
        "SELECT * FROM student_psych_profile WHERE student_id = ?", (me["id"],)
    ).fetchone()
    profile = None
    if prof:
        try:
            hist = json.loads(prof["emotion_history"] or "[]")
        except (TypeError, ValueError):
            hist = []
        profile = {
            "tag": prof["latest_emotion_tag"] or "—",
            "score": prof["emotion_score"],
            "last": _short(prof["last_interaction_time"]),
            "total": len(hist),
            "history": hist[-10:],
        }

    # 均分只统计百分制课程；雅思/托福亮出自己的等级，但不混进均分与最高分
    pct_scores = [s for s in scores if not _is_language_test(s["course"])]
    vals = [s["score"] for s in pct_scores if s["score"] is not None]
    avg = round(sum(vals) / len(vals), 1) if vals else None
    best = max(pct_scores, key=lambda s: s["score"]) if pct_scores else None
    pending = sum(1 for l in leaves if l["status"] == "待审批")

    cls = class_service.student_class(db, me["id"])
    class_name = cls["name"] if cls else ""
    homeroom = me.get("homeroom_name") or ""

    return {
        "class_name": class_name,
        "class_teacher": homeroom,
        "headline": (
            f"{me['real_name']} · {class_name or '未分配班级'}"
            + (f" · 班主任 {homeroom}" if homeroom else "")
            + f" · 均分 {avg if avg is not None else '—'}"
        ),
        "cards": [
            {
                "label": "我的班级",
                "value": class_name or "—",
                "hint": (f"班主任 {homeroom}" if homeroom else "找顾问分配班级"),
            },
            {
                "label": "平均分",
                "value": avg if avg is not None else "—",
                "hint": f"百分制 {len(pct_scores)} 门 · 语言成绩单列" if avg is not None else "暂无百分制课程",
            },
            {"label": "最高分", "value": best["score"] if best else "—", "hint": best["course"] if best else "暂无成绩"},
            {"label": "待批请假", "value": pending, "hint": f"最近 {len(leaves)} 条记录"},
            {"label": "我的反馈", "value": len(fb_open), "hint": f"待回复 · 已回复 {len(fb_done)} 条"},
            {"label": "心理周记", "value": len(jr_open), "hint": f"待跟进 · 已写 {len(jr_all)} 篇"},
        ],
        "sections": [
            {
                "key": "scores",
                "kind": "score",
                "title": "我的成绩",
                "hint": "本学期课程与等级",
                "items": scores,
            },
            {"key": "leaves", "kind": "leave", "title": "我的请假", "hint": "审批状态实时同步", "items": leaves},
            {
                "key": "feedback",
                "kind": "feedback",
                "title": "我的反馈",
                "hint": "课程 / 住宿 / 报修都可以提，班主任回复后在这里看",
                "items": tickets,
            },
        ],
        "feedback": fb_all,
        "feedback_categories": FB_CATEGORIES,
        "journals": jr_all,
        "profile": profile,
        "journal_options": {
            "tags": list(JR_TAGS), "sleeps": list(JR_SLEEPS),
            "sources": list(JR_SOURCES), "durations": list(JR_DURATIONS),
        },
        "footer": None,
        "can_follow": False,
    }


# ---------------------------------------------------------------------------
# 接口
# ---------------------------------------------------------------------------
@router.get("/workspace", response_model=ResponseModel, summary="我的工作台（按身份返回权限内数据）")
def my_workspace(
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    role = me["role"]
    if role == "admin":
        data = _admin_payload(db, me)
    elif role == "teacher":
        data = _teacher_payload(db, me)
    elif role == "staff":
        data = _staff_payload(db, me)
    elif role == "student":
        data = _student_payload(db, me)
    else:
        raise HTTPException(status_code=403, detail="当前身份没有工作台")

    data.update(
        {
            "role": role,
            "role_label": me["role_label"],
            "name": me["real_name"],
            "department": me.get("department"),
            "lead_statuses": LEAD_STATUSES,
            "today_logs": log_service.today_stats(db, me["id"])["total"],
        }
    )
    return ResponseModel(msg=f"{me['role_label']}工作台", data=data)


class FollowIn(BaseModel):
    note: Optional[str] = None
    status: Optional[str] = None


@router.post("/workspace/lead/{lead_id}/follow", response_model=ResponseModel, summary="顾问：写跟进 / 改线索状态")
def follow_lead(
    lead_id: int,
    body: FollowIn,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    # 线索是顾问自己的业绩，管理员只在数据后台看：谁引进的、跟到哪一步。
    # 让管理员能写，等于把提成归属和跟进责任搅在一起。
    if me["role"] != "staff":
        raise HTTPException(status_code=403, detail="线索由所属顾问跟进，管理员只在数据后台查看")

    row = db.execute("SELECT * FROM crm_lead WHERE id = ?", (lead_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="线索不存在")
    if row["owner_employee_id"] != me["id"]:
        raise HTTPException(status_code=403, detail="这条线索不在你名下，不能跟进")

    status = body.status if body.status in LEAD_STATUSES else None
    note = (body.note or "").strip()[:300]
    if not status and not note:
        raise HTTPException(status_code=400, detail="跟进内容和状态至少填一个")

    import time as _time

    line = f"\n[{_time.strftime('%m-%d %H:%M')}] {note}" if note else ""
    if status:
        db.execute(
            "UPDATE crm_lead SET status = ?, follow_up_history = COALESCE(follow_up_history,'') || ?, "
            "update_time = datetime('now','localtime') WHERE id = ?",
            (status, line, lead_id),
        )
    else:
        db.execute(
            "UPDATE crm_lead SET follow_up_history = COALESCE(follow_up_history,'') || ?, "
            "update_time = datetime('now','localtime') WHERE id = ?",
            (line, lead_id),
        )
    db.commit()
    # 签约 / 流失会改变试听班名单，当场同步（已流失的移出班级）
    class_service.attach_lead(db, lead_id)
    changed = []
    if status and status != row["status"]:
        changed.append(f"状态 {row['status']} → {status}")
    if note:
        changed.append(note)
    log_service.write(
        db,
        actor=me,
        action="lead_status" if status else "lead_follow",
        summary=f"跟进线索：{row['customer_name'] or '未留名'}（{row['contact_info'] or '—'}）",
        detail="｜".join(changed)[:300],
        target_type="lead",
        target_id=lead_id,
    )
    return ResponseModel(msg="已保存", data={"id": lead_id, "status": status or row["status"]})


class AlertHandleIn(BaseModel):
    status: str
    note: Optional[str] = None


ALERT_STATUSES = ("未处理", "跟进中", "已处理")

# 预警和周记是同一件事的两个视图，状态要一一对应：
# 预警「已处理」= 周记「已跟进」，「跟进中」两边同名。
_ALERT_TO_JR = {"未处理": "待跟进", "跟进中": "跟进中", "已处理": "已跟进"}
_JR_TO_ALERT = {"待跟进": "未处理", "跟进中": "跟进中", "已跟进": "已处理"}


def _sync_alert_to_journal(
    db: sqlite3.Connection, journal_id: Optional[int], status: str, note: str, handler_id: int
) -> None:
    """老师处理预警后，把结果回写到来源周记，学生端才看得到「班主任回复」。"""
    if not journal_id:
        return  # 对话等其它来源的预警没有对应周记
    exists = db.execute(
        "SELECT 1 FROM student_psych_journal WHERE id = ?", (journal_id,)
    ).fetchone()
    if not exists:
        return
    db.execute(
        "UPDATE student_psych_journal SET status = ?, handler_id = ?, handle_note = ?, "
        "handle_time = datetime('now','localtime'), update_time = datetime('now','localtime') "
        "WHERE id = ?",
        (_ALERT_TO_JR.get(status, "已跟进"), handler_id, note, journal_id),
    )


def _sync_journal_to_alert(
    db: sqlite3.Connection, journal_id: int, status: str, note: str, handler_id: int
) -> None:
    """反向：老师直接在周记面板回复时，同步关联预警，避免预警面板还挂着未处理。"""
    row = db.execute(
        "SELECT id FROM student_psych_alert WHERE journal_id = ? ORDER BY id DESC LIMIT 1",
        (journal_id,),
    ).fetchone()
    if not row:
        return
    db.execute(
        "UPDATE student_psych_alert SET status = ?, handler_id = ?, handle_note = ?, "
        "handle_time = datetime('now','localtime') WHERE id = ?",
        (_JR_TO_ALERT.get(status, "已处理"), handler_id, note, row["id"]),
    )


@router.post("/workspace/alert/{alert_id}/handle", response_model=ResponseModel, summary="班主任：跟进 / 处理心理预警")
def handle_alert(
    alert_id: int,
    body: AlertHandleIn,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    # 预警是班主任的活：他知道这个学生最近什么状态、家长能不能联系上。
    # 管理员只在数据后台看全量，不代处理；学生本人永远看不到这条记录。
    if me["role"] != "teacher":
        raise HTTPException(status_code=403, detail="心理预警由学生班主任处理，管理员只在数据后台查看")

    row = db.execute(
        "SELECT a.*, u.real_name, u.homeroom_teacher_id FROM student_psych_alert a "
        "JOIN sys_user u ON u.id = a.student_id WHERE a.id = ?",
        (alert_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="预警不存在")
    if row["homeroom_teacher_id"] != me["id"]:
        raise HTTPException(status_code=403, detail="这条预警不在你班上，不能处理")

    status = (body.status or "").strip()
    if status not in ALERT_STATUSES:
        raise HTTPException(status_code=400, detail="状态只能是 未处理 / 跟进中 / 已处理")
    note = (body.note or "").strip()[:300]
    if status == "已处理" and not note and not (row["handle_note"] or "").strip():
        raise HTTPException(
            status_code=400,
            detail="标为已处理前写一句沟通结果（例如：已电话联系，情绪平稳，家长知情）",
        )

    final_note = note or row["handle_note"]
    db.execute(
        "UPDATE student_psych_alert SET status = ?, handler_id = ?, handle_note = ?, "
        "handle_time = datetime('now','localtime') WHERE id = ?",
        (status, me["id"], final_note, alert_id),
    )
    # 同一件事的两个视图：预警处理完，来源周记也要同步，学生端才不再是「待跟进」
    _sync_alert_to_journal(db, row["journal_id"] if "journal_id" in row.keys() else None,
                           status, final_note or "", me["id"])
    db.commit()
    log_service.write(
        db,
        actor=me,
        action="alert_handle",
        summary=f"心理预警：{row['real_name']} · {status}" + (f"｜{note[:40]}" if note else ""),
        detail=note,
        target_type="psych_alert",
        target_id=alert_id,
    )
    return ResponseModel(
        msg=f"{row['real_name']} 的预警已标记为「{status}」",
        data={"id": alert_id, "status": status},
    )


class FeedbackIn(BaseModel):
    content: str
    category: Optional[str] = None


@router.post("/workspace/feedback", response_model=ResponseModel, summary="学员：提交一条反馈")
def submit_feedback(
    body: FeedbackIn,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    # 反馈是学生提的：老师、顾问、管理员都不从学生入口代提，
    # 免得出现「谁都能以学生名义写一条」的糊涂账。
    if me["role"] != "student":
        raise HTTPException(status_code=403, detail="反馈由学员本人提交")

    text = (body.content or "").strip()
    if len(text) < 4:
        raise HTTPException(status_code=400, detail="把问题写清楚一点（至少 4 个字），老师才好处理")
    if len(text) > 500:
        raise HTTPException(status_code=400, detail="内容请控制在 500 字以内")
    category = (body.category or "").strip()
    if category not in FB_CATEGORIES:
        category = "其他"

    # content 存一行摘要（列表里显示），detail 存全文（老师展开看）
    head = text.splitlines()[0][:40]
    cur = db.execute(
        "INSERT INTO student_feedback_ticket "
        "(student_id, category, content, detail, status, is_notified) "
        "VALUES (?,?,?,?,'待处理',0)",
        (me["id"], category, head, text),
    )
    db.commit()
    fid = cur.lastrowid
    log_service.write(
        db,
        actor=me,
        action="feedback_submit",
        summary=f"提交反馈：{category}｜{head}",
        detail=text[:300],
        target_type="feedback",
        target_id=fid,
    )
    return ResponseModel(
        msg="已提交，班主任回复后会在「我的反馈」里看到",
        data={"id": fid, "category": category, "status": "待处理"},
    )


class FeedbackHandleIn(BaseModel):
    status: str
    reply: Optional[str] = None


@router.post(
    "/workspace/feedback/{fid}/handle",
    response_model=ResponseModel,
    summary="班主任：回复 / 结案学生反馈",
)
def handle_feedback(
    fid: int,
    body: FeedbackHandleIn,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    # 学生反馈落到班主任手里：他清楚这个学生的情况，也知道该找教务还是宿管。
    if me["role"] != "teacher":
        raise HTTPException(status_code=403, detail="学生反馈由本班班主任回复，管理员只在数据后台查看")

    row = db.execute(
        "SELECT t.*, u.real_name, u.homeroom_teacher_id FROM student_feedback_ticket t "
        "JOIN sys_user u ON u.id = t.student_id WHERE t.id = ?",
        (fid,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="这条反馈不存在")
    if row["homeroom_teacher_id"] != me["id"]:
        raise HTTPException(status_code=403, detail="这条反馈不在你班上，不能处理")

    status = (body.status or "").strip()
    if status not in FB_STATUSES:
        raise HTTPException(status_code=400, detail="状态只能是 待处理 / 处理中 / 已解决")
    reply = (body.reply or "").strip()[:400]
    # 结案必须给学生一个答复，否则学生端只看到「已解决」三个字，等于没回
    if status == FB_DONE and not reply and not (row["solution"] or "").strip():
        raise HTTPException(
            status_code=400,
            detail="结案前写一句回复，学生会原样看到（例如：已联系宿管，明天上门维修）",
        )

    db.execute(
        "UPDATE student_feedback_ticket SET status = ?, solution = ?, handler_id = ?, "
        "handle_time = datetime('now','localtime'), "
        "is_notified = CASE WHEN ? <> '' THEN 1 ELSE is_notified END, "
        "update_time = datetime('now','localtime') WHERE id = ?",
        (status, reply or row["solution"], me["id"], reply, fid),
    )
    db.commit()
    log_service.write(
        db,
        actor=me,
        action="feedback_handle",
        summary=f"学生反馈：{row['real_name']} · {status}" + (f"｜{reply[:40]}" if reply else ""),
        detail=reply,
        target_type="feedback",
        target_id=fid,
    )
    return ResponseModel(
        msg=f"{row['real_name']} 的反馈已标记为「{status}」",
        data={"id": fid, "status": status},
    )


class JournalIn(BaseModel):
    content: str
    mood_tag: Optional[str] = None
    mood_score: Optional[int] = None
    sleep: Optional[str] = None
    stress_source: Optional[str] = None
    duration: Optional[str] = None


def _enum(value: Any, options: tuple, default: str) -> str:
    v = value.strip() if isinstance(value, str) else ""
    return v if v in options else default


@router.post("/workspace/journal", response_model=ResponseModel, summary="学员：写一篇心理周记")
def submit_journal(
    body: JournalIn,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    if me["role"] != "student":
        raise HTTPException(status_code=403, detail="心理周记由学员本人填写")

    text = (body.content or "").strip()
    if len(text) < 4:
        raise HTTPException(status_code=400, detail="写几句你现在的状态吧（至少 4 个字）")
    if len(text) > 500:
        raise HTTPException(status_code=400, detail="内容请控制在 500 字以内")
    try:
        score = int(body.mood_score) if body.mood_score is not None else 50
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="情绪分值要是 0~100 的数字")
    if not 0 <= score <= 100:
        raise HTTPException(status_code=400, detail="情绪分值要在 0~100 之间")

    tag = _enum(body.mood_tag, JR_TAGS, "其他")
    sleep = _enum(body.sleep, JR_SLEEPS, "一般")
    source = _enum(body.stress_source, JR_SOURCES, "其他")
    duration = _enum(body.duration, JR_DURATIONS, "今天")
    head = text.splitlines()[0][:60]

    cur = db.execute(
        "INSERT INTO student_psych_journal "
        "(student_id, mood_tag, mood_score, sleep, stress_source, duration, content, status) "
        "VALUES (?,?,?,?,?,?,?,'待跟进')",
        (me["id"], tag, score, sleep, source, duration, text),
    )
    jid = cur.lastrowid
    # 画像沉淀：最新标签 / 分值 / 情绪历史都跟着更新（历史最多 50 条）
    profile_engine.update_psych_profile(db, me["id"], tag, score)
    # 自评达到危机线，额外给班主任生成一条预警（与对话里的高危预警同口径）
    alert_id = None
    if score >= JR_ALERT_SCORE:
        alert_id = alert_engine.check_and_create_alert(
            db,
            me["id"],
            f"心理周记自评[分值 {score}]，原话：{text}",
            "高" if score >= 85 else "中",
            journal_id=jid,
        )
    log_service.write(
        db,
        actor=me,
        action="journal_submit",
        summary=f"心理周记：{tag} · 分值 {score}｜{head}",
        detail=f"睡眠 {sleep} · 压力 {source} · 持续 {duration}"[:300],
        target_type="psych_journal",
        target_id=jid,
    )
    msg = "已写进心理周记，班主任会在心理关怀里看到"
    if alert_id:
        msg += "；分值较高，已同步提醒班主任"
    return ResponseModel(
        msg=msg,
        data={"id": jid, "status": "待跟进", "alert_id": alert_id},
    )


class JournalHandleIn(BaseModel):
    status: str
    reply: Optional[str] = None


@router.post(
    "/workspace/journal/{jid}/handle",
    response_model=ResponseModel,
    summary="班主任：跟进 / 回复学生心理周记",
)
def handle_journal(
    jid: int,
    body: JournalHandleIn,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    if me["role"] != "teacher":
        raise HTTPException(status_code=403, detail="心理周记由本班班主任跟进，管理员只在数据后台查看")
    row = db.execute(
        "SELECT j.*, u.real_name, u.homeroom_teacher_id FROM student_psych_journal j "
        "JOIN sys_user u ON u.id = j.student_id WHERE j.id = ?",
        (jid,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="周记不存在")
    if row["homeroom_teacher_id"] != me["id"]:
        raise HTTPException(status_code=403, detail="这篇周记不在你班上，不能跟进")

    status = (body.status or "").strip()
    if status not in JR_STATUSES:
        raise HTTPException(status_code=400, detail="状态只能是 待跟进 / 跟进中 / 已跟进")
    reply = (body.reply or "").strip()[:400]
    if status == JR_DONE and not reply and not (row["handle_note"] or "").strip():
        raise HTTPException(
            status_code=400,
            detail="标为已跟进前写一句回复，学生能看到（例如：已约明天上午聊，先保证今晚休息）",
        )
    final_reply = reply or row["handle_note"]
    db.execute(
        "UPDATE student_psych_journal SET status = ?, handle_note = ?, handler_id = ?, "
        "handle_time = datetime('now','localtime'), update_time = datetime('now','localtime') "
        "WHERE id = ?",
        (status, final_reply, me["id"], jid),
    )
    # 反向同步：这篇周记若触发过预警，预警板也一起更新，避免两边状态打架
    _sync_journal_to_alert(db, jid, status, final_reply or "", me["id"])
    db.commit()
    log_service.write(
        db,
        actor=me,
        action="journal_handle",
        summary=f"心理周记：{row['real_name']} · {status}" + (f"｜{reply[:40]}" if reply else ""),
        detail=reply,
        target_type="psych_journal",
        target_id=jid,
    )
    return ResponseModel(
        msg=f"{row['real_name']} 的周记已标记为「{status}」",
        data={"id": jid, "status": status},
    )


@router.get("/my/logs", response_model=ResponseModel, summary="我的操作日志（只能看自己的）")
def my_logs(
    limit: int = 40,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    return ResponseModel(
        msg=f"{me['real_name']} 的最近 {limit} 条记录",
        data={
            "rows": log_service.recent(db, me["id"], max(1, min(limit, 100))),
            "today": log_service.today_stats(db, me["id"]),
            "role": me["role"],
            "role_label": me["role_label"],
        },
    )
