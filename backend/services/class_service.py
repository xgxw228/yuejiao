"""班级与班主任（一一对应）。

规则只有一条，但全系统都靠它：
- 一个班只有一位班主任，一位班主任只带一个班，不交叉；
- 学员挂在班上（sys_user.class_id），班主任由班决定；
- sys_user.homeroom_teacher_id 始终跟班的班主任同步——请假审批、成绩录入、
  越权判断都还看这一列，所以换老师时把学生的这一列一起改掉，权限就跟着走了；
- 顾问可以建班、调整某个班由谁带；管理员只看不改。

两类班：
- 常规班：正式学员（sys_user 里的 STUDENT）；
- 试听班：活动项目老师（如张老师）带的有联系方式的意向学员，成员来自客户线索
  （crm_lead.contact_info 非空、且不是「已流失」），按已签约 / 待签约分组。
  试听班不收正式学员，开户时班级下拉里也不会出现它。
"""

import sqlite3
from typing import Any, Optional

CLASS_PREFIX = "粤教"
DEFAULT_GRADE = "2025 级"
KIND_NORMAL = "常规班"
KIND_TRIAL = "试听班"
ACTIVITY_ROLE = "活动项目老师"

# 试听班成员的筛选口径：有联系方式、且没流失。
# 「已流失」就是用户说的"已丢失的客户学生"，不纳入班级。
TRIAL_WHERE = (
    "l.class_id = ? AND TRIM(COALESCE(l.contact_info, '')) <> '' "
    "AND COALESCE(l.status, '新增意向') <> '已流失'"
)


def _active_students_sql() -> str:
    return (
        "SELECT COUNT(*) FROM sys_user s WHERE s.class_id = c.id "
        "AND s.user_type = 'STUDENT' AND COALESCE(s.status,'正常') <> '已删除'"
    )


def get_class(db: sqlite3.Connection, class_id: Any) -> Optional[sqlite3.Row]:
    if not class_id:
        return None
    return db.execute("SELECT * FROM school_class WHERE id = ?", (int(class_id),)).fetchone()


def teacher_class(db: sqlite3.Connection, teacher_id: Any) -> Optional[sqlite3.Row]:
    if not teacher_id:
        return None
    return db.execute(
        "SELECT * FROM school_class WHERE teacher_id = ? ORDER BY id LIMIT 1", (int(teacher_id),)
    ).fetchone()


def student_class(db: sqlite3.Connection, student_id: Any) -> Optional[sqlite3.Row]:
    if not student_id:
        return None
    return db.execute(
        "SELECT c.* FROM sys_user s JOIN school_class c ON c.id = s.class_id "
        "WHERE s.id = ?",
        (int(student_id),),
    ).fetchone()


def student_count(db: sqlite3.Connection, class_id: Any) -> int:
    row = db.execute(
        "SELECT COUNT(*) FROM sys_user WHERE class_id = ? AND user_type = 'STUDENT' "
        "AND COALESCE(status,'正常') <> '已删除'",
        (int(class_id),),
    ).fetchone()
    return int(row[0] or 0)


def _row(db: sqlite3.Connection, r: sqlite3.Row) -> dict:
    teacher = (
        db.execute(
            "SELECT real_name, contact_info, status FROM sys_user WHERE id = ?",
            (r["teacher_id"],),
        ).fetchone()
        if r["teacher_id"]
        else None
    )
    kind = _kind_of(r)
    row = {
        "id": r["id"],
        "name": r["name"],
        "grade": r["grade"] or "",
        "kind": kind,
        "teacher_id": r["teacher_id"],
        "teacher": (teacher["real_name"] if teacher else "") or "待分配",
        "teacher_status": (teacher["status"] if teacher else None) or "",
        "students": student_count(db, r["id"]),
        "note": r["note"] or "",
    }
    if kind == KIND_TRIAL:
        counts = trial_counts(db, r["id"])
        row["students"] = counts["total"]  # 试听班没有正式学员，人数按名单算
        row["trial"] = counts
    return row


def _kind_of(r: sqlite3.Row) -> str:
    """老库没有 kind 列时按常规班处理。"""
    try:
        return (r["kind"] or KIND_NORMAL) if "kind" in r.keys() else KIND_NORMAL
    except (IndexError, TypeError):
        return KIND_NORMAL


