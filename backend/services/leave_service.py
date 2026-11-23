"""请假审批服务：班主任归属、待办查询、审批落库。

状态机：待审批 → 已通过 / 已驳回。

设计要点：
1. 班主任关系落在 sys_user.homeroom_teacher_id（学生记录指向员工记录）。
2. 申请一提交就把 approver_id 写成该学生的班主任，所以「待审批」也能立刻说清
   「在等谁批」，不需要等审批时才补人。
3. 审批完成写 approve_time / approve_comment，前端和学生查询都靠它区分
   「已分配但还没批」和「已经批完了」。
"""

import sqlite3
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException

PENDING = "待审批"
APPROVED = "已通过"
REJECTED = "已驳回"
STATUSES = (PENDING, APPROVED, REJECTED)


# ---------------------------------------------------------------------------
# 时间小工具
# ---------------------------------------------------------------------------

def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("T", " ")
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def days_of(start: Any, end: Any) -> int:
    """请假天数，按自然日含首尾计算（当天请一天 = 1）。"""
    s, e = _parse_dt(start), _parse_dt(end)
    if not s or not e:
        return 1
    return max((e.date() - s.date()).days + 1, 1)


def _short(value: Any) -> Optional[str]:
    dt = _parse_dt(value)
    return dt.strftime("%m-%d %H:%M") if dt else None


def _long(value: Any) -> Optional[str]:
    dt = _parse_dt(value)
    return dt.strftime("%Y-%m-%d %H:%M") if dt else None


# ---------------------------------------------------------------------------
# 班主任归属
# ---------------------------------------------------------------------------

def teacher_of(db: sqlite3.Connection, student_id: Any) -> Optional[dict]:
    """学生 -> 班主任。没配班主任时兜底到教务，保证审批链不断。"""
    try:
        sid = int(float(student_id))
    except (TypeError, ValueError):
        return None

    row = db.execute(
        """SELECT t.id, t.real_name, t.department
           FROM sys_user s JOIN sys_user t ON t.id = s.homeroom_teacher_id
           WHERE s.id = ?""",
        (sid,),
    ).fetchone()
    if not row:
        row = db.execute(
            """SELECT id, real_name, department FROM sys_user
               WHERE user_type = 'EMPLOYEE' AND department LIKE '%教务%'
               ORDER BY id LIMIT 1"""
        ).fetchone()
    if not row:
        row = db.execute(
            "SELECT id, real_name, department FROM sys_user WHERE user_type = 'EMPLOYEE' ORDER BY id LIMIT 1"
        ).fetchone()
    if not row:
        return None
    return {"id": row["id"], "name": row["real_name"], "department": row["department"]}


def is_teacher(db: sqlite3.Connection, teacher_id: Any) -> bool:
    row = db.execute(
        "SELECT 1 FROM sys_user WHERE homeroom_teacher_id = ? LIMIT 1", (teacher_id,)
    ).fetchone()
    return bool(row)


def is_admin(db: sqlite3.Connection, user_id: Any) -> bool:
    """管理员/领导：可以跨班主任审批（演示里用来体现"全校视角"）。"""
    row = db.execute(
        "SELECT employee_role FROM sys_user WHERE id = ?", (user_id,)
    ).fetchone()
    return bool(row and (row["employee_role"] or "") in ("管理员", "领导"))


def teacher_profile(db: sqlite3.Connection, teacher_id: Any) -> Optional[dict]:
    row = db.execute(
        "SELECT id, real_name, department, employee_role FROM sys_user WHERE id = ?",
        (teacher_id,),
    ).fetchone()
    if not row:
        return None
    students = db.execute(
        "SELECT real_name FROM sys_user WHERE homeroom_teacher_id = ? ORDER BY id",
        (teacher_id,),
    ).fetchall()
    return {
        "id": row["id"],
        "name": row["real_name"],
        "department": row["department"],
        "role": row["employee_role"],
        "is_homeroom": bool(students),
        "students": [s["real_name"] for s in students],
    }


# ---------------------------------------------------------------------------
# 记录包装（把 id 换成能直接念给用户听的字段）
# ---------------------------------------------------------------------------

