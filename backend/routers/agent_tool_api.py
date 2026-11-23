"""Dify Agent 业务工具接口（三层架构里的「手脚」）。

Dify 工作流的 HTTP 请求节点全部指向本文件的路由，统一前缀 /api/agent。
设计约束：
- 只做数据读写与确定性规则计算，不做话术润色（润色交给 Dify 的 LLM 节点）
- 所有接口返回 ResponseModel {code, msg, data}，字段名 snake_case
- 参数非法返回 400，资源不存在返回 404（供 Dify 节点做异常分支）
"""

import hmac
import json
import re
import sqlite3
from datetime import date, datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, BeforeValidator

from config import INTERNAL_TOKEN
from database import get_db
from models.base import ResponseModel
from services import (
    auth_service,
    class_service,
    emotion_engine,
    leave_parser,
    leave_service,
    log_service,
    nl2sql_service,
    session_memory,
)
from services.alert_engine import check_and_create_alert
from services.profile_engine import update_psych_profile
from services.profile_match_engine import recommend

router = APIRouter()

LEAD_STATUS = ["新增意向", "跟进中", "已签约", "已流失"]


def require_service(
    x_internal_token: Optional[str] = Header(None, alias="X-Internal-Token"),
    authorization: Optional[str] = Header(None),
) -> dict:
    """写操作鉴权（需求 FR-030 的接口安全兜底）。

    两类调用方：
    - 对话工具层：Dify 的 HTTP 节点带 `X-Internal-Token`（容器内服务令牌）；
    - 页面/外部：带登录拿到的 `Authorization: Bearer <token>`，会校验签名与有效期。
    只读查询接口不挂这个依赖，避免把演示用的 curl 全部挡住。
    """
    if x_internal_token and hmac.compare_digest(x_internal_token, INTERNAL_TOKEN):
        return {"kind": "service", "uid": None, "role": "service"}
    payload = auth_service.read_token(authorization)
    if payload:
        return {"kind": "user", "uid": payload.get("uid"), "role": payload.get("role")}
    raise HTTPException(
        status_code=401,
        detail="写操作需要凭证：请带 Authorization: Bearer <登录 token>，或内部服务令牌",
    )



def _id_coercer(default: int):
    """把 Dify 传来的 ""、null、"3" 统一成整数。

    Dify 的输入变量留空时会渲染成空字符串，直接塞进 JSON 会让 pydantic 报 422，
    这里统一兜底成演示默认值，保证对话不中断。
    """

    def convert(value: Any) -> int:
        if value in (None, "", []):
            return default
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    return convert


StudentId = Annotated[int, BeforeValidator(_id_coercer(1))]
EmployeeId = Annotated[int, BeforeValidator(_id_coercer(3))]
CustomerId = Annotated[int, BeforeValidator(_id_coercer(1))]


def _query_int(value: Optional[str], default: int) -> Optional[int]:
    if value in (None, "", "null"):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# 请求体模型
# ---------------------------------------------------------------------------

class LeaveApply(BaseModel):
    student_id: StudentId = 1
    reason: str
    service_type: str = "请假"
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class LeaveApprove(BaseModel):
    approver_id: Optional[int] = None
    approved: bool = True
    comment: Optional[str] = None


class EmotionEvaluate(BaseModel):
    student_id: StudentId = 1
    text: str
    emotion_tag: Optional[str] = None
    emotion_score: Optional[int] = None


class FeedbackCreate(BaseModel):
    student_id: StudentId = 1
    content: str
    detail: Optional[str] = None


class FeedbackResolve(BaseModel):
    solution: str
    teacher_id: Optional[int] = None


class LeadCreate(BaseModel):
    customer_name: str
    contact_info: Optional[str] = None
    background_info: Optional[str] = None
    follow_up_history: Optional[str] = None
    owner_employee_id: Optional[EmployeeId] = None


class LeadStatusUpdate(BaseModel):
    status: str


class ReportCreate(BaseModel):
    employee_id: EmployeeId = 3
    content: str
    report_date: Optional[str] = None


class ScoreCreate(BaseModel):
    student_id: StudentId
    course_name: str
    score: float
    semester: Optional[str] = None
    overwrite: bool = False


class NL2SQLQuery(BaseModel):
    query: str
    # Dify 会带上当前登录员工，用于「我班上」「我带的」这类身份相关过滤
    user_id: Optional[int] = None
    # 多轮指代消解：conversation_id 用来取本会话的上文（推荐），
    # history 允许调用方直接塞一段摘要（压测/脚本用）
    conversation_id: Optional[str] = None
    history: Optional[str] = None


class ProfileEvaluate(BaseModel):
    raw_text: Optional[str] = None
    name: Optional[str] = None
    age: Optional[int] = None
    education: Optional[str] = None
    intent: Optional[str] = None
    language: Optional[str] = None
    hands_on: Optional[str] = None
    economy: Optional[str] = None


class EventRegister(BaseModel):
    event_id: Optional[int] = None
    event_name: Optional[str] = None
    customer_id: CustomerId = 1


# ---------------------------------------------------------------------------
# 学生侧：请假（FR-006 ~ FR-008）
# ---------------------------------------------------------------------------

_APPROVAL_HINTS = (
    "审批通过", "审核通过", "帮我批", "帮我审", "批一下", "批准", "通过一下",
    "给我批", "让我批", "直接批", "帮我通过",
)
_LEAVE_WORDS = ("请假", "休假", "事假", "病假", "离校", "请假条")


