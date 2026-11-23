"""账户管理（前缀 /api/accounts）。

谁管谁，由角色 + 归属共同决定：
- 管理员：看全部班主任 / 顾问 / 学员；可开班主任、顾问账户；可停用 / 启用 / 删除；
- 顾问：只看自己开的学员；可开学员账户并指定班主任；停用启用删除都不给（要恢复找管理员）；
- 班主任、学员：没有这个入口，接口 403。

停用是软状态（status='停用'）：账号还在、还能被管理员启用，但登录直接被拦；
删除也是软删（status='已删除' + 用户名改写成 deleted_<id>_<原名>），
这样历史请假 / 成绩 / 日志不会断，原用户名还能重新开户。
"""

import re
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from database import get_db
from models.base import ResponseModel
from services import auth_service, class_service, log_service

router = APIRouter()

USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,19}$")
ROLE_LABEL = {"teacher": "班主任", "staff": "顾问", "student": "学员"}
DEPARTMENTS = {
    "teacher": "留学事业部 · 咨询组",
    "staff": "留学事业部 · 咨询组",
    "student": "国际学院 2026 级 · 方向待定",
}


def _me(db: sqlite3.Connection, authorization: Optional[str]) -> dict:
    payload = auth_service.read_token(authorization)
    if not payload:
        raise HTTPException(status_code=401, detail="请先登录")
    me = auth_service.profile(db, payload.get("uid"))
    if not me:
        raise HTTPException(status_code=401, detail="登录信息已失效，请重新登录")
    return me


def _require_manager(me: dict) -> None:
    if me["role"] not in ("admin", "staff"):
        raise HTTPException(status_code=403, detail="只有管理员和顾问可以管理账户")


def _role_of(db: sqlite3.Connection, row: sqlite3.Row) -> str:
    students = (
        db.execute(
            "SELECT COUNT(*) FROM sys_user WHERE homeroom_teacher_id = ? AND user_type = 'STUDENT'",
            (row["id"],),
        ).fetchone()[0]
        if (row["user_type"] or "").upper() == "EMPLOYEE"
        else 0
    )
    has_class = bool(
        db.execute("SELECT 1 FROM school_class WHERE teacher_id = ?", (row["id"],)).fetchone()
    ) if (row["user_type"] or "").upper() == "EMPLOYEE" else False
    return auth_service.resolve_role(row, students, has_class)


def _teacher_name(db: sqlite3.Connection, tid) -> str:
    if not tid:
        return ""
    t = db.execute("SELECT real_name FROM sys_user WHERE id = ?", (tid,)).fetchone()
    return t["real_name"] if t else ""


def _teacher_options(db: sqlite3.Connection) -> list[dict]:
    """在职班主任 + 他们现在带的班（一个老师最多一个班）。"""
    rows = []
    for r in db.execute(
        "SELECT * FROM sys_user WHERE user_type = 'EMPLOYEE' "
        "AND COALESCE(status,'正常') = '正常' ORDER BY id"
    ):
        if _role_of(db, r) != "teacher":
            continue
        cls = class_service.teacher_class(db, r["id"])
        rows.append(
            {
                "id": r["id"],
                "name": r["real_name"],
                "dept": r["department"] or "",
                # 试听班只交给活动项目老师，常规班不给活动项目老师，避免两边责任串味
                "is_activity": (r["employee_role"] or "") == class_service.ACTIVITY_ROLE,
                "class_id": cls["id"] if cls else None,
                "class_name": cls["name"] if cls else "",
                "class_kind": (cls["kind"] or class_service.KIND_NORMAL) if cls else "",
                "students": db.execute(
                    "SELECT COUNT(*) FROM sys_user WHERE homeroom_teacher_id = ?",
                    (r["id"],),
                ).fetchone()[0],
            }
        )
    return rows


def _row(db: sqlite3.Connection, r: sqlite3.Row) -> dict:
    role = _role_of(db, r)
    cls = None
    if role == "student":
        cls = class_service.student_class(db, r["id"])
    elif role == "teacher":
        cls = class_service.teacher_class(db, r["id"])
    role_label = ROLE_LABEL.get(role, role)
    trial = None
    if cls is not None and (cls["kind"] or class_service.KIND_NORMAL) == class_service.KIND_TRIAL:
        # 活动项目老师带的是试听班，不能显示成「班主任 · 名下 0 人」
        role_label = "活动项目老师"
        trial = class_service.trial_counts(db, cls["id"])
    return {
        "id": r["id"],
        "username": r["username"],
        "name": r["real_name"],
        "role": role,
        "role_label": role_label,
        "dept": r["department"] or "—",
        "contact": r["contact_info"] or "",
        "status": r["status"] or "正常",
        "disabled": (r["status"] or "正常") != "正常",
        "teacher": _teacher_name(db, r["homeroom_teacher_id"]),
        "class_id": cls["id"] if cls else None,
        "class_name": cls["name"] if cls else "",
        "class_kind": (cls["kind"] or class_service.KIND_NORMAL) if cls else "",
        "class_teacher": _teacher_name(db, cls["teacher_id"]) if cls else "",
        "trial": trial,
        "created_by": r["created_by"],
        "students": (
            db.execute(
                "SELECT COUNT(*) FROM sys_user WHERE homeroom_teacher_id = ? AND user_type = 'STUDENT'",
                (r["id"],),
            ).fetchone()[0]
            if role == "teacher"
            else 0
        ),
    }