def enrich(db: sqlite3.Connection, row: Any) -> dict:
    data = dict(row)

    student = db.execute(
        "SELECT real_name, department FROM sys_user WHERE id = ?", (data.get("student_id"),)
    ).fetchone()
    teacher = None
    if data.get("approver_id"):
        teacher = db.execute(
            "SELECT real_name, department FROM sys_user WHERE id = ?", (data["approver_id"],)
        ).fetchone()

    data["student_name"] = student["real_name"] if student else f"学生{data.get('student_id')}"
    data["student_class"] = student["department"] if student else ""
    data["approver_name"] = teacher["real_name"] if teacher else None
    data["days"] = days_of(data.get("start_time"), data.get("end_time"))

    status = data.get("status")
    data["is_pending"] = status == PENDING
    if data["approver_name"]:
        data["approver_desc"] = f"班主任 {data['approver_name']}"
        if status == PENDING:
            data["status_text"] = f"待{data['approver_name']}审批"
        else:
            data["status_text"] = f"{status}（{data['approver_name']}审批）"
    else:
        data["approver_desc"] = "尚未分配班主任"
        data["status_text"] = status

    for key in ("start_time", "end_time", "create_time", "approve_time"):
        data[f"{key}_short"] = _short(data.get(key))
    data["start_time_text"] = _long(data.get("start_time"))
    data["end_time_text"] = _long(data.get("end_time"))
    data["approve_time_text"] = _long(data.get("approve_time"))

    if data.get("start_time") and data.get("end_time"):
        start, end = _parse_dt(data["start_time"]), _parse_dt(data["end_time"])
        if start and end:
            if start.date() == end.date():
                data["period_text"] = f"{start:%m-%d} {start:%H:%M}~{end:%H:%M}（1 天）"
            else:
                data["period_text"] = (
                    f"{start:%m-%d}~{end:%m-%d} 共 {data['days']} 天"
                )
    return data


def get_record(db: sqlite3.Connection, record_id: int) -> Optional[dict]:
    row = db.execute(
        "SELECT * FROM student_admin_service WHERE id = ?", (record_id,)
    ).fetchone()
    return enrich(db, row) if row else None


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------

def pending_for(db: sqlite3.Connection, teacher_id: Any) -> list[dict]:
    rows = db.execute(
        """SELECT * FROM student_admin_service
           WHERE status = ? AND approver_id = ?
           ORDER BY start_time ASC, id ASC""",
        (PENDING, teacher_id),
    ).fetchall()
    return [enrich(db, r) for r in rows]


def handled_by(db: sqlite3.Connection, teacher_id: Any, limit: int = 8) -> list[dict]:
    rows = db.execute(
        """SELECT * FROM student_admin_service
           WHERE status IN (?, ?) AND approver_id = ?
           ORDER BY COALESCE(approve_time, update_time) DESC, id DESC
           LIMIT ?""",
        (APPROVED, REJECTED, teacher_id, limit),
    ).fetchall()
    return [enrich(db, r) for r in rows]


def history_of_student(db: sqlite3.Connection, student_id: Any, limit: int = 20) -> list[dict]:
    rows = db.execute(
        """SELECT * FROM student_admin_service
           WHERE student_id = ? ORDER BY id DESC LIMIT ?""",
        (student_id, limit),
    ).fetchall()
    return [enrich(db, r) for r in rows]


def summary(db: sqlite3.Connection, teacher_id: Any) -> dict:
    profile = teacher_profile(db, teacher_id) or {
        "id": teacher_id, "name": "未知用户", "department": None,
        "role": None, "is_homeroom": False, "students": [],
    }
    pending = db.execute(
        "SELECT COUNT(*) FROM student_admin_service WHERE status = ? AND approver_id = ?",
        (PENDING, teacher_id),
    ).fetchone()[0]
    handled = db.execute(
        "SELECT COUNT(*) FROM student_admin_service WHERE status IN (?, ?) AND approver_id = ?",
        (APPROVED, REJECTED, teacher_id),
    ).fetchone()[0]
    return {
        "scope": "self",
        "approver_id": teacher_id,
        "approver_name": profile["name"],
        "department": profile["department"],
        "is_homeroom": profile["is_homeroom"],
        "students": profile["students"],
        "pending": pending,
        "handled": handled,
    }


# ---------------------------------------------------------------------------
# 管理员视角（全校，不按班主任过滤）
# ---------------------------------------------------------------------------