def _guard_leave_apply(reason: str) -> None:
    """拦住两类"不是请假"的输入，避免生成莫名其妙请假单。

    实测踩过的坑：学生说「帮我把这个请假审批通过」，模型按"请假"字眼一路走到
    写库，结果库里多出一条事由就是这句话的待审批单。
    """
    text = (reason or "").strip()
    if any(k in text for k in _APPROVAL_HINTS):
        raise HTTPException(
            status_code=403,
            detail="学生身份没有审批权限：请假由班主任在系统里审批，你可以查一下自己的审批进度。",
        )
    if not leave_parser.has_time_expression(text) and not any(k in text for k in _LEAVE_WORDS):
        raise HTTPException(
            status_code=400,
            detail="这段话里没有识别到请假时间或事由，暂时无法提交；请说明哪天请假、请多久、什么原因。",
        )


@router.post("/leave-apply", response_model=ResponseModel, summary="学生提交请假申请（自动解析时间）")
def leave_apply(
    data: LeaveApply,
    db: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(require_service),
):
    _guard_leave_apply(data.reason)
    start_time, end_time = data.start_time, data.end_time
    parsed = False
    if not start_time or not end_time:
        start_time, end_time = leave_parser.parse_leave_time(data.reason)
        parsed = True

    # 提交时就把该学生的班主任写进 approver_id，
    # 这样「待审批」也能明确告诉学生「在等哪位老师批」。
    teacher = leave_service.teacher_of(db, data.student_id)

    # 库里存本地时间（SQLite 的 CURRENT_TIMESTAMP 是 UTC，演示时会和"刚刚提交"差 8 小时）
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur = db.cursor()
    cur.execute(
        """INSERT INTO student_admin_service
           (student_id, service_type, start_time, end_time, reason, status, approver_id,
            create_time, update_time)
           VALUES (?, ?, ?, ?, ?, '待审批', ?, ?, ?)""",
        (
            data.student_id, data.service_type, start_time, end_time, data.reason,
            teacher["id"] if teacher else None, now, now,
        ),
    )
    db.commit()

    record = leave_service.get_record(db, cur.lastrowid)

    student = auth_service.profile(db, data.student_id)
    log_service.write(
        db,
        actor=student,
        action="leave_apply",
        summary=f"提交请假：{record['period_text'] if isinstance(record, dict) and record.get('period_text') else data.reason[:40]}",
        detail=f"事由：{data.reason}｜等待 {teacher['name'] if teacher else '班主任'} 审批",
        target_type="leave",
        target_id=cur.lastrowid,
    )

    return ResponseModel(
        msg=(
            f"请假申请已提交，等待班主任{teacher['name']}审批"
            if teacher else "请假申请已提交，等待班主任审批"
        ),
        data={
            "parsed_from_text": parsed,
            "teacher": teacher,
            "record": record,
        },
    )