def trial_counts(db: sqlite3.Connection, class_id: Any) -> dict:
    """试听班人数：待签约（新增意向 + 跟进中）/ 已签约；已流失不算。"""
    pending = db.execute(
        f"SELECT COUNT(*) FROM crm_lead l WHERE {TRIAL_WHERE} "
        "AND COALESCE(l.status,'') IN ('新增意向', '跟进中')",
        (int(class_id),),
    ).fetchone()[0]
    signed = db.execute(
        f"SELECT COUNT(*) FROM crm_lead l WHERE {TRIAL_WHERE} AND l.status = '已签约'",
        (int(class_id),),
    ).fetchone()[0]
    return {"pending": int(pending or 0), "signed": int(signed or 0), "total": int(pending or 0) + int(signed or 0)}


def trial_members(db: sqlite3.Connection, class_id: Any) -> dict:
    """试听班的名单，按「待签约 / 已签约」分组；已流失的不出现。"""
    rows = db.execute(
        f"SELECT l.*, u.real_name AS owner_name FROM crm_lead l "
        f"LEFT JOIN sys_user u ON u.id = l.owner_employee_id "
        f"WHERE {TRIAL_WHERE} "
        f"ORDER BY CASE l.status WHEN '已签约' THEN 1 ELSE 0 END, "
        f"l.update_time DESC, l.id DESC",
        (int(class_id),),
    ).fetchall()
    out = {"pending": [], "signed": []}
    for r in rows:
        item = {
            "id": r["id"],
            "name": r["customer_name"] or "未留名",
            "phone": r["contact_info"] or "",
            "status": r["status"] or "新增意向",
            "brief": (r["background_info"] or "").strip(),
            "owner": r["owner_name"] or "未分配",
            "time": (r["update_time"] or r["create_time"] or "")[:16],
            "history": (r["follow_up_history"] or "").strip(),
        }
        out["signed" if item["status"] == "已签约" else "pending"].append(item)
    return out


def list_classes(db: sqlite3.Connection) -> list[dict]:
    return [
        _row(db, r)
        for r in db.execute(
            "SELECT * FROM school_class ORDER BY id"
        ).fetchall()
    ]


def class_brief(db: sqlite3.Connection, r: Optional[sqlite3.Row]) -> str:
    """班级一句话：「粤教1班 · 李老师」；没有班时给空串。"""
    if not r:
        return ""
    t = db.execute("SELECT real_name FROM sys_user WHERE id = ?", (r["teacher_id"],)).fetchone()
    name = t["real_name"] if t else "待分配班主任"
    return f"{r['name']} · {name}"


def create_class(
    db: sqlite3.Connection,
    name: str,
    teacher_id: Optional[int] = None,
    grade: Optional[str] = None,
    created_by: Optional[int] = None,
    kind: str = KIND_NORMAL,
) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("请填写班级名称")
    if len(name) > 20:
        raise ValueError("班级名称最多 20 个字")
    if db.execute("SELECT 1 FROM school_class WHERE name = ?", (name,)).fetchone():
        raise ValueError(f"班级「{name}」已经存在")

    if teacher_id:
        teacher = _require_teacher(db, int(teacher_id))
        if (teacher["employee_role"] or "") == ACTIVITY_ROLE and kind == KIND_NORMAL:
            raise ValueError("活动项目老师带的是试听班，不占常规班")
        taken = teacher_class(db, teacher["id"])
        if taken:
            raise ValueError(
                f"{teacher['real_name']} 已经在带 {taken['name']}，一个老师只能带一个班，"
                "先把原来的班交给别人"
            )

    cur = db.execute(
        "INSERT INTO school_class (name, grade, kind, teacher_id, created_by, create_time, update_time) "
        "VALUES (?, ?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))",
        (
            name,
            (grade or "").strip() or DEFAULT_GRADE,
            kind,
            int(teacher_id) if teacher_id else None,
            created_by,
        ),
    )
    db.commit()
    return _row(db, db.execute("SELECT * FROM school_class WHERE id = ?", (cur.lastrowid,)).fetchone())


