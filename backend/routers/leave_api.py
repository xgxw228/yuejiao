"""请假审批（前端面板专用路由，前缀 /api/leave）。

和 /api/agent/leave-* 的分工：
- /api/agent/* 给 Dify 工作流的 HTTP 节点用，返回话术需要的最小字段；
- /api/leave/* 给演示前端的「班主任审批」面板用，返回带学生姓名、班级、
  天数和审批状态的完整视图。
两边共用 services/leave_service.py，不会出现口径不一致。
"""

import hmac
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from config import INTERNAL_TOKEN
from database import get_db
from models.base import ResponseModel
from services import auth_service, leave_service, log_service

router = APIRouter()


class ApproveBody(BaseModel):
    record_id: int
    approver_id: int
    approved: bool = True
    comment: Optional[str] = None


def _actor(db: sqlite3.Connection, authorization: Optional[str]) -> dict:
    """面板接口一律认 token，不认 query 里的 approver_id。

    没这层校验时，随便改个 ?approver_id=9 就能看别的老师名下请假，
    等于隔离形同虚设。
    """
    payload = auth_service.read_token(authorization)
    if not payload:
        raise HTTPException(status_code=401, detail="请先登录")
    me = auth_service.profile(db, payload.get("uid"))
    if not me:
        raise HTTPException(status_code=401, detail="登录信息已失效，请重新登录")
    return me


def _scope(db: sqlite3.Connection, me: dict, approver_id: Optional[int], scope: str) -> tuple[int, bool]:
    """返回（实际审批人, 是否全校视图）。管理员的全校视图才允许 scope=all。"""
    if scope == "all" and me["role"] == "admin":
        return me["id"], True
    if me["role"] == "admin":
        return me["id"], False
    if me["role"] != "teacher":
        raise HTTPException(status_code=403, detail="当前身份没有审批权限")
    # 班主任传别人的 id 也没用，一律按 token 里的本人算
    return me["id"], False


@router.get("/teachers", response_model=ResponseModel, summary="班主任列表（含待办数）")
def list_teachers(
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _actor(db, authorization)
    if me["role"] not in ("admin", "teacher"):
        raise HTTPException(status_code=403, detail="只有班主任和管理员可以查看审批队列")
    rows = leave_service.teachers(db)
    return ResponseModel(msg=f"共 {len(rows)} 位班主任", data=rows)


@router.get("/summary", response_model=ResponseModel, summary="当前身份的审批概览")
def get_summary(
    approver_id: Optional[int] = Query(None, description="兼容旧参数，非管理员会被忽略"),
    scope: str = Query("self", description="self=只看自己名下；all=管理员全校视图"),
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _actor(db, authorization)
    uid, all_view = _scope(db, me, approver_id, scope)
    data = leave_service.summary_all(db, uid) if all_view else leave_service.summary(db, uid)
    return ResponseModel(msg=f"待审批 {data['pending']} 条", data=data)


@router.get("/pending", response_model=ResponseModel, summary="待我审批的请假")
def list_pending(
    approver_id: Optional[int] = Query(None),
    scope: str = Query("self"),
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _actor(db, authorization)
    uid, all_view = _scope(db, me, approver_id, scope)
    rows = leave_service.pending_all(db) if all_view else leave_service.pending_for(db, uid)
    return ResponseModel(msg=f"待审批 {len(rows)} 条", data=rows)


@router.get("/handled", response_model=ResponseModel, summary="我已处理的请假")
def list_handled(
    approver_id: Optional[int] = Query(None),
    scope: str = Query("self"),
    limit: int = Query(8, ge=1, le=50),
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _actor(db, authorization)
    uid, all_view = _scope(db, me, approver_id, scope)
    rows = leave_service.handled_all(db, limit) if all_view else leave_service.handled_by(db, uid, limit)
    return ResponseModel(msg=f"已处理 {len(rows)} 条", data=rows)


@router.get("/student/{student_id}", response_model=ResponseModel, summary="某个学生的请假流程")
def student_history(
    student_id: int,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _actor(db, authorization)
    if me["role"] == "student" and int(me["id"]) != int(student_id):
        raise HTTPException(status_code=403, detail="只能查看自己的请假记录")
    if me["role"] == "teacher":
        teacher = leave_service.teacher_of(db, student_id)
        if not teacher or int(teacher["id"]) != int(me["id"]):
            raise HTTPException(status_code=403, detail="这名学生不在你名下，不能查看")
    if me["role"] not in ("admin", "teacher", "student"):
        raise HTTPException(status_code=403, detail="当前身份不能查看请假记录")

    rows = leave_service.history_of_student(db, student_id)
    teacher = leave_service.teacher_of(db, student_id)
    return ResponseModel(
        msg=f"共 {len(rows)} 条请假记录",
        data={"teacher": teacher, "records": rows},
    )


@router.post("/approve", response_model=ResponseModel, summary="通过/驳回请假（需登录凭证）")
def do_approve(
    body: ApproveBody,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
    x_internal_token: Optional[str] = Header(None, alias="X-Internal-Token"),
):
    """审批必须带凭证，且以**凭证里的身份**为准。

    以前直接信 body.approver_id，等于谁都能替别人批 ——
    现在非管理员即使把 approver_id 写成别人，也会被改回本人。
    """
    approver_id = body.approver_id
    actor = None
    if x_internal_token and hmac.compare_digest(x_internal_token, INTERNAL_TOKEN):
        actor = auth_service.profile(db, approver_id)
    else:
        payload = auth_service.read_token(authorization)
        if not payload:
            raise HTTPException(status_code=401, detail="审批需要登录凭证，请重新登录后再试")
        uid = int(payload.get("uid") or 0)
        actor = auth_service.profile(db, uid)
        if payload.get("role") == "admin":
            # 管理员是「看」不是「批」：请假归学生所在班主任，避免把下属的活干了
            raise HTTPException(
                status_code=403,
                detail="请假由学生所在班主任审批，管理员只在数据后台查看，不代批",
            )
        approver_id = uid

    record = leave_service.approve(
        db,
        record_id=body.record_id,
        approver_id=approver_id,
        approved=body.approved,
        comment=body.comment,
    )
    action = "已通过" if body.approved else "已驳回"
    log_service.write(
        db,
        actor=actor,
        action="leave_approve",
        summary=f"{action}请假：{record['student_name']} · {record['period_text']}",
        detail=(f"意见：{body.comment}" if body.comment else "") or "未填写意见",
        target_type="leave",
        target_id=body.record_id,
    )
    return ResponseModel(
        msg=f"{action}：{record['student_name']} · {record['period_text']}",
        data=record,
    )