@router.get("/leave-list", response_model=ResponseModel, summary="查询请假/行政申请（带审批人姓名）")
def leave_list(
    student_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    sql = "SELECT * FROM student_admin_service WHERE 1=1"
    args = []
    sid = _query_int(student_id, 1)
    if sid is not None:
        sql += " AND student_id = ?"
        args.append(sid)
    if status:
        sql += " AND status = ?"
        args.append(status)
    sql += " ORDER BY id DESC LIMIT 20"
    rows = [leave_service.enrich(db, r) for r in db.execute(sql, args).fetchall()]
    teacher = leave_service.teacher_of(db, sid) if sid is not None else None
    pending = sum(1 for r in rows if r["is_pending"])
    return ResponseModel(
        msg=f"共 {len(rows)} 条记录，其中 {pending} 条待审批",
        data={"teacher": teacher, "total": len(rows), "pending": pending, "records": rows},
    )


@router.put("/leave-approve/{record_id}", response_model=ResponseModel, summary="请假审批")
def leave_approve(
    record_id: int,
    data: LeaveApprove,
    db: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(require_service),
):
    record = leave_service.approve(
        db,
        record_id=record_id,
        approver_id=data.approver_id,
        approved=data.approved,
        comment=data.comment,
    )
    return ResponseModel(
        msg=f"审批完成：{record['status_text']}，审批人 {record['approver_name']}",
        data=record,
    )


# ---------------------------------------------------------------------------
# 学生侧：情绪评估与预警（FR-009 ~ FR-011）
# ---------------------------------------------------------------------------

@router.post("/emotion-evaluate", response_model=ResponseModel, summary="情绪评估 + 心理画像 + 高危预警")
def emotion_evaluate(
    data: EmotionEvaluate,
    db: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(require_service),
):
    result = emotion_engine.evaluate(data.text, data.emotion_tag, data.emotion_score)

    # 1. 沉淀对话记录
    db.execute(
        """INSERT INTO conversation_log (user_id, agent_type, user_input, ai_output, emotion_tag)
           VALUES (?, 'STUDENT', ?, ?, ?)""",
        (data.student_id, data.text, None, result["emotion_tag"]),
    )
    db.commit()

    # 2. 累积心理画像
    update_psych_profile(db, data.student_id, result["emotion_tag"], result["emotion_score"])

    # 3. 阈值判断 → 写预警
    alert_id = None
    if result["need_alert"]:
        alert_id = check_and_create_alert(
            db,
            student_id=data.student_id,
            trigger_reason=f"情绪评估命中[{result['basis']}]，原话：{data.text}",
            risk_level="高",
        )
        message = "已触发高危预警并通知班主任，请尽快关注该学生。"
    elif result["need_watch"]:
        message = "情绪状态需要关注，已记录到心理画像，建议班主任适时沟通。"
    else:
        message = "情绪状态平稳，已记录到心理画像。"

    return ResponseModel(
        msg=message,
        data={
            "student_id": data.student_id,
            "emotion_tag": result["emotion_tag"],
            "emotion_score": result["emotion_score"],
            "risk_level": result["risk_level"],
            "alerted": result["need_alert"],
            "alert_id": alert_id,
            "basis": result["basis"],
            "message": message,
        },
    )


@router.get("/psych-profile/{student_id}", response_model=ResponseModel, summary="查询心理画像")
def psych_profile(student_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute(
        "SELECT * FROM student_psych_profile WHERE student_id = ?", (student_id,)
    ).fetchone()
    if not row:
        return ResponseModel(msg="暂无心理画像记录", data=None)
    data = dict(row)
    if data.get("emotion_history"):
        try:
            data["emotion_history"] = json.loads(data["emotion_history"])
        except (json.JSONDecodeError, TypeError):
            pass
    return ResponseModel(data=data)


@router.get("/alert-list", response_model=ResponseModel, summary="预警列表")
def alert_list(
    status: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    sql = "SELECT * FROM student_psych_alert WHERE 1=1"
    args = []
    if status:
        sql += " AND status = ?"
        args.append(status)
    sql += " ORDER BY id DESC LIMIT 20"
    return ResponseModel(data=[dict(r) for r in db.execute(sql, args).fetchall()])


# ---------------------------------------------------------------------------
# 学生侧：售后反馈（FR-012 ~ FR-014）
# ---------------------------------------------------------------------------

_SENSITIVE = ("api key", "apikey", "api_key", "密钥", "连接串", "私钥", "数据库账号", "access token")
_REQUEST_WORDS = ("发我", "给我", "告诉我", "提供", "发一下", "给我一份", "贴给我", "输出", "打印", "发过来")


def _guard_feedback(content: str) -> None:
    """售后工单只收真实反馈，不收"把密钥发我"这类越权要求。"""
    text = (content or "").lower()
    if any(k in text for k in _SENSITIVE) and any(w in text for w in _REQUEST_WORDS):
        raise HTTPException(
            status_code=403,
            detail="系统不会通过对话提供密钥、密码或数据库连接信息，这类请求已拒绝，也不会生成工单。",
        )


@router.post("/feedback-create", response_model=ResponseModel, summary="提交售后反馈工单")
def feedback_create(
    data: FeedbackCreate,
    db: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(require_service),
):
    _guard_feedback(data.content)
    cur = db.cursor()
    cur.execute(
        """INSERT INTO student_feedback_ticket (student_id, content, detail, status)
           VALUES (?, ?, ?, '待处理')""",
        (data.student_id, data.content, data.detail),
    )
    db.commit()
    row = dict(db.execute(
        "SELECT * FROM student_feedback_ticket WHERE id = ?", (cur.lastrowid,)
    ).fetchone())
    return ResponseModel(msg="反馈已提交，工单已创建", data=row)


@router.get("/feedback-list", response_model=ResponseModel, summary="查询反馈工单")
def feedback_list(
    student_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    sql = "SELECT * FROM student_feedback_ticket WHERE 1=1"
    args = []
    if student_id is not None:
        sql += " AND student_id = ?"
        args.append(student_id)
    if status:
        sql += " AND status = ?"
        args.append(status)
    sql += " ORDER BY id DESC LIMIT 20"
    rows = [dict(r) for r in db.execute(sql, args).fetchall()]
    return ResponseModel(msg=f"共 {len(rows)} 条工单", data=rows)


@router.put("/feedback-resolve/{ticket_id}", response_model=ResponseModel, summary="工单解决并通知学生")
def feedback_resolve(ticket_id: int, data: FeedbackResolve, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM student_feedback_ticket WHERE id = ?", (ticket_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="工单不存在")
    db.execute(
        """UPDATE student_feedback_ticket
           SET status='已解决', solution=?, is_notified=1, update_time=CURRENT_TIMESTAMP
           WHERE id=?""",
        (data.solution, ticket_id),
    )
    db.commit()
    return ResponseModel(msg="工单已解决，已通知学生")


# ---------------------------------------------------------------------------
# 学生侧：成绩查询（FR-015）
# ---------------------------------------------------------------------------

@router.get("/score-list", response_model=ResponseModel, summary="学生查询本人成绩（支持按课程过滤）")
def score_list(
    student_id: Optional[str] = Query(None),
    course: Optional[str] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    sid = _query_int(student_id, 1) or 1
    sql = "SELECT * FROM student_score WHERE student_id = ?"
    args: list[Any] = [sid]
    if course:
        sql += " AND course_name LIKE ?"
        args.append(f"%{course}%")
    rows = [dict(r) for r in db.execute(sql + " ORDER BY id DESC", args).fetchall()]
    if not rows:
        return ResponseModel(msg="暂无成绩记录", data=[])
    avg = round(sum(r["score"] for r in rows) / len(rows), 1)
    return ResponseModel(
        msg=f"共 {len(rows)} 门课程成绩，平均 {avg} 分",
        data=rows,
    )


# ---------------------------------------------------------------------------
# 员工侧：CRM（FR-016 ~ FR-018）
# ---------------------------------------------------------------------------

@router.post("/lead-create", response_model=ResponseModel, summary="录入意向客户")
def lead_create(
    data: LeadCreate,
    db: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(require_service),
):
    # 没指定负责人时按「手上线索最少」轮询分配，
    # 否则线上留资会全部堆给同一个人（之前写死 emp003，其他顾问永远分不到）
    owner = data.owner_employee_id
    if not owner:
        pick = db.execute(
            "SELECT u.id, COUNT(l.id) AS n FROM sys_user u "
            "LEFT JOIN crm_lead l ON l.owner_employee_id = u.id "
            "WHERE u.user_type='EMPLOYEE' AND u.employee_role='普通员工' "
            "AND u.department LIKE '%咨询%' "
            "GROUP BY u.id ORDER BY n ASC, u.id ASC LIMIT 1"
        ).fetchone()
        owner = pick["id"] if pick else 3

    cur = db.cursor()
    cur.execute(
        """INSERT INTO crm_lead
           (customer_name, contact_info, background_info, follow_up_history, status, owner_employee_id)
           VALUES (?, ?, ?, ?, '新增意向', ?)""",
        (data.customer_name, data.contact_info, data.background_info,
         data.follow_up_history, owner),
    )
    db.commit()
    # 有手机号的线索自动进试听班，Dify 侧录入也一样
    class_service.attach_lead(db, cur.lastrowid)
    row = dict(db.execute("SELECT * FROM crm_lead WHERE id = ?", (cur.lastrowid,)).fetchone())
    return ResponseModel(msg="意向客户已录入", data=row)


@router.get("/lead-search", response_model=ResponseModel, summary="查询意向客户（支持关键词模糊匹配）")
def lead_search(
    keyword: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    owner_employee_id: Optional[int] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    sql = "SELECT * FROM crm_lead WHERE 1=1"
    args = []
    if keyword:
        sql += " AND (customer_name LIKE ? OR background_info LIKE ? OR follow_up_history LIKE ?)"
        like = f"%{keyword}%"
        args += [like, like, like]
    if status:
        sql += " AND status = ?"
        args.append(status)
    if owner_employee_id is not None:
        sql += " AND owner_employee_id = ?"
        args.append(owner_employee_id)
    sql += " ORDER BY id DESC LIMIT 20"
    rows = [dict(r) for r in db.execute(sql, args).fetchall()]
    if not rows:
        return ResponseModel(msg="未找到符合条件的客户", data=[])
    return ResponseModel(msg=f"共 {len(rows)} 条客户记录", data=rows)


@router.put("/lead-status/{lead_id}", response_model=ResponseModel, summary="客户状态流转")
def lead_status(
    lead_id: int,
    data: LeadStatusUpdate,
    db: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(require_service),
):
    if data.status not in LEAD_STATUS:
        raise HTTPException(
            status_code=400,
            detail=f"非法状态：{data.status}，仅支持 {'/'.join(LEAD_STATUS)}",
        )
    row = db.execute("SELECT * FROM crm_lead WHERE id = ?", (lead_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="客户不存在")
    db.execute(
        "UPDATE crm_lead SET status=?, update_time=CURRENT_TIMESTAMP WHERE id=?",
        (data.status, lead_id),
    )
    db.commit()
    class_service.attach_lead(db, lead_id)
    return ResponseModel(
        msg=f"客户状态已由【{row['status']}】流转为【{data.status}】",
        data={"id": lead_id, "from": row["status"], "to": data.status},
    )


class LeadStatusByName(BaseModel):
    customer_name: str
    status: str


@router.put("/lead-status-by-name", response_model=ResponseModel, summary="按客户姓名流转状态")
def lead_status_by_name(
    data: LeadStatusByName,
    db: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(require_service),
):
    """Dify 里拿不到上一步 HTTP 响应的字段，所以提供按姓名直接流转的入口。"""
    if data.status not in LEAD_STATUS:
        raise HTTPException(
            status_code=400,
            detail=f"非法状态：{data.status}，仅支持 {'/'.join(LEAD_STATUS)}",
        )
    rows = db.execute(
        "SELECT * FROM crm_lead WHERE customer_name LIKE ? ORDER BY id DESC",
        (f"%{data.customer_name}%",),
    ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail=f"未找到客户【{data.customer_name}】")
    if len(rows) > 1:
        names = "、".join(r["customer_name"] for r in rows)
        raise HTTPException(status_code=400, detail=f"匹配到多个客户（{names}），请提供更完整的姓名")

    row = rows[0]
    db.execute(
        "UPDATE crm_lead SET status=?, update_time=CURRENT_TIMESTAMP WHERE id=?",
        (data.status, row["id"]),
    )
    db.commit()
    class_service.attach_lead(db, row["id"])
    return ResponseModel(
        msg=f"客户【{row['customer_name']}】状态已由【{row['status']}】流转为【{data.status}】",
        data={"id": row["id"], "customer_name": row["customer_name"], "from": row["status"], "to": data.status},
    )


# ---------------------------------------------------------------------------
# 员工侧：客户详情与字段更新（FR-017）
# ---------------------------------------------------------------------------

@router.get("/lead-detail/{lead_id}", response_model=ResponseModel, summary="客户详情")
def lead_detail(lead_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute(
        "SELECT l.*, u.real_name AS owner_name FROM crm_lead l "
        "LEFT JOIN sys_user u ON u.id = l.owner_employee_id WHERE l.id = ?",
        (lead_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="客户不存在")
    return ResponseModel(data=dict(row))


class LeadUpdate(BaseModel):
    contact_info: Optional[str] = None
    background_info: Optional[str] = None
    follow_up_history: Optional[str] = None
    status: Optional[str] = None


@router.put("/lead-update/{lead_id}", response_model=ResponseModel, summary="更新客户背景与跟进记录")
def lead_update(
    lead_id: int,
    data: LeadUpdate,
    db: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(require_service),
):
    row = db.execute("SELECT * FROM crm_lead WHERE id = ?", (lead_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="客户不存在")
    if data.status and data.status not in LEAD_STATUS:
        raise HTTPException(status_code=400, detail=f"非法状态：{data.status}")
    if not any([data.contact_info, data.background_info, data.follow_up_history, data.status]):
        raise HTTPException(status_code=400, detail="没有需要更新的字段")

    fields, args = [], []
    for key in ("contact_info", "background_info", "follow_up_history", "status"):
        value = getattr(data, key)
        if value is not None:
            fields.append(f"{key} = ?")
            args.append(value)
    fields.append("update_time = CURRENT_TIMESTAMP")
    args.append(lead_id)
    db.execute(f"UPDATE crm_lead SET {', '.join(fields)} WHERE id = ?", args)
    db.commit()

    updated = dict(db.execute("SELECT * FROM crm_lead WHERE id = ?", (lead_id,)).fetchone())
    return ResponseModel(msg=f"客户【{updated['customer_name']}】资料已更新", data=updated)


# ---------------------------------------------------------------------------
# 员工侧：日报与成绩录入（FR-019 / FR-020）
# ---------------------------------------------------------------------------

@router.post("/report-create", response_model=ResponseModel, summary="提交员工日报")
def report_create(
    data: ReportCreate,
    db: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(require_service),
):
    report_date = data.report_date or date.today().isoformat()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = db.cursor()
    cur.execute(
        "INSERT INTO employee_daily_report (employee_id, report_date, content, create_time) VALUES (?, ?, ?, ?)",
        (data.employee_id, report_date, data.content, now),
    )
    db.commit()
    row = dict(db.execute(
        "SELECT * FROM employee_daily_report WHERE id = ?", (cur.lastrowid,)
    ).fetchone())
    return ResponseModel(msg="日报已记录", data=row)


def _score_upper(course_name: str) -> float:
    """雅思 9 分制、托福 120 分制，其余按百分制。"""
    if "雅思" in course_name:
        return 9.0
    if "托福" in course_name:
        return 120.0
    return 100.0


def _score_limit_detail(course_name: str) -> str:
    if "雅思" in course_name:
        return f"【{course_name}】按雅思 9 分制，成绩必须在 0~9 之间"
    if "托福" in course_name:
        return f"【{course_name}】按托福 120 分制，成绩必须在 0~120 之间"
    return f"【{course_name}】按百分制，成绩必须在 0~100 之间"


def _current_semester(today: Optional[date] = None) -> str:
    """按日期推算当前学期，格式与库里一致：2025-2026 第一学期。"""
    d = today or date.today()
    y = d.year
    if d.month >= 9:          # 9-12 月：本学年第一学期
        return f"{y}-{y + 1} 第一学期"
    if d.month == 1:          # 1 月仍属上一学年的第一学期
        return f"{y - 1}-{y} 第一学期"
    return f"{y - 1}-{y} 第二学期"


def _guess_semester(db: sqlite3.Connection, student_id: int) -> str:
    """没指定学期时：沿用该生最近一条成绩的学期，没有历史再用当前学期。

    为什么必须给默认值：录完不填学期，表里就是「未填学期」，
    老师回头问「这是哪个学期的成绩」根本无从回答——现场就是这么卡住的。
    沿用该生已有学期比按系统时间推算更贴近实际（补录、跨学期批量录都能对上）。
    """
    row = db.execute(
        "SELECT semester FROM student_score WHERE student_id = ? "
        "AND semester IS NOT NULL AND semester != '' ORDER BY id DESC LIMIT 1",
        (student_id,),
    ).fetchone()
    return row["semester"] if row else _current_semester()


def _upsert_score(
    db: sqlite3.Connection,
    student_id: int,
    student_name: Optional[str],
    course_name: str,
    score: float,
    semester: Optional[str],
    overwrite: bool,
) -> ResponseModel:
    """录成绩：同学生 + 同课程 + 同学期已存在时不重复插入，除非显式 overwrite。

    不这么做的后果是库里出现「雅思听力 6.5」和「雅思听力 150」两条并存，
    学生查这门课平均分直接算错。
    """
    upper = _score_upper(course_name)
    if score < 0 or score > upper:
        raise HTTPException(status_code=400, detail=_score_limit_detail(course_name))

    semester_auto = False
    if not semester:
        semester = _guess_semester(db, student_id)
        semester_auto = True
    sem_note = f"（{semester}{'，未指定时按该生所在学期归档' if semester_auto else ''}）"

    sql = "SELECT * FROM student_score WHERE student_id = ? AND course_name = ?"
    args = [student_id, course_name]
    if semester:
        sql += " AND semester = ?"
        args.append(semester)
    existing = db.execute(sql + " ORDER BY id DESC LIMIT 1", args).fetchone()

    label = f"【{student_name}】" if student_name else ""

    if existing and not overwrite:
        return ResponseModel(
            msg=(
                f"{label}已有【{course_name}】成绩 {existing['score']} 分"
                f"（{existing['semester'] or '学期未填'}），本次没有重复录入。"
                f"如果要改成 {score} 分，请回复「覆盖」"
            ),
            data={
                "duplicated": True,
                "need_confirm": True,
                "student_id": student_id,
                "student_name": student_name,
                "course_name": course_name,
                "existing_id": existing["id"],
                "existing_score": existing["score"],
                "semester": existing["semester"] or semester,
                "semester_auto": semester_auto,
                "new_score": score,
            },
        )

    if existing:
        old = existing["score"]
        db.execute("UPDATE student_score SET score = ? WHERE id = ?", (score, existing["id"]))
        db.commit()
        return ResponseModel(
            msg=f"{label}的【{course_name}】成绩已从 {old} 分改为 {score} 分{sem_note}",
            data={
                "updated": True,
                "id": existing["id"],
                "student_id": student_id,
                "student_name": student_name,
                "course_name": course_name,
                "old_score": old,
                "score": score,
                "semester": existing["semester"] or semester,
                "semester_auto": semester_auto,
            },
        )

    cur = db.cursor()
    cur.execute(
        "INSERT INTO student_score (student_id, course_name, score, semester) VALUES (?, ?, ?, ?)",
        (student_id, course_name, score, semester),
    )
    db.commit()
    return ResponseModel(
        msg=f"已为{label or '该学生'}录入【{course_name}】成绩 {score} 分{sem_note}",
        data={
            "id": cur.lastrowid,
            "student_id": student_id,
            "student_name": student_name,
            "course_name": course_name,
            "score": score,
            "semester": semester,
            "semester_auto": semester_auto,
        },
    )


@router.post("/score-create", response_model=ResponseModel, summary="员工录入学生成绩（同课同学期自动去重）")
def score_create(
    data: ScoreCreate,
    db: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(require_service),
):
    student = db.execute(
        "SELECT id, real_name FROM sys_user WHERE id = ?", (data.student_id,)
    ).fetchone()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    return _upsert_score(
        db, data.student_id, student["real_name"], data.course_name,
        data.score, data.semester, data.overwrite,
    )


class ScoreCreateByName(BaseModel):
    student_name: str
    course_name: str
    score: float
    semester: Optional[str] = None
    overwrite: bool = False


@router.post("/score-create-by-name", response_model=ResponseModel, summary="按学生姓名录入成绩（同课同学期自动去重）")
def score_create_by_name(
    data: ScoreCreateByName,
    db: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(require_service),
):
    rows = db.execute(
        "SELECT * FROM sys_user WHERE user_type='STUDENT' AND real_name LIKE ?",
        (f"%{data.student_name}%",),
    ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail=f"未找到学生【{data.student_name}】")
    if len(rows) > 1:
        names = "、".join(r["real_name"] for r in rows)
        raise HTTPException(status_code=400, detail=f"匹配到多名学生（{names}），请提供更完整的姓名")

    student = rows[0]
    return _upsert_score(
        db, student["id"], student["real_name"], data.course_name,
        data.score, data.semester, data.overwrite,
    )


# ---------------------------------------------------------------------------
# 员工侧：NL2SQL 口语查询（FR-021）
# ---------------------------------------------------------------------------

@router.post("/nl2sql", response_model=ResponseModel, summary="口语化查询（NL2SQL：意图 + SQL + 结果）")
def nl2sql(data: NL2SQLQuery, db: sqlite3.Connection = Depends(get_db)):
    """把员工的口语问题翻译成一条 SELECT，并把 SQL 原文一起返回。

    SQL 只用于展示与复核（回答里会附一句"查询语句"），执行走参数化占位符。
    带 conversation_id 时顺带做多轮指代消解：「这是哪个学期的成绩」这种追问
    本身不含人名/课程，要回到上文里捞实体，否则只能生成 WHERE 1=1 倒全表。
    """
    history = data.history or session_memory.hint(data.conversation_id or "")
    result = nl2sql_service.run(
        db, data.query, nl2sql_service.build_ctx(db, data.user_id), history=history
    )
    return ResponseModel(msg=result["summary"], data=result)


@router.get("/scores", response_model=ResponseModel, summary="员工成绩册（按班级/课程/分数筛选）")
def score_book(
    class_name: Optional[str] = Query(None, description="班级或方向关键字，如 2025级、新加坡、德国"),
    course: Optional[str] = Query(None, description="课程名模糊匹配"),
    below: Optional[float] = Query(None, description="只看低于该分数的记录，例如 60"),
    teacher_id: Optional[int] = Query(None, description="只看该班主任名下学生"),
    include_standardized: bool = Query(False, description="是否把雅思/托福也算进来（默认排除，避免量纲混淆）"),
    db: sqlite3.Connection = Depends(get_db),
):
    """老师能录成绩，就必须能成批地看成成绩——这是「能写不能读」的补位。

    和 score-list（学生查本人）不同，这里是按班级/课程/分数维度看整册。
    """
    sql = (
        "SELECT s.id, s.student_id, u.real_name AS student_name, u.department, "
        "s.course_name, s.score, s.semester FROM student_score s "
        "JOIN sys_user u ON u.id = s.student_id WHERE 1=1"
    )
    args: list = []
    if class_name:
        # 库里是「国际学院 2025 级 · 新加坡方向」，中间带空格，先去掉空格再匹配
        sql += " AND REPLACE(u.department, ' ', '') LIKE ?"
        args.append(f"%{class_name.replace(' ', '')}%")
    if course:
        sql += " AND s.course_name LIKE ?"
        args.append(f"%{course}%")
    if below is not None:
        sql += " AND s.score < ?"
        args.append(below)
        if not include_standardized:
            sql += " AND s.course_name NOT LIKE '%雅思%' AND s.course_name NOT LIKE '%托福%'"
    if teacher_id:
        sql += " AND u.homeroom_teacher_id = ?"
        args.append(teacher_id)
    sql += " ORDER BY u.real_name, s.course_name"

    rows = [dict(r) for r in db.execute(sql, args).fetchall()]
    if not rows:
        return ResponseModel(msg="没有符合条件的成绩记录", data={"rows": [], "total": 0, "students": 0})

    students = len({r["student_id"] for r in rows})
    # 平均分只在同一量纲下有意义：雅思/托福单独统计
    pct = [r["score"] for r in rows if "雅思" not in r["course_name"] and "托福" not in r["course_name"]]
    avg = round(sum(pct) / len(pct), 1) if pct else None
    failed = [r for r in pct if r < 60]
    msg = f"{students} 名学生、{len(rows)} 条成绩"
    if avg is not None:
        msg += f"，百分制平均 {avg} 分"
    if failed:
        msg += f"，其中 {len(failed)} 条不及格"

    return ResponseModel(
        msg=msg,
        data={
            "rows": rows,
            "total": len(rows),
            "students": students,
            "avg": avg,
            "failed": len(failed),
        },
    )


@router.get("/parent-view", response_model=ResponseModel, summary="家长查看孩子成绩/请假/活动（按亲属关系限定）")
def parent_view(
    parent_id: int = Query(..., description="家长的用户 ID"),
    db: sqlite3.Connection = Depends(get_db),
):
    """家长只允许看自己孩子；这条链路之前是断的——家长问「孩子考了多少分」只能答「找顾问确认」。"""
    parent = db.execute(
        "SELECT * FROM sys_user WHERE id = ? AND user_type = 'PARENT'", (parent_id,)
    ).fetchone()
    if not parent:
        raise HTTPException(status_code=404, detail="不是家长账号")

    sid = parent["parent_of_student_id"]
    if not sid:
        return ResponseModel(msg="这个账号还没有绑定学生，请联系教务老师", data={"bound": False})

    student = db.execute("SELECT * FROM sys_user WHERE id = ?", (sid,)).fetchone()
    if not student:
        return ResponseModel(msg="绑定的学生档案不存在，请联系教务老师", data={"bound": False})

    scores = [
        dict(r)
        for r in db.execute(
            "SELECT course_name, score, semester FROM student_score WHERE student_id = ? ORDER BY id DESC",
            (sid,),
        ).fetchall()
    ]
    leaves = [
        dict(r)
        for r in db.execute(
            "SELECT id, service_type, start_time, end_time, reason, status FROM student_admin_service "
            "WHERE student_id = ? ORDER BY id DESC LIMIT 5",
            (sid,),
        ).fetchall()
    ]
    # 报名记录的 customer_id 指向 crm_lead.id，不是用户 id，所以按孩子姓名关联
    events = [
        dict(r)
        for r in db.execute(
            "SELECT e.event_name, e.start_time, e.location, r.status FROM event_registration r "
            "JOIN event_lecture e ON e.id = r.event_id "
            "JOIN crm_lead l ON l.id = r.customer_id "
            "WHERE l.customer_name = ? ORDER BY r.id DESC LIMIT 5",
            (student["real_name"],),
        ).fetchall()
    ]

    pct = [s["score"] for s in scores if "雅思" not in s["course_name"] and "托福" not in s["course_name"]]
    avg = round(sum(pct) / len(pct), 1) if pct else None

    return ResponseModel(
        msg=f"已查到 {student['real_name']} 的成绩、请假和活动记录",
        data={
            "bound": True,
            "student": {
                "id": student["id"],
                "name": student["real_name"],
                "department": student["department"],
            },
            "scores": scores,
            "avg": avg,
            "leaves": leaves,
            "events": events,
        },
    )


@router.put("/alert-status/{alert_id}", response_model=ResponseModel, summary="心理预警状态流转（认领/解除）")
def alert_status(
    alert_id: int,
    data: dict,
    db: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(require_service),
):
    """预警只能看不能处理，等于高危学生没有闭环。这里补上认领（跟进中）与解除。"""
    status = (data or {}).get("status")
    if status not in ("未处理", "跟进中", "已解除"):
        raise HTTPException(status_code=400, detail="状态只能是 未处理 / 跟进中 / 已解除")
    row = db.execute("SELECT * FROM student_psych_alert WHERE id = ?", (alert_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="预警记录不存在")
    db.execute("UPDATE student_psych_alert SET status = ? WHERE id = ?", (status, alert_id))
    db.commit()
    return ResponseModel(
        msg=f"已把这条预警从「{row['status']}」改为「{status}」",
        data={"id": alert_id, "old_status": row["status"], "status": status},
    )


@router.put("/alert-status-by-name", response_model=ResponseModel, summary="按学生姓名流转预警状态（认领/解除）")
def alert_status_by_name(
    data: dict,
    db: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(require_service),
):
    """员工说的是「把张三的预警标记为跟进中」，手里没有预警 ID，所以按姓名定位。"""
    student_name = (data or {}).get("student_name") or ""
    status = (data or {}).get("status")
    if status not in ("未处理", "跟进中", "已解除"):
        raise HTTPException(status_code=400, detail="状态只能是 未处理 / 跟进中 / 已解除")

    students = db.execute(
        "SELECT id, real_name FROM sys_user WHERE user_type='STUDENT' AND real_name LIKE ?",
        (f"%{student_name}%",),
    ).fetchall()
    if not students:
        raise HTTPException(status_code=404, detail=f"未找到学生【{student_name}】")
    if len(students) > 1:
        names = "、".join(r["real_name"] for r in students)
        raise HTTPException(status_code=400, detail=f"匹配到多名学生（{names}），请提供更完整的姓名")

    student = students[0]
    alert = db.execute(
        "SELECT * FROM student_psych_alert WHERE student_id = ? ORDER BY id DESC LIMIT 1",
        (student["id"],),
    ).fetchone()
    if not alert:
        return ResponseModel(
            msg=f"【{student['real_name']}】目前没有心理预警记录，不需要处理",
            data={"student_name": student["real_name"], "has_alert": False},
        )

    db.execute("UPDATE student_psych_alert SET status = ? WHERE id = ?", (status, alert["id"]))
    db.commit()
    return ResponseModel(
        msg=f"已把【{student['real_name']}】的预警从「{alert['status']}」改为「{status}」",
        data={
            "student_name": student["real_name"],
            "alert_id": alert["id"],
            "risk_level": alert["risk_level"],
            "old_status": alert["status"],
            "status": status,
        },
    )


# ---------------------------------------------------------------------------
# 客服侧：画像研判推荐（FR-001 ~ FR-005，共享工具）
# ---------------------------------------------------------------------------

@router.post("/profile-evaluate", response_model=ResponseModel, summary="画像研判与留学项目推荐")
def profile_evaluate(data: ProfileEvaluate):
    result = recommend(data.model_dump())
    return ResponseModel(msg=result["summary"], data=result)


# ---------------------------------------------------------------------------
# 客服侧：项目与活动（FR-023 ~ FR-027）
# ---------------------------------------------------------------------------

@router.get("/project-list", response_model=ResponseModel, summary="课程/项目查询")
def project_list(
    keyword: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    detail: Optional[str] = Query(None, description="项目ID或项目名（模糊）"),
    db: sqlite3.Connection = Depends(get_db),
):
    sql = "SELECT * FROM course_project WHERE 1=1"
    args = []
    if detail:
        if detail.isdigit():
            sql += " AND id = ?"
            args.append(int(detail))
        else:
            sql += " AND project_name LIKE ?"
            args.append(f"%{detail}%")
    if keyword:
        sql += " AND (project_name LIKE ? OR description LIKE ? OR target_audience LIKE ?)"
        like = f"%{keyword}%"
        args += [like, like, like]
    if category:
        sql += " AND category = ?"
        args.append(category)
    rows = [dict(r) for r in db.execute(sql, args).fetchall()]
    if not rows:
        return ResponseModel(msg="未找到匹配的项目", data=[])
    return ResponseModel(msg=f"共 {len(rows)} 个项目", data=rows)


@router.get("/event-list", response_model=ResponseModel, summary="活动/讲座查询（支持按类型过滤）")
def event_list(
    keyword: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
    upcoming: Optional[bool] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    sql = "SELECT * FROM event_lecture WHERE 1=1"
    args: list[Any] = []
    if keyword:
        sql += " AND event_name LIKE ?"
        args.append(f"%{keyword}%")
    if type:
        sql += " AND event_type = ?"
        args.append(type)
    if upcoming:
        sql += " AND start_time >= datetime('now', 'localtime')"
    sql += " ORDER BY start_time ASC"
    rows = [dict(r) for r in db.execute(sql, args).fetchall()]
    for r in rows:
        r["remaining"] = r["max_participants"] - r["current_participants"]
    if not rows:
        return ResponseModel(msg="暂无活动", data=[])
    return ResponseModel(msg=f"共 {len(rows)} 场活动", data=rows)


@router.get("/event-registrations", response_model=ResponseModel, summary="活动报名记录查询")
def event_registrations(
    event_id: Optional[int] = Query(None),
    customer_id: Optional[int] = Query(None),
    db: sqlite3.Connection = Depends(get_db),
):
    sql = (
        "SELECT r.id, r.event_id, e.event_name, e.start_time, e.location, "
        "r.customer_id, u.real_name AS customer_name, r.status, r.create_time "
        "FROM event_registration r "
        "LEFT JOIN event_lecture e ON e.id = r.event_id "
        "LEFT JOIN sys_user u ON u.id = r.customer_id WHERE 1=1"
    )
    args: list[Any] = []
    if event_id is not None:
        sql += " AND r.event_id = ?"
        args.append(event_id)
    if customer_id is not None:
        sql += " AND r.customer_id = ?"
        args.append(customer_id)
    sql += " ORDER BY r.id DESC LIMIT 50"
    rows = [dict(r) for r in db.execute(sql, args).fetchall()]
    return ResponseModel(msg=f"共 {len(rows)} 条报名记录", data=rows)


@router.post("/event-register", response_model=ResponseModel, summary="活动报名（校验名额并累加）")
def event_register(
    data: EventRegister,
    soft_fail: bool = Query(
        False,
        description="业务失败也返回 200 并在 data.reason 里给出真实原因；供对话 Agent 原样转述，避免 Dify HTTP 节点用默认值覆盖掉错误详情",
    ),
    db: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(require_service),
):
    def biz_fail(reason: str, msg: str, **extra):
        """业务性失败：给真实原因，不让人猜。"""
        if soft_fail:
            return ResponseModel(msg=msg, data={"success": False, "reason": reason, **extra})
        raise HTTPException(status_code=400, detail=msg)

    if data.event_id:
        event = db.execute("SELECT * FROM event_lecture WHERE id = ?", (data.event_id,)).fetchone()
    elif data.event_name:
        event = db.execute(
            "SELECT * FROM event_lecture WHERE event_name LIKE ? ORDER BY start_time ASC LIMIT 1",
            (f"%{data.event_name}%",),
        ).fetchone()
    else:
        return biz_fail("缺少参数", "请提供活动 ID 或活动名称")

    if not event:
        if soft_fail:
            return ResponseModel(
                msg=f"没有找到名称匹配「{data.event_name}」的活动，请确认活动名称",
                data={"success": False, "reason": "活动不存在", "query": data.event_name},
            )
        raise HTTPException(status_code=404, detail="活动不存在")

    if event["current_participants"] >= event["max_participants"]:
        return biz_fail(
            "名额已满",
            f"【{event['event_name']}】名额已满（{event['current_participants']}/{event['max_participants']}），报名未成功",
            event_name=event["event_name"],
            current_participants=event["current_participants"],
            max_participants=event["max_participants"],
        )

    # 同一客户报同一场活动只保留一条，重复提交直接告诉他"已经报过"
    existing = db.execute(
        "SELECT id, create_time FROM event_registration WHERE event_id = ? AND customer_id = ?",
        (event["id"], data.customer_id),
    ).fetchone()
    if existing:
        return ResponseModel(
            msg=f"你已报名【{event['event_name']}】，无需重复提交",
            data={
                "registration_id": existing["id"],
                "event_name": event["event_name"],
                "start_time": event["start_time"],
                "location": event["location"],
                "duplicated": True,
                "current_participants": event["current_participants"],
                "max_participants": event["max_participants"],
            },
        )

    cur = db.cursor()
    cur.execute(
        "INSERT INTO event_registration (event_id, customer_id, status) VALUES (?, ?, '已报名')",
        (event["id"], data.customer_id),
    )
    db.execute(
        "UPDATE event_lecture SET current_participants = current_participants + 1 WHERE id = ?",
        (event["id"],),
    )
    db.commit()

    return ResponseModel(
        msg=f"报名成功：{event['event_name']}",
        data={
            "registration_id": cur.lastrowid,
            "event_name": event["event_name"],
            "start_time": event["start_time"],
            "location": event["location"],
            "current_participants": event["current_participants"] + 1,
            "max_participants": event["max_participants"],
        },
    )