def pending_all(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        """SELECT * FROM student_admin_service
           WHERE status = ? ORDER BY start_time ASC, id ASC""",
        (PENDING,),
    ).fetchall()
    return [enrich(db, r) for r in rows]


def handled_all(db: sqlite3.Connection, limit: int = 8) -> list[dict]:
    rows = db.execute(
        """SELECT * FROM student_admin_service
           WHERE status IN (?, ?)
           ORDER BY COALESCE(approve_time, update_time) DESC, id DESC LIMIT ?""",
        (APPROVED, REJECTED, limit),
    ).fetchall()
    return [enrich(db, r) for r in rows]


def summary_all(db: sqlite3.Connection, user_id: Any) -> dict:
    user = db.execute(
        "SELECT real_name, department FROM sys_user WHERE id = ?", (user_id,)
    ).fetchone()
    pending = db.execute(
        "SELECT COUNT(*) FROM student_admin_service WHERE status = ?", (PENDING,)
    ).fetchone()[0]
    handled = db.execute(
        "SELECT COUNT(*) FROM student_admin_service WHERE status IN (?, ?)",
        (APPROVED, REJECTED),
    ).fetchone()[0]
    students = db.execute(
        "SELECT real_name FROM sys_user WHERE user_type = 'STUDENT' ORDER BY id"
    ).fetchall()
    return {
        "scope": "all",
        "approver_id": user_id,
        "approver_name": user["real_name"] if user else "未知用户",
        "department": (user["department"] if user else None),
        "is_homeroom": True,          # 管理员视同有权限，前端不必再引导切换身份
        "is_admin_view": True,
        "students": [s["real_name"] for s in students],
        "pending": pending,
        "handled": handled,
    }


def teachers(db: sqlite3.Connection) -> list[dict]:
    """所有带学生的班主任 + 各自的待办数（供前端切换演示）。"""
    rows = db.execute(
        """SELECT t.id, t.real_name, t.department,
                  (SELECT COUNT(*) FROM student_admin_service s
                    WHERE s.status = ? AND s.approver_id = t.id) AS pending,
                  (SELECT COUNT(*) FROM sys_user u
                    WHERE u.homeroom_teacher_id = t.id) AS students
           FROM sys_user t
           WHERE t.user_type = 'EMPLOYEE'
             AND EXISTS (SELECT 1 FROM sys_user u WHERE u.homeroom_teacher_id = t.id)
           ORDER BY t.id""",
        (PENDING,),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "name": r["real_name"],
            "department": r["department"],
            "pending": r["pending"],
            "students": r["students"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# 审批
# ---------------------------------------------------------------------------

def approve(
    db: sqlite3.Connection,
    record_id: int,
    approver_id: Any,
    approved: bool = True,
    comment: Optional[str] = None,
) -> dict:
    row = db.execute(
        "SELECT * FROM student_admin_service WHERE id = ?", (record_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"请假申请 {record_id} 不存在")

    if row["status"] != PENDING:
        who = ""
        if row["approver_id"]:
            t = db.execute(
                "SELECT real_name FROM sys_user WHERE id = ?", (row["approver_id"],)
            ).fetchone()
            who = f"（{t['real_name']}）" if t else ""
        raise HTTPException(
            status_code=400,
            detail=f"该申请已处理{who}，当前状态：{row['status']}",
        )

    try:
        approver_id = int(float(approver_id))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="缺少审批人 ID，无法确认审批身份")

    if is_admin(db, approver_id):
        raise HTTPException(
            status_code=403,
            detail="请假统一由学生所在班主任审批，管理员不代批（在数据后台可查看全量）",
        )

    # 归属只看学生档案上的 homeroom_teacher_id，不看申请单上的 approver_id：
    # 单子字段可能被改过，师生关系才是权限依据。
    owner = teacher_of(db, row["student_id"]) or {}
    if int(owner.get("id") or 0) != approver_id:
        owner_name = owner.get("name") or "其他老师"
        raise HTTPException(
            status_code=403,
            detail=f"该申请由班主任{owner_name}负责，你不是这名学生的班主任",
        )

    new_status = APPROVED if approved else REJECTED
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        """UPDATE student_admin_service
           SET status = ?, approver_id = ?, approve_time = ?,
               approve_comment = ?, update_time = ?
           WHERE id = ?""",
        (new_status, approver_id, now, (comment or "").strip() or None, now, record_id),
    )
    db.commit()
    return get_record(db, record_id)
