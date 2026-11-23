"""登录与角色权限。

设计思路：登录只回答"我是谁"，真正决定差异的是角色 ——
同一个系统里，角色决定三件事：
1. 能看到哪几个 Agent（学生只有留学管家，家长只有客服顾问）；
2. 能看谁的数据（学生只看自己；班主任只看名下学生；管理员看全校）；
3. 能点哪些功能（审批面板、身份模拟只对部分角色开放）。

Token 用 HMAC 签名的轻量方案（无状态、不落库），够演示用：
    base64(payload).sha256_hmac(payload)
payload = {"uid": 1, "role": "student", "exp": 1730000000}
"""

import base64
import hashlib
import hmac
import json
import os
import sqlite3
import time
from typing import Any, Optional

from fastapi import HTTPException

SECRET = os.environ.get("AUTH_SECRET", "yuejiao-demo-secret-2026")
# 演示环境默认 7 天，避免隔天/过夜后 token 失效导致「明明登录了却进不去」
TOKEN_TTL = int(os.environ.get("AUTH_TTL", str(7 * 24 * 3600)))

# ---------------------------------------------------------------------------
# 角色矩阵
# ---------------------------------------------------------------------------
ROLES: dict[str, dict] = {
    "admin": {
        "label": "管理员",
        "desc": "全部 Agent · 全校数据 · 账户管理（不代批请假）",
        "agents": ["student", "employee", "customer"],
        "features": {"approve": None, "switch_identity": True, "admin": True},
    },
    "teacher": {
        "label": "班主任",
        "desc": "员工助手 + 请假审批（只看自己名下的学生）",
        "agents": ["employee"],
        "features": {"approve": "own", "switch_identity": False, "admin": False},
    },
    "staff": {
        "label": "顾问",
        "desc": "客户线索 / CRM 跟进 / 项目推荐，无审批权",
        "agents": ["employee", "customer"],
        "features": {"approve": None, "switch_identity": False, "admin": False},
    },
    "student": {
        "label": "学员",
        "desc": "留学管家，只能办理和查询自己的事务",
        "agents": ["student"],
        "features": {"approve": None, "switch_identity": False, "admin": False},
    },
    "parent": {
        "label": "家长",
        "desc": "客服顾问：项目推荐 / 活动报名（看不到学生隐私数据）",
        "agents": ["customer"],
        "features": {"approve": None, "switch_identity": False, "admin": False},
    },
}