def _require_teacher(db: sqlite3.Connection, teacher_id: int) -> sqlite3.Row:
    from services import auth_service

    row = db.execute(
        "SELECT * FROM sys_user WHERE id = ? AND user_type = 'EMPLOYEE'", (int(teacher_id),)
    ).fetchone()
    if not row or (row["status"] or "正常") != "正常":
        raise ValueError("所选老师不存在或已停用")
    students = db.execute(
        "SELECT COUNT(*) FROM sys_user WHERE homeroom_teacher_id = ? AND user_type = 'STUDENT'",
        (row["id"],),
    ).fetchone()[0]
    has_class = bool(teacher_class(db, row["id"]))
    if auth_service.resolve_role(row, students, has_class) != "teacher":
        raise ValueError("只能选班主任来带班")
    return row


def _set_teacher(db: sqlite3.Connection, class_id: int, teacher_id: Any) -> int:
    """把班交给某位老师，并把班上的学生一起转过去，返回转过去的学生数。"""
    db.execute(
        "UPDATE school_class SET teacher_id = ?, update_time = datetime('now','localtime') WHERE id = ?",
        (teacher_id, class_id),
    )
    return db.execute(
        "UPDATE sys_user SET homeroom_teacher_id = ?, update_time = datetime('now','localtime') "
        "WHERE class_id = ? AND user_type = 'STUDENT'",
        (teacher_id, class_id),
    ).rowcount


def assign_teacher(db: sqlite3.Connection, class_id: int, teacher_id: int) -> dict:
    """把某个班交给某位班主任：班上的学生一起转过去。

    如果这位老师本来带着别的班，两个班就对调老师——这样「一个老师只带一个班」
    始终成立，3 个班 3 位老师也能随时互换，不会卡住。
    """
    cls = get_class(db, class_id)
    if not cls:
        raise LookupError("班级不存在")
    teacher = _require_teacher(db, teacher_id)

    # 班型跟老师身份要对得上：试听班只交给活动项目老师，常规班不给活动项目老师
    is_trial = (cls["kind"] or KIND_NORMAL) == KIND_TRIAL
    is_activity = (teacher["employee_role"] or "") == ACTIVITY_ROLE
    if is_trial != is_activity:
        raise ValueError(
            "试听班只能交给活动项目老师；常规班也不要交给活动项目老师"
        )

    before = cls["teacher_id"]
    if before and int(before) == teacher["id"]:
        return {
            "class": _row(db, cls),
            "moved": 0,
            "before_teacher": teacher["real_name"],
            "teacher": teacher["real_name"],
            "swapped": None,
            "swapped_moved": 0,
        }

    before_name = ""
    if before:
        t = db.execute("SELECT real_name FROM sys_user WHERE id = ?", (before,)).fetchone()
        before_name = t["real_name"] if t else ""

    taken = teacher_class(db, teacher["id"])
    swapped, swapped_moved = None, 0
    if taken and taken["id"] != cls["id"]:
        if not before:
            raise ValueError(
                f"{teacher['real_name']} 已经在带 {taken['name']}。这个班还没有班主任，"
                "请先给它指定一位老师，再和这位老师对调"
            )
        # 对调：新老师来这个班，原班主任去带新老师原来的班
        swapped = taken["name"]
        swapped_moved = _set_teacher(db, taken["id"], before)

    moved = _set_teacher(db, cls["id"], teacher["id"])
    db.commit()

    row = db.execute("SELECT * FROM school_class WHERE id = ?", (cls["id"],)).fetchone()
    return {
        "class": _row(db, row),
        "moved": moved,
        "before_teacher": before_name,
        "teacher": teacher["real_name"],
        "swapped": swapped,
        "swapped_moved": swapped_moved,
    }


