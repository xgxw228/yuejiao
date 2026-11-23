"""系统级接口：健康检查（FR-030）+ 只读管理后台（FR-031）。

管理后台只做"看数据"，不提供增删改：
演示要的是"数据都在、能自查"，开放写入口反而增加讲错的风险。
"""

import sqlite3
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from database import get_db
from models.base import ResponseModel
from services import auth_service, log_service

router = APIRouter()

START_TS = time.time()

# 表名白名单：既控制顺序，也防止把任意字符串拼进 SQL
TABLES: dict[str, dict] = {
    "sys_user": {"label": "用户", "icon": "👥", "order": "id"},
    "course_project": {"label": "项目课程", "icon": "🎓", "order": "id"},
    "crm_lead": {"label": "客户线索", "icon": "📇", "order": "id DESC"},
    "student_score": {"label": "学生成绩", "icon": "📊", "order": "id DESC"},
    "student_admin_service": {"label": "请假审批", "icon": "🗓", "order": "id DESC"},
    "student_feedback_ticket": {"label": "反馈工单", "icon": "🎫", "order": "id DESC"},
    "student_psych_alert": {"label": "心理预警", "icon": "🫂", "order": "id DESC"},
    "student_psych_journal": {"label": "心理周记", "icon": "📔", "order": "id DESC"},
    "student_psych_profile": {"label": "心理画像", "icon": "🧭", "order": "student_id"},
    "employee_daily_report": {"label": "员工日报", "icon": "📝", "order": "id DESC"},
    "event_lecture": {"label": "活动讲座", "icon": "🎤", "order": "start_time"},
    "event_registration": {"label": "活动报名", "icon": "✅", "order": "id DESC"},
    "conversation_log": {"label": "对话记录", "icon": "💬", "order": "id DESC"},
}

HIDDEN_COLUMNS = {"password_hash"}

# 表里的「XX 编号」对一线同事没有意义：查询时连带把姓名 / 班级名取出来，
# 展示时顶到编号原来的位置上（编号本身仍留在 rows 里，接口不做破坏性裁剪）。
# 元组含义：(编号列, 展示列, 中文列名, 关联到哪张表)
REF_COLUMNS: dict[str, list[tuple[str, str, str, str]]] = {
    "sys_user": [
        ("homeroom_teacher_id", "homeroom_teacher_name", "班主任", "user"),
        ("class_id", "class_name", "班级", "class"),
        ("parent_of_student_id", "parent_student_name", "关联学生", "user"),
        ("created_by", "created_by_name", "开户人", "user"),
    ],
    "student_score": [("student_id", "student_name", "学生", "user")],
    "student_admin_service": [
        ("student_id", "student_name", "学生", "user"),
        ("approver_id", "approver_name", "审批人", "user"),
    ],
    "student_feedback_ticket": [
        ("student_id", "student_name", "学生", "user"),
        ("handler_id", "handler_name", "处理人", "user"),
    ],
    "student_psych_alert": [
        ("student_id", "student_name", "学生", "user"),
        ("teacher_id", "teacher_name", "跟进老师", "user"),
        ("handler_id", "handler_name", "处理人", "user"),
    ],
    "student_psych_journal": [
        ("student_id", "student_name", "学生", "user"),
        ("handler_id", "handler_name", "跟进老师", "user"),
    ],
    "student_psych_profile": [("student_id", "student_name", "学生", "user")],
    "employee_daily_report": [("employee_id", "employee_name", "员工", "user")],
    "conversation_log": [("user_id", "user_name", "用户", "user")],
}

