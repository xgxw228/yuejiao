"""操作日志（工作日报）。

这里只做三件事：写一条、按人读、给后台读全量。

写日志的口径统一成「谁 / 什么时候 / 对什么 / 做了什么 / 结果」，
这样学生查自己的请假进度、老师看自己批过谁、管理员追一条线索的来龙去脉，
都能用同一张表回答；管理员只有读权限，接口层面不提供改和删。
"""

import sqlite3
from datetime import datetime
from typing import Any, Optional

ACTION_LABELS = {
    "lead_create": "客户留资",
    "lead_repeat": "再次咨询",
    "lead_follow": "线索跟进",
    "lead_status": "线索状态",
    "leave_apply": "提交请假",
    "leave_approve": "请假审批",
    "leave_delete": "删除请假",
    "score_save": "成绩录入",
    "score_delete": "成绩删除",
    "chat": "咨询小粤同学",
    "leave_query": "查询请假进度",
    "account_create": "新增账户",
    "account_disable": "停用账户",
    "account_enable": "启用账户",
    "account_delete": "删除账户",
    "activity_create": "新建活动",
    "activity_status": "活动状态",
    "activity_delete": "删除活动",
    "activity_signup": "活动报名",
    "class_create": "新建班级",
    "class_teacher": "调整班主任",
    "alert_handle": "心理预警处理",
    "feedback_submit": "提交反馈",
    "feedback_handle": "反馈处理",
    "journal_submit": "写心理周记",
    "journal_handle": "心理周记跟进",
}

ROLE_LABELS = {
    "admin": "管理员",
    "teacher": "班主任",
    "staff": "顾问",
    "student": "学员",
    "parent": "家长",
    "anonymous": "访客",
}


def write(
    db: sqlite3.Connection,
    *,
    action: str,
    summary: str,
    actor: Optional[dict] = None,
    target_type: Optional[str] = None,
    target_id: Optional[Any] = None,
    detail: Optional[str] = None,
    result: str = "成功",
) -> None:
    """写一条日志。actor 传 auth_service.profile 的结果，匿名访客传 None。"""
    actor = actor or {}
    role = actor.get("role") or "anonymous"
    db.execute(
        "INSERT INTO op_log (actor_id, actor_name, actor_role, action, action_label, "
        "target_type, target_id, summary, detail, result, create_time) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            actor.get("id"),
            actor.get("real_name") or ("访客" if not actor else "—"),
            role,
            action,
            ACTION_LABELS.get(action, action),
            target_type,
            target_id,
            summary[:300],
            (detail or "")[:600],
            result,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    db.commit()


def _row(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "actor_id": r["actor_id"],
        "actor_name": r["actor_name"],
        "actor_role": r["actor_role"],
        "role_label": ROLE_LABELS.get(r["actor_role"] or "", r["actor_role"] or "—"),
        "action": r["action"],
        "action_label": r["action_label"] or ACTION_LABELS.get(r["action"], r["action"]),
        "target_type": r["target_type"],
        "target_id": r["target_id"],
        "summary": r["summary"],
        "detail": r["detail"] or "",
        "result": r["result"] or "成功",
        "time": r["create_time"],
        "time_short": (r["create_time"] or "")[5:16],
    }


def recent(db: sqlite3.Connection, actor_id: Any, limit: int = 40) -> list[dict]:
    rows = db.execute(
        "SELECT * FROM op_log WHERE actor_id = ? ORDER BY id DESC LIMIT ?",
        (actor_id, limit),
    ).fetchall()
    return [_row(r) for r in rows]


def today_stats(db: sqlite3.Connection, actor_id: Optional[Any] = None) -> dict:
    where = "date(create_time) = date('now','localtime')"
    args: list[Any] = []
    if actor_id is not None:
        where += " AND actor_id = ?"
        args.append(actor_id)
    total = db.execute(f"SELECT COUNT(*) FROM op_log WHERE {where}", args).fetchone()[0]
    by_action = {
        r["action"]: r["n"]
        for r in db.execute(
            f"SELECT action, COUNT(*) AS n FROM op_log WHERE {where} GROUP BY action", args
        )
    }
    return {"total": total, "by_action": by_action}


def query(
    db: sqlite3.Connection,
    *,
    page: int = 1,
    size: int = 30,
    action: Optional[str] = None,
    actor_id: Optional[int] = None,
    q: Optional[str] = None,
) -> dict:
    where, args = [], []
    if action:
        where.append("action = ?")
        args.append(action)
    if actor_id:
        where.append("actor_id = ?")
        args.append(actor_id)
    if q:
        where.append("(summary LIKE ? OR detail LIKE ? OR actor_name LIKE ?)")
        args += [f"%{q}%"] * 3
    w = (" WHERE " + " AND ".join(where)) if where else ""

    total = db.execute(f"SELECT COUNT(*) FROM op_log{w}", args).fetchone()[0]
    rows = [
        _row(r)
        for r in db.execute(
            f"SELECT * FROM op_log{w} ORDER BY id DESC LIMIT ? OFFSET ?",
            args + [size, (page - 1) * size],
        )
    ]
    actors = [
        {"id": r["actor_id"], "name": r["actor_name"], "role": r["actor_role"]}
        for r in db.execute(
            "SELECT actor_id, actor_name, actor_role, MAX(id) AS m FROM op_log "
            "WHERE actor_id IS NOT NULL GROUP BY actor_id ORDER BY m DESC"
        )
    ]
    return {
        "rows": rows,
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, (total + size - 1) // size),
        "actions": [{"key": k, "label": v} for k, v in ACTION_LABELS.items()],
        "actors": actors,
        "today": today_stats(db),
    }