# ---------------------------------------------------------------------------
# 老师下拉（顾问开学生时选班主任）
# 必须放在 /{uid} 之前，否则 "teachers" 会被当成 int 解析
# ---------------------------------------------------------------------------
@router.get("/teachers", response_model=ResponseModel, summary="可选班主任（开户时分配）")
def list_teachers(
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    _require_manager(me)
    rows = _teacher_options(db)
    return ResponseModel(msg=f"{len(rows)} 位班主任可选", data=rows)


# ---------------------------------------------------------------------------
# 列表
# ---------------------------------------------------------------------------
@router.get("", response_model=ResponseModel, summary="账户列表（按身份限定范围）")
def list_accounts(
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    _require_manager(me)

    if me["role"] == "admin":
        where = (
            "user_type IN ('EMPLOYEE','STUDENT') AND id <> ? "
            "AND COALESCE(status,'正常') <> '已删除' "
            "AND COALESCE(employee_role,'') NOT IN ('管理员','领导')"
        )
        args = (me["id"],)
        note = "管理员可开班主任 / 顾问账户，可停用、启用、删除"
    else:
        where = (
            "user_type = 'STUDENT' AND created_by = ? "
            "AND COALESCE(status,'正常') <> '已删除'"
        )
        args = (me["id"],)
        note = "顾问只能开学员账户，选班级就定了班主任；停用 / 删除由管理员处理"

    rows = [_row(db, r) for r in db.execute(f"SELECT * FROM sys_user WHERE {where} ORDER BY id", args)]
    rows.sort(key=lambda x: ({"teacher": 0, "staff": 1, "student": 2}.get(x["role"], 3), x["id"]))

    teachers = _teacher_options(db) if me["role"] in ("staff", "admin") else []
    classes = class_service.list_classes(db)

    return ResponseModel(
        msg=f"共 {len(rows)} 个账户",
        data={
            "rows": rows,
            "teachers": teachers,
            "classes": classes,
            "role": me["role"],
            "can_create": ["teacher", "staff"] if me["role"] == "admin" else ["student"],
            "can_toggle": me["role"] == "admin",
            "can_delete": me["role"] == "admin",
            "can_manage_class": me["role"] == "staff",
            "note": note,
            "stats": {
                "total": len(rows),
                "active": sum(1 for x in rows if not x["disabled"]),
                "disabled": sum(1 for x in rows if x["disabled"]),
            },
        },
    )


# ---------------------------------------------------------------------------
# 开户
# ---------------------------------------------------------------------------
class AccountIn(BaseModel):
    role: str
    real_name: str
    username: str
    password: Optional[str] = None
    department: Optional[str] = None
    contact: Optional[str] = None
    class_id: Optional[int] = None
    homeroom_teacher_id: Optional[int] = None


@router.post("", response_model=ResponseModel, summary="新增账户（管理员开老师/顾问，顾问开学员）")
def create_account(
    body: AccountIn,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    _require_manager(me)

    role = (body.role or "").strip()
    allowed = ["teacher", "staff"] if me["role"] == "admin" else ["student"]
    if role not in allowed:
        raise HTTPException(
            status_code=403,
            detail="管理员只能开班主任 / 顾问账户" if me["role"] == "admin" else "顾问只能开学员账户",
        )

    name = (body.real_name or "").strip()
    username = (body.username or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="请填写姓名")
    if not USERNAME_RE.match(username):
        raise HTTPException(
            status_code=400,
            detail="账号需以字母开头，3~20 位，只能用字母、数字、下划线",
        )

    # 软删的账号已把用户名改写成 deleted_*，这里只查真正占用的
    if db.execute("SELECT 1 FROM sys_user WHERE username = ?", (username,)).fetchone():
        raise HTTPException(status_code=400, detail=f"账号 {username} 已被占用，换一个")

    homeroom_id = None
    class_id = None
    class_name = ""
    if role == "student":
        # 班级决定班主任：选了班就等于选了这个班的老师，不能单独指定别的老师
        cls = class_service.get_class(db, body.class_id)
        if not cls and body.homeroom_teacher_id:
            cls = class_service.teacher_class(db, int(body.homeroom_teacher_id))
            if not cls:
                raise HTTPException(
                    status_code=400,
                    detail="这位老师还没带班，请先在「班级与班主任」里给他分一个班",
                )
        if not cls:
            raise HTTPException(status_code=400, detail="请选择学员所在班级")
        # 试听班是活动项目老师带的意向学员名单（来自客户线索），不收正式学员
        if (cls["kind"] or "常规班") == class_service.KIND_TRIAL:
            raise HTTPException(
                status_code=400,
                detail=f"{cls['name']} 是试听班，只放有联系方式的意向学员，正式学员请选常规班",
            )
        if not cls["teacher_id"]:
            raise HTTPException(
                status_code=400, detail=f"{cls['name']} 还没有班主任，请先给这个班分配老师"
            )
        homeroom_id = int(cls["teacher_id"])
        class_id = int(cls["id"])
        class_name = cls["name"]

    if role == "teacher":
        user_type, employee_role = "EMPLOYEE", "班主任"
    elif role == "staff":
        user_type, employee_role = "EMPLOYEE", "普通员工"
    else:
        user_type, employee_role = "STUDENT", None

    dept = (body.department or "").strip() or DEPARTMENTS[role]
    raw_pwd = (body.password or "").strip() or auth_service.DEMO_PASSWORD
    cur = db.execute(
        "INSERT INTO sys_user (username, password_hash, real_name, user_type, employee_role, "
        "department, contact_info, homeroom_teacher_id, class_id, status, created_by, "
        "create_time, update_time) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '正常', ?, datetime('now','localtime'), "
        "datetime('now','localtime'))",
        (
            username,
            auth_service.hash_password(raw_pwd),
            name,
            user_type,
            employee_role,
            dept,
            (body.contact or "").strip() or None,
            homeroom_id,
            class_id,
            me["id"],
        ),
    )
    db.commit()

    hint = ""
    if role == "student":
        hint = f"，{class_name} · 班主任 {_teacher_name(db, homeroom_id)}"
    log_service.write(
        db,
        actor=me,
        action="account_create",
        summary=f"新增{ROLE_LABEL[role]}账户：{name}（{username}）{hint}",
        detail=f"初始密码 {raw_pwd}",
        target_type="user",
        target_id=cur.lastrowid,
    )
    return ResponseModel(
        msg=f"已新增{ROLE_LABEL[role]}：{name}（{username}）{hint}，初始密码 {raw_pwd}",
        data={"id": cur.lastrowid, "username": username, "password": raw_pwd},
    )


# ---------------------------------------------------------------------------
# 班级：一个班只对应一位班主任；换老师，这个班的学生一起转过去
# 顾问维护，管理员只读
# ---------------------------------------------------------------------------
class ClassIn(BaseModel):
    name: str
    teacher_id: Optional[int] = None
    grade: Optional[str] = None


class ClassTeacherIn(BaseModel):
    teacher_id: int


@router.get("/classes", response_model=ResponseModel, summary="班级列表（含班主任、人数）")
def list_classes(
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    _require_manager(me)
    rows = class_service.list_classes(db)
    return ResponseModel(msg=f"共 {len(rows)} 个班级", data=rows)


@router.post("/classes", response_model=ResponseModel, summary="新建班级（仅顾问）")
def add_class(
    body: ClassIn,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    _require_manager(me)
    if me["role"] != "staff":
        raise HTTPException(status_code=403, detail="班级由顾问维护，管理员只查看")

    try:
        row = class_service.create_class(
            db, body.name, body.teacher_id, body.grade, created_by=me["id"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    log_service.write(
        db,
        actor=me,
        action="class_create",
        summary=f"新建班级：{row['name']}（班主任 {row['teacher']}）",
        target_type="class",
        target_id=row["id"],
    )
    return ResponseModel(
        msg=f"已新建 {row['name']}，班主任 {row['teacher']}；开学员时选这个班就行",
        data=row,
    )


@router.post("/classes/{cid}/teacher", response_model=ResponseModel, summary="调整班级班主任（仅顾问）")
def change_class_teacher(
    cid: int,
    body: ClassTeacherIn,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    _require_manager(me)
    if me["role"] != "staff":
        raise HTTPException(status_code=403, detail="班级由顾问维护，管理员只查看")

    try:
        res = class_service.assign_teacher(db, cid, body.teacher_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    cls = res["class"]
    tail = (
        f"，{res['moved']} 名学生的请假和成绩一起转给 {res['teacher']}"
        if res["moved"]
        else f"，这个班还没有学生，之后开学员会自动归 {res['teacher']}"
    )
    if res["swapped"]:
        tail += (
            f"；{res['teacher']} 原来带的 {res['swapped']} 交给 {res['before_teacher']}，"
            f"两个班对调（各 {res['moved']} / {res['swapped_moved']} 人）"
        )
    elif res["before_teacher"] and res["before_teacher"] != res["teacher"]:
        tail += f"；{res['before_teacher']} 现在没有带班"
    log_service.write(
        db,
        actor=me,
        action="class_teacher",
        summary=(
            f"调整班主任：{cls['name']} → {res['teacher']}（{res['moved']} 名学生）"
            + (f"；{res['swapped']} → {res['before_teacher']}（对调）" if res["swapped"] else "")
        ),
        detail=(
            f"原班主任 {res['before_teacher'] or '待分配'}；"
            "班上学生的 homeroom_teacher_id 已同步，请假审批与成绩录入随之切换"
        ),
        target_type="class",
        target_id=cls["id"],
    )
    return ResponseModel(msg=f"{cls['name']} 改由 {res['teacher']} 负责{tail}", data=cls)


# ---------------------------------------------------------------------------
# 停用 / 启用
# ---------------------------------------------------------------------------
class StatusIn(BaseModel):
    action: str  # disable / enable


@router.post("/{uid}/status", response_model=ResponseModel, summary="停用 / 启用账户（仅管理员）")
def set_status(
    uid: int,
    body: StatusIn,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    if me["role"] != "admin":
        raise HTTPException(status_code=403, detail="只有管理员可以停用或恢复账户")
    if uid == me["id"]:
        raise HTTPException(status_code=400, detail="不能停用自己的账号")

    row = db.execute("SELECT * FROM sys_user WHERE id = ?", (uid,)).fetchone()
    if not row or (row["status"] or "正常") == "已删除":
        raise HTTPException(status_code=404, detail="该账户不存在")
    if _role_of(db, row) == "admin":
        raise HTTPException(status_code=400, detail="管理员账户不能被停用")

    act = (body.action or "").strip()
    if act not in ("disable", "enable"):
        raise HTTPException(status_code=400, detail="action 只能是 disable 或 enable")

    status = "停用" if act == "disable" else "正常"
    db.execute(
        "UPDATE sys_user SET status = ?, update_time = datetime('now','localtime') WHERE id = ?",
        (status, uid),
    )
    db.commit()

    verb = "停用" if act == "disable" else "启用"
    log_service.write(
        db,
        actor=me,
        action="account_disable" if act == "disable" else "account_enable",
        summary=f"{verb}账户：{row['real_name']}（{row['username']}）",
        target_type="user",
        target_id=uid,
    )
    tail = "，该账号现在登录会提示无权限" if act == "disable" else "，该账号已可正常登录"
    return ResponseModel(msg=f"已{verb}：{row['real_name']}{tail}")


# ---------------------------------------------------------------------------
# 删除（软删：留档，用户名释放）
# ---------------------------------------------------------------------------
@router.delete("/{uid}", response_model=ResponseModel, summary="删除账户（仅管理员）")
def delete_account(
    uid: int,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    if me["role"] != "admin":
        raise HTTPException(status_code=403, detail="只有管理员可以删除账户")
    if uid == me["id"]:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")

    row = db.execute("SELECT * FROM sys_user WHERE id = ?", (uid,)).fetchone()
    if not row or (row["status"] or "正常") == "已删除":
        raise HTTPException(status_code=404, detail="该账户不存在")
    if _role_of(db, row) == "admin":
        raise HTTPException(status_code=400, detail="管理员账户不能被删除")

    if (row["user_type"] or "").upper() == "EMPLOYEE":
        left = db.execute(
            "SELECT COUNT(*) FROM sys_user WHERE homeroom_teacher_id = ? AND user_type = 'STUDENT' "
            "AND COALESCE(status,'正常') <> '已删除'",
            (uid,),
        ).fetchone()[0]
        if left:
            raise HTTPException(
                status_code=400,
                detail=f"{row['real_name']} 名下还有 {left} 名学生，请先把学生转给其他班主任再删除",
            )
        # 空班就先把班主任摘掉，班还留着，等顾问安排新老师
        db.execute(
            "UPDATE school_class SET teacher_id = NULL, update_time = datetime('now','localtime') "
            "WHERE teacher_id = ?",
            (uid,),
        )

    old_username = row["username"]
    db.execute(
        "UPDATE sys_user SET status = '已删除', username = ?, "
        "update_time = datetime('now','localtime') WHERE id = ?",
        (f"deleted_{uid}_{old_username}", uid),
    )
    db.commit()

    log_service.write(
        db,
        actor=me,
        action="account_delete",
        summary=f"删除账户：{row['real_name']}（{old_username}）",
        detail="账号已删除，登录会提示没有该账户；历史请假 / 成绩 / 日志保留",
        target_type="user",
        target_id=uid,
    )
    return ResponseModel(msg=f"已删除账户：{row['real_name']}（{old_username}），该账号已无法登录")