# 后台表格的列名一律显示中文：给一线同事看的数据表，不该出现 customer_name 这种字段名。
COLUMN_LABELS: dict[str, str] = {
    "id": "编号",
    "username": "登录账号",
    "real_name": "姓名",
    "user_type": "用户类型",
    "employee_role": "员工角色",
    "department": "部门 / 方向",
    "contact_info": "联系方式",
    "status": "状态",
    "create_time": "创建时间",
    "update_time": "更新时间",
    "homeroom_teacher_id": "班主任ID",
    "parent_of_student_id": "关联学生ID",
    "created_by": "开户人ID",
    "class_id": "班级ID",
    "project_name": "项目名称",
    "category": "类别",
    "description": "简介",
    "target_audience": "适合人群",
    "customer_name": "客户姓名",
    "background_info": "需求背景",
    "follow_up_history": "跟进记录",
    "owner_employee_id": "顾问ID",
    "owner_name": "顾问",
    "student_id": "学生ID",
    "course_name": "课程",
    "score": "分数",
    "semester": "学期",
    "service_type": "请假类型",
    "start_time": "开始时间",
    "end_time": "结束时间",
    "reason": "请假事由",
    "approver_id": "审批人ID",
    "related_academic_id": "关联教务ID",
    "approve_time": "审批时间",
    "approve_comment": "审批意见",
    "content": "内容",
    "detail": "详情",
    "solution": "处理结果",
    "is_notified": "已通知",
    "trigger_reason": "触发原因",
    "risk_level": "风险等级",
    "mood_tag": "情绪标签",
    "mood_score": "情绪分值",
    "sleep": "睡眠",
    "stress_source": "压力来源",
    "duration": "持续多久",
    "handler_id": "处理人ID",
    "handle_note": "处理记录",
    "handle_time": "处理时间",
    "teacher_id": "班主任ID",
    "latest_emotion_tag": "最新情绪",
    "emotion_score": "情绪分",
    "last_interaction_time": "最近互动时间",
    "emotion_history": "情绪记录",
    "employee_id": "员工ID",
    "report_date": "日报日期",
    "event_name": "活动名称",
    "event_type": "活动类型",
    "location": "地点",
    "max_participants": "名额",
    "current_participants": "已报名",
    "event_id": "活动ID",
    "customer_id": "客户ID",
    "user_id": "用户ID",
    "agent_type": "智能体",
    "user_input": "学生提问",
    "ai_output": "智能体回复",
    "emotion_tag": "情绪标签",
}


def _display_columns(name: str, cols: list[str]) -> list[str]:
    """编号列换成姓名列，顺序不变；客户线索另加「顾问」。"""
    out = list(cols)
    for col, name_col, _label, _kind in REF_COLUMNS.get(name, []):
        if col in out:
            out[out.index(col)] = name_col
    if name == "crm_lead":
        out = [c for c in out if c != "owner_employee_id"]
        at = out.index("status") + 1 if "status" in out else len(out)
        out.insert(at, "owner_name")
    # 老库的 class_id 是 ALTER 补出来的（排在最后），新库在表中间；
    # 固定成「班主任 → 班级」相邻，两个环境看到的列顺序才一致。
    if "class_name" in out and "homeroom_teacher_name" in out:
        out.remove("class_name")
        out.insert(out.index("homeroom_teacher_name") + 1, "class_name")
    # 反馈表的分类 / 处理人是 ALTER 补出来的（排在末尾），固定成
    # 「学生 → 类别 → 内容 → … → 处理结果 → 处理人 → 处理时间」，新旧库列序一致。
    if name == "student_feedback_ticket":
        if "category" in out and "content" in out:
            out.remove("category")
            out.insert(out.index("content"), "category")
        if "handler_name" in out:
            out.remove("handler_name")
            at = out.index("solution") + 1 if "solution" in out else len(out)
            out.insert(at, "handler_name")
        if "handle_time" in out:
            out.remove("handle_time")
            at = out.index("handler_name") + 1 if "handler_name" in out else len(out)
            out.insert(at, "handle_time")
    return out


def require_admin(authorization: Optional[str] = Header(None)) -> dict:
    """后台只给管理员看（领导/管理员角色）。"""
    payload = auth_service.read_token(authorization)
    if not payload:
        raise HTTPException(status_code=401, detail="请先登录")
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="只有管理员可以查看数据后台")
    return payload


def _columns(db: sqlite3.Connection, table: str) -> list[str]:
    return [
        r["name"]
        for r in db.execute(f"PRAGMA table_info({table})").fetchall()
        if r["name"] not in HIDDEN_COLUMNS
    ]


@router.get("/health", summary="健康检查")
def health(db: sqlite3.Connection = Depends(get_db)):
    db_ok, detail = True, "ok"
    try:
        db.execute("SELECT 1").fetchone()
        tables = db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
    except Exception as exc:  # noqa: BLE001
        db_ok, detail, tables = False, str(exc), 0

    dify_ok = False
    try:
        import socket

        with socket.create_connection(("127.0.0.1", 80), timeout=0.5):
            dify_ok = True
    except OSError:
        dify_ok = False

    status = "ok" if db_ok else "down"
    return ResponseModel(
        msg=f"服务{'正常' if db_ok else '异常'}",
        data={
            "status": status,
            "db": {"ok": db_ok, "tables": tables, "detail": detail},
            "dify": {"ok": dify_ok, "endpoint": "http://localhost"},
            "uptime_seconds": round(time.time() - START_TS, 1),
            "version": "2.0.0",
        },
    )