def hash_password(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 登录页上的演示账号（按身份分组，一键填充）
# ---------------------------------------------------------------------------
DEMO_PASSWORD = "123456"
DEMO_ROLE_ORDER = ("admin", "teacher", "activity_teacher", "student", "staff")

# 兜底：数据库读不到时仍然能登录页展示（正常情况走 demo_accounts 从库里取）
DEMO_ROLES: list[dict] = [
    {
        "key": "admin",
        "username": "admin",
        "password": DEMO_PASSWORD,
        "name": "王主任",
        "label": "管理员",
        "desc": "全校数据 · 只读后台",
        "group": "教学管理部",
        "icon": "🛡️",
    },
    {
        "key": "teacher",
        "username": "emp001",
        "password": DEMO_PASSWORD,
        "name": "李老师",
        "label": "班主任",
        "desc": "粤教1班 · 名下 3 名学生",
        "group": "张三、许明、林晓",
        "icon": "🧑‍🏫",
    },
    {
        "key": "student",
        "username": "stu001",
        "password": DEMO_PASSWORD,
        "name": "张三",
        "label": "学员",
        "desc": "粤教1班 · 新加坡方向 · 仅本人数据",
        "group": "李老师",
        "icon": "🎓",
    },
    {
        "key": "staff",
        "username": "emp006",
        "password": DEMO_PASSWORD,
        "name": "陈顾问",
        "label": "顾问",
        "desc": "名下 3 条线索",
        "group": "咨询三组",
        "icon": "🧑‍💼",
    },
]


def _direction(department: Optional[str]) -> str:
    """「国际学院 2025 级 · 新加坡方向」→「新加坡方向」；「咨询一组（新加坡）」→ 括号内。"""
    text = (department or "").strip()
    if "·" in text:
        text = text.split("·")[-1].strip()
    if "（" in text and "）" in text:
        text = text[text.index("（") + 1 : text.rindex("）")].strip()
    return text


def demo_accounts(db: sqlite3.Connection) -> list[dict]:
    """从库里生成登录页的演示账号，保证「账号 ↔ 归属」跟真实数据一致。

    同一身份给多个账号，是为了现场验证：换个老师/换个学员登录，
    看到的东西必须是各自名下那一份。所以这里不写死，直接读 sys_user：
    - 班主任：名下学生姓名 + 人数
    - 学员：班主任姓名 + 方向
    - 顾问：名下线索数
    - 管理员：只保留一个
    """
    rows = db.execute(
        "SELECT * FROM sys_user WHERE user_type IN ('STUDENT','EMPLOYEE') "
        "AND COALESCE(status,'正常') <> '已删除' ORDER BY id"
    ).fetchall()

    out: list[dict] = []
    for row in rows:
        students = _student_count(db, row["id"]) if (row["user_type"] or "").upper() == "EMPLOYEE" else 0
        has_class = bool(
            db.execute("SELECT 1 FROM school_class WHERE teacher_id = ?", (row["id"],)).fetchone()
        )
        role = resolve_role(row, students, has_class)
        if role not in DEMO_ROLE_ORDER or role == "parent":
            continue

        role_label = ROLES[role]["label"]
        card_key = role
        if role == "teacher":
            cls = db.execute(
                "SELECT id, name, kind FROM school_class WHERE teacher_id = ? ORDER BY id LIMIT 1",
                (row["id"],),
            ).fetchone()
            if cls and (cls["kind"] or "常规班") == "试听班":
                # 活动项目老师：班上是试听名单，不是正式学员
                from services import class_service

                counts = class_service.trial_counts(db, cls["id"])
                role_label = "活动项目老师"
                card_key = "activity_teacher"
                desc = (
                    f"{cls['name']} · 待签约 {counts['pending']} 人 · 已签约 {counts['signed']} 人"
                )
                group = "有联系方式、未流失的意向学员"
            else:
                names = [
                    r["real_name"]
                    for r in db.execute(
                        "SELECT real_name FROM sys_user WHERE homeroom_teacher_id = ? ORDER BY id",
                        (row["id"],),
                    )
                ]
                desc = (cls["name"] + " · " if cls else "未分配班级 · ") + f"名下 {len(names)} 名学生"
                group = "、".join(names) or "名下暂无学生"
        elif role == "student":
            c = db.execute(
                "SELECT c.name, t.real_name AS teacher FROM sys_user s "
                "JOIN school_class c ON c.id = s.class_id "
                "LEFT JOIN sys_user t ON t.id = c.teacher_id WHERE s.id = ?",
                (row["id"],),
            ).fetchone()
            teacher = (c["teacher"] if c else None) or "未分配班主任"
            # 班主任已经单独占一列（group），描述里不再重复姓名，避免「李老师 · 李老师名下」
            desc = ((c["name"] + " · ") if c else "") + \
                f"{_direction(row['department']) or '方向待定'} · 仅本人数据"
            group = teacher
        elif role == "staff":
            n = db.execute(
                "SELECT COUNT(*) FROM crm_lead WHERE owner_employee_id = ?", (row["id"],)
            ).fetchone()[0]
            desc = f"名下 {n} 条线索 · 无审批权"
            group = _direction(row["department"]) or "留学事业部"
        else:
            desc = "全校数据 · 只读后台"
            group = _direction(row["department"]) or "教学管理部"

        off = (row["status"] or "正常") != "正常"
        if off:
            desc = "已停用 · 需管理员恢复后才能登录"

        out.append(
            {
                "key": card_key,
                "username": row["username"],
                "password": DEMO_PASSWORD,
                "name": row["real_name"],
                "label": role_label,
                "desc": desc,
                "group": group,
                "disabled": off,
                "icon": {
                    "admin": "🛡️", "teacher": "🧑‍🏫", "activity_teacher": "🎧",
                    "student": "🎓", "staff": "🧑‍💼",
                }[card_key],
            }
        )

    out.sort(key=lambda a: (DEMO_ROLE_ORDER.index(a["key"]), a["username"]))
    return out



# ---------------------------------------------------------------------------
# 角色判定
# ---------------------------------------------------------------------------

def _student_count(db: sqlite3.Connection, teacher_id: Any) -> int:
    row = db.execute(
        "SELECT COUNT(*) FROM sys_user WHERE homeroom_teacher_id = ?", (teacher_id,)
    ).fetchone()
    return int(row[0] or 0)


def resolve_role(row: Any, students: int = 0, has_class: bool = False) -> str:
    user_type = (row["user_type"] or "").upper()
    if user_type == "STUDENT":
        return "student"
    if user_type == "PARENT":
        return "parent"
    if (row["employee_role"] or "") in ("管理员", "领导"):
        return "admin"
    # 显式标了班主任就按班主任算：新开的账号还没分学生时，
    # 不能因为“名下 0 人”就被降级成顾问。
    if (row["employee_role"] or "") == "班主任":
        return "teacher"
    # 活动项目老师（带试听班）名下没有正式学员，但确实在带班，也要给老师视图
    return "teacher" if (students > 0 or has_class) else "staff"


def _identity_label(row: Any, class_name: Optional[str]) -> str:
    """底部身份行：学员 / 班主任优先显示班级，其余显示部门。"""
    tail = class_name or (row["department"] or "")
    text = f"{row['real_name']} · {row['username']}"
    return f"{text} · {tail}" if tail else text


def profile(db: sqlite3.Connection, user_id: Any) -> Optional[dict]:
    """按 id 取用户 + 角色，登录态和 /me 都用它。"""
    try:
        uid = int(float(user_id))
    except (TypeError, ValueError):
        return None
    row = db.execute("SELECT * FROM sys_user WHERE id = ?", (uid,)).fetchone()
    if not row:
        return None
    if (row["status"] or "正常") in ("已删除",):
        return None
    if (row["status"] or "正常") != "正常":
        raise HTTPException(
            status_code=403,
            detail="该账号已被停用，没有登录权限，请联系管理员在「账户管理」里恢复",
        )

    students = _student_count(db, uid) if (row["user_type"] or "").upper() == "EMPLOYEE" else 0
    has_class = False
    if (row["user_type"] or "").upper() == "EMPLOYEE":
        has_class = bool(
            db.execute("SELECT 1 FROM school_class WHERE teacher_id = ?", (uid,)).fetchone()
        )
    role = resolve_role(row, students, has_class)
    meta = ROLES[role]

    homeroom_name = None
    if row["homeroom_teacher_id"]:
        t = db.execute(
            "SELECT real_name FROM sys_user WHERE id = ?", (row["homeroom_teacher_id"],)
        ).fetchone()
        homeroom_name = t["real_name"] if t else None

    parent_of = None
    if row["parent_of_student_id"]:
        s = db.execute(
            "SELECT real_name FROM sys_user WHERE id = ?", (row["parent_of_student_id"],)
        ).fetchone()
        parent_of = s["real_name"] if s else None

    # 班级：学员看自己在哪个班，班主任看自己带哪个班
    class_name, class_teacher, class_kind = None, None, None
    if role == "student":
        c = db.execute(
            "SELECT c.name, c.kind, t.real_name AS teacher FROM sys_user s "
            "JOIN school_class c ON c.id = s.class_id "
            "LEFT JOIN sys_user t ON t.id = c.teacher_id WHERE s.id = ?",
            (uid,),
        ).fetchone()
        if c:
            class_name, class_teacher, class_kind = c["name"], c["teacher"], c["kind"]
    elif role == "teacher":
        c = db.execute(
            "SELECT name, kind FROM school_class WHERE teacher_id = ? ORDER BY id LIMIT 1", (uid,)
        ).fetchone()
        class_name = c["name"] if c else None
        class_kind = c["kind"] if c else None

    # 活动项目老师带的是试听班，身份标签不能写成「班主任」
    role_label = meta["label"]
    if class_kind == "试听班" and role == "teacher":
        role_label = "活动项目老师"

    return {
        "id": row["id"],
        "username": row["username"],
        "real_name": row["real_name"],
        "initial": (row["real_name"] or "?")[0],
        "user_type": row["user_type"],
        "employee_role": row["employee_role"],
        "department": row["department"],
        "label": _identity_label(row, class_name),
        "role": role,
        "role_label": role_label,
        "role_desc": meta["desc"],
        "agents": meta["agents"],
        "features": dict(meta["features"]),
        "students": students,           # 班主任名下学生数
        "homeroom_name": homeroom_name,  # 学生的班主任
        "class_name": class_name,        # 学员所在班级 / 班主任带的班
        "class_kind": class_kind,        # 常规班 / 试听班
        "class_teacher": class_teacher,  # 学员班级的班主任
        "parent_of": parent_of,          # 家长对应的学生
    }


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_token(user: dict) -> str:
    payload = {
        "uid": user["id"],
        "role": user["role"],
        "exp": int(time.time()) + TOKEN_TTL,
    }
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()[:40]
    return f"{body}.{sig}"


def read_token(token: Optional[str]) -> Optional[dict]:
    """校验签名与过期时间，返回 payload；不合法返回 None。"""
    if not token:
        return None
    token = token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if token.count(".") != 1:
        return None
    body, sig = token.split(".", 1)
    expect = hmac.new(SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()[:40]
    if not hmac.compare_digest(sig, expect):
        return None
    try:
        payload = json.loads(_b64d(body).decode("utf-8"))
    except Exception:
        return None
    if int(payload.get("exp") or 0) < int(time.time()):
        return None
    return payload


def current_user(db: sqlite3.Connection, token: Optional[str]) -> Optional[dict]:
    """token -> 用户完整信息。token 有效但用户被删/禁用时返回 None。"""
    payload = read_token(token)
    if not payload:
        return None
    user = profile(db, payload.get("uid"))
    if not user:
        return None
    return user


# ---------------------------------------------------------------------------
# 登录
# ---------------------------------------------------------------------------

def login(db: sqlite3.Connection, username: str, password: str) -> dict:
    username = (username or "").strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="请输入账号和密码")

    row = db.execute(
        "SELECT * FROM sys_user WHERE username = ? AND COALESCE(status,'正常') <> '已删除'",
        (username,),
    ).fetchone()
    if not row:
        # 允许用姓名登录（演示方便），但重名时必须用账号，避免登进别人的账户
        same_name = db.execute(
            "SELECT * FROM sys_user WHERE real_name = ? AND COALESCE(status,'正常') <> '已删除'",
            (username,),
        ).fetchall()
        if len(same_name) > 1:
            raise HTTPException(
                status_code=400,
                detail="有多个同名账户，请改用登录账号登录（姓名可以重名，账号不会）",
            )
        row = same_name[0] if same_name else None
    if not row:
        raise HTTPException(
            status_code=401,
            detail="没有该账户，请核对账号后重试；需要开通请联系顾问",
        )

    if not hmac.compare_digest(hash_password(password), row["password_hash"] or ""):
        raise HTTPException(status_code=401, detail="密码不正确（演示账号密码统一为 123456）")

    if (row["status"] or "正常") != "正常":
        raise HTTPException(
            status_code=403,
            detail="该账号已停用，没有登录权限，请联系管理员在「账户管理」里恢复后再登录",
        )

    user = profile(db, row["id"])
    if not user:
        raise HTTPException(status_code=401, detail="账号不可用")
    return {"token": make_token(user), "user": user}