def ensure_classes(db: sqlite3.Connection) -> None:
    """首次启动（班级表为空）时，按现有班主任把班建起来，老数据不用手工搬。

    只在「一个班都没有」时补：之后顾问删了 / 换了老师的班，不会被重新造出来。
    班级表已经有数据时，只做一次修复——把没挂班的学生按班主任挂到他的班上。
    活动项目老师不占常规班号：他带的是试听班，成员来自有联系方式的线索。
    """
    from services import auth_service

    total = db.execute("SELECT COUNT(*) FROM school_class").fetchone()[0]
    teachers = []
    for row in db.execute(
        "SELECT * FROM sys_user WHERE user_type = 'EMPLOYEE' "
        "AND COALESCE(status,'正常') = '正常' ORDER BY id"
    ):
        if (row["employee_role"] or "") == ACTIVITY_ROLE:
            continue
        students = db.execute(
            "SELECT COUNT(*) FROM sys_user WHERE homeroom_teacher_id = ? AND user_type = 'STUDENT'",
            (row["id"],),
        ).fetchone()[0]
        if auth_service.resolve_role(row, students) == "teacher":
            teachers.append((row, students))

    if not total:
        # 手上有人学生的老师排前面，拿 1 班、2 班、3 班……
        teachers.sort(key=lambda x: (-x[1], x[0]["id"]))
        for idx, (row, _) in enumerate(teachers, start=1):
            db.execute(
                "INSERT INTO school_class (name, grade, kind, teacher_id, note, create_time, update_time) "
                "VALUES (?, ?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))",
                (f"{CLASS_PREFIX}{idx}班", DEFAULT_GRADE, KIND_NORMAL, row["id"], "系统按现有班主任初始化"),
            )
        db.commit()

    # 补挂：学生有班主任但没班级 → 挂到这个班主任的班
    for row in db.execute(
        "SELECT id, homeroom_teacher_id FROM sys_user "
        "WHERE user_type = 'STUDENT' AND class_id IS NULL AND homeroom_teacher_id IS NOT NULL"
    ).fetchall():
        cls = teacher_class(db, row["homeroom_teacher_id"])
        if cls:
            db.execute("UPDATE sys_user SET class_id = ? WHERE id = ?", (cls["id"], row["id"]))
    db.commit()

    ensure_trial_class(db)


def ensure_trial_class(db: sqlite3.Connection) -> Optional[sqlite3.Row]:
    """活动项目老师带一个试听班：没有就建，并把有联系方式、未流失的线索挂进去。"""
    teacher = db.execute(
        "SELECT * FROM sys_user WHERE user_type = 'EMPLOYEE' AND employee_role = ? "
        "AND COALESCE(status,'正常') = '正常' ORDER BY id LIMIT 1",
        (ACTIVITY_ROLE,),
    ).fetchone()
    if not teacher:
        return None

    cls = db.execute(
        "SELECT * FROM school_class WHERE teacher_id = ? ORDER BY id LIMIT 1", (teacher["id"],)
    ).fetchone()
    if not cls:
        db.execute(
            "INSERT INTO school_class (name, grade, kind, teacher_id, note, create_time, update_time) "
            "VALUES (?, ?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))",
            (
                f"{CLASS_PREFIX}试听班",
                DEFAULT_GRADE,
                KIND_TRIAL,
                teacher["id"],
                "活动项目老师带班：有联系方式、未流失的意向学员自动进班",
            ),
        )
        db.commit()
        cls = db.execute(
            "SELECT * FROM school_class WHERE teacher_id = ? ORDER BY id LIMIT 1", (teacher["id"],)
        ).fetchone()

    sync_trial_members(db, cls["id"])
    return cls


def sync_trial_members(db: sqlite3.Connection, class_id: Any) -> int:
    """把线索名单同步进试听班：有电话且没流失的进班，流失 / 没电话的移出。

    线索状态一变（签约、流失），名单跟着变，不用手工维护。
    """
    cid = int(class_id)
    db.execute(
        "UPDATE crm_lead SET class_id = NULL WHERE class_id = ? "
        "AND (TRIM(COALESCE(contact_info,'')) = '' OR COALESCE(status,'') = '已流失')",
        (cid,),
    )
    n = db.execute(
        "UPDATE crm_lead SET class_id = ? WHERE TRIM(COALESCE(contact_info,'')) <> '' "
        "AND COALESCE(status,'新增意向') <> '已流失' AND COALESCE(class_id, 0) <> ?",
        (cid, cid),
    ).rowcount
    db.commit()
    return n


def attach_lead(db: sqlite3.Connection, lead_id: Any) -> None:
    """线索新增 / 状态变化后，立刻决定它在不在试听班。

    有电话、没流失 → 进班；流失或没留电话 → 移出。这样顾问在页面上把状态
    改成「已流失」，张老师的名单里当场就少一个人，不用等重启。
    """
    cls = db.execute(
        "SELECT id FROM school_class WHERE kind = ? ORDER BY id LIMIT 1", (KIND_TRIAL,)
    ).fetchone()
    if not cls:
        return
    db.execute(
        "UPDATE crm_lead SET class_id = CASE WHEN TRIM(COALESCE(contact_info,'')) <> '' "
        "AND COALESCE(status,'新增意向') <> '已流失' THEN ? ELSE NULL END WHERE id = ?",
        (cls["id"], int(lead_id)),
    )
    db.commit()