@router.get("/admin/tables", summary="后台：表清单与行数")
def admin_tables(
    db: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(require_admin),
):
    out = []
    for name, meta in TABLES.items():
        try:
            count = db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        except sqlite3.Error:
            count = 0
        out.append({"name": name, "label": meta["label"], "icon": meta["icon"], "count": count})
    return ResponseModel(msg=f"共 {len(out)} 张表", data=out)


@router.get("/admin/dashboard", summary="后台：经营概览（领导视图）")
def admin_dashboard(
    db: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """领导不该只能逐表翻数据，先给一屏「今天要关注什么」。"""

    def one(sql: str, args: tuple = ()) -> int:
        try:
            row = db.execute(sql, args).fetchone()
            return row[0] if row and row[0] is not None else 0
        except sqlite3.Error:
            return 0

    today = time.strftime("%Y-%m-%d")
    return ResponseModel(
        msg="经营概览",
        data={
            "leads": {
                "total": one("SELECT COUNT(*) FROM crm_lead"),
                "today": one("SELECT COUNT(*) FROM crm_lead WHERE date(create_time) = ?", (today,)),
                "signed": one("SELECT COUNT(*) FROM crm_lead WHERE status = '已签约'"),
                "following": one("SELECT COUNT(*) FROM crm_lead WHERE status = '跟进中'"),
            },
            "leaves": {
                "pending": one("SELECT COUNT(*) FROM student_admin_service WHERE status = '待审批'"),
                "total": one("SELECT COUNT(*) FROM student_admin_service"),
            },
            "alerts": {
                "open": one("SELECT COUNT(*) FROM student_psych_alert WHERE status = '未处理'"),
                "following": one("SELECT COUNT(*) FROM student_psych_alert WHERE status = '跟进中'"),
            },
            "tickets": {
                "open": one("SELECT COUNT(*) FROM student_feedback_ticket WHERE status != '已解决'"),
            },
            "events": {
                "upcoming": one(
                    "SELECT COUNT(*) FROM event_lecture WHERE start_time >= ?", (today,)
                ),
                "registrations": one("SELECT COUNT(*) FROM event_registration"),
            },
            "chats": {
                "today": one("SELECT COUNT(*) FROM conversation_log WHERE date(create_time) = ?", (today,)),
                "total": one("SELECT COUNT(*) FROM conversation_log"),
            },
        },
    )


@router.get("/admin/table/{name}", summary="后台：分页读取某张表")
def admin_table(
    name: str,
    q: Optional[str] = Query(None, description="关键字，匹配任意文本列"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(require_admin),
):
    if name not in TABLES:
        raise HTTPException(status_code=404, detail=f"不支持的表：{name}")

    cols = _columns(db, name)
    lead = name == "crm_lead"
    refs = REF_COLUMNS.get(name, [])

    # 主表一律带表名前缀：下面会 left join 出人名，id / create_time 这类列会重名
    select_cols = ", ".join(f"{name}.{c}" if refs else c for c in cols)
    name_exprs: list[str] = []  # 搜索时也要能按姓名 / 班级名命中
    if refs:
        joins = []
        for i, (col, name_col, _label, kind) in enumerate(refs):
            if kind == "class":
                alias = f"c{i}"
                joins.append(f"LEFT JOIN school_class {alias} ON {alias}.id = {name}.{col}")
                select_cols += f", {alias}.name AS {name_col}"
                name_exprs.append(f"CAST({alias}.name AS TEXT)")
            else:
                alias = f"u{i}"
                joins.append(f"LEFT JOIN sys_user {alias} ON {alias}.id = {name}.{col}")
                select_cols += f", {alias}.real_name AS {name_col}"
                name_exprs.append(f"CAST({alias}.real_name AS TEXT)")
        source = f"{name} " + " ".join(joins)
    else:
        source = name

    # 客户线索要多带一列「顾问」姓名：owner_employee_id 是内部编号，看不出来是谁引进的
    if lead:
        select_cols = ", ".join(f"l.{c}" for c in cols)
        source = "crm_lead l LEFT JOIN sys_user u ON u.id = l.owner_employee_id"
        select_cols += ", u.real_name AS owner_name"
        name_exprs = ["CAST(u.real_name AS TEXT)"]
        order_col, _, direction = TABLES[name]["order"].partition(" ")
        order = f"l.{order_col} {direction}".strip()
    elif refs:
        order_col, _, direction = TABLES[name]["order"].partition(" ")
        order = f"{name}.{order_col} {direction}".strip()
    else:
        order = TABLES[name]["order"]

    prefix = "l." if lead else (f"{name}." if refs else "")
    # 搜索面：去掉被替换掉的编号列，补上姓名 / 班级名
    ref_ids = {c for c, *_ in refs}
    search_cols = [c for c in cols if c not in ref_ids]
    where, args = "", []
    if q:
        exprs = [f"CAST({prefix}{c} AS TEXT)" for c in search_cols] + name_exprs
        where = " WHERE " + " OR ".join(f"{e} LIKE ?" for e in exprs)
        args = [f"%{q}%"] * len(exprs)

    total = db.execute(f"SELECT COUNT(*) FROM {source}{where}", args).fetchone()[0]
    offset = (page - 1) * size
    rows = [
        dict(r)
        for r in db.execute(
            f"SELECT {select_cols} FROM {source}{where} "
            f"ORDER BY {order} LIMIT ? OFFSET ?",
            args + [size, offset],
        ).fetchall()
    ]
    display_cols = _display_columns(name, cols)
    labels = {c: COLUMN_LABELS.get(c, c) for c in display_cols}
    for _col, name_col, label, _kind in refs:
        labels[name_col] = label
    if lead:
        labels["owner_name"] = "顾问"
    return ResponseModel(
        msg=f"共 {total} 行",
        data={
            "name": name,
            "label": TABLES[name]["label"],
            "columns": display_cols,
            "labels": labels,
            "rows": rows,
            "total": total,
            "page": page,
            "size": size,
            "pages": max(1, (total + size - 1) // size),
        },
    )


# ---------------------------------------------------------------------------
# 线索跟进：管理员只看，不动手。
# 客户归属在开户时就定了（owner_employee_id），跟进和状态由该顾问自己维护，
# 管理员在这里看「谁引进了谁、跟到哪一步」，代写跟进等于替下属干活，也会让提成归属说不清。
# ---------------------------------------------------------------------------
LEAD_STATUSES = ["新增意向", "跟进中", "已签约", "已流失"]


@router.get("/admin/leads", summary="后台：客户线索（含跟进记录）")
def admin_leads(
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(require_admin),
):
    where, args = [], []
    if status and status in LEAD_STATUSES:
        where.append("l.status = ?")
        args.append(status)
    if q:
        where.append("(l.customer_name LIKE ? OR l.contact_info LIKE ? OR l.background_info LIKE ?)")
        args += [f"%{q}%"] * 3
    w = (" WHERE " + " AND ".join(where)) if where else ""

    total = db.execute(f"SELECT COUNT(*) FROM crm_lead l{w}", args).fetchone()[0]
    rows = [
        dict(r)
        for r in db.execute(
            f"SELECT l.*, u.real_name AS owner_name FROM crm_lead l "
            f"LEFT JOIN sys_user u ON u.id = l.owner_employee_id {w} "
            f"ORDER BY l.update_time DESC, l.id DESC LIMIT ? OFFSET ?",
            args + [size, (page - 1) * size],
        ).fetchall()
    ]
    counts = {
        r["status"]: r["n"]
        for r in db.execute("SELECT status, COUNT(*) AS n FROM crm_lead GROUP BY status")
    }
    return ResponseModel(
        msg=f"共 {total} 条",
        data={
            "rows": rows,
            "total": total,
            "page": page,
            "size": size,
            "pages": max(1, (total + size - 1) // size),
            "counts": counts,
            "statuses": LEAD_STATUSES,
        },
    )


@router.get("/admin/logs", summary="后台：操作日志（只读，不可改不可删）")
def admin_logs(
    page: int = Query(1, ge=1),
    size: int = Query(30, ge=1, le=100),
    action: Optional[str] = Query(None),
    actor_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(require_admin),
):
    data = log_service.query(
        db, page=page, size=size, action=action, actor_id=actor_id, q=q
    )
    return ResponseModel(msg=f"共 {data['total']} 条", data=data)
