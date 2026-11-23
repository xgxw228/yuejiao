"""登录页公开接口：在线客服留资。

只做一件小事——访客在客服里留下姓名 / 手机号，就写一条 crm_lead，
归到顾问（默认 emp006 陈顾问）名下，后台和顾问侧都能接手跟进。

这个入口不需要登录，所以只开放「写线索」这一个动作：
手机号做格式校验、姓名和意向做长度截断、负责人固定为顾问，
不接受任意外键或状态值，避免匿名入口变成写后门。
"""

import re
import sqlite3
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database import get_db
from services import class_service, log_service

router = APIRouter()

PHONE_RE = re.compile(r"1\d{10}")
CONSULTANT_USERNAME = "emp006"   # 默认接待顾问：陈顾问（咨询三组）
SOURCE_TAG = "登录页在线客服"


class LeadIn(BaseModel):
    phone: str
    name: Optional[str] = None
    intent: Optional[str] = None
    summary: Optional[str] = None


def _clip(value: Optional[str], limit: int) -> str:
    return (value or "").strip().replace("\r", "")[:limit]


def _pick_consultant(db: sqlite3.Connection):
    """按当前手上未流失线索数量，把新线索分给最闲的顾问。

    顾问 = 员工身份、非管理员/领导、名下没有学生（有学生的会被判定成班主任）。
    这样多个顾问时不会全压在同一个人身上，也便于演示"各看各的"。
    """
    rows = db.execute(
        "SELECT u.id, u.real_name, u.contact_info, "
        "  (SELECT COUNT(*) FROM crm_lead l "
        "     WHERE l.owner_employee_id = u.id AND l.status != '已流失') AS load "
        "FROM sys_user u "
        "WHERE u.user_type = 'EMPLOYEE' "
        "  AND COALESCE(u.employee_role,'') NOT IN ('管理员', '领导') "
        "  AND COALESCE(u.status,'正常') = '正常' "
        "  AND u.department LIKE '%咨询%' "  # 只分给咨询顾问，不分给活动/教务老师
        "  AND NOT EXISTS (SELECT 1 FROM sys_user s WHERE s.homeroom_teacher_id = u.id) "
        "ORDER BY load ASC, u.id ASC"
    ).fetchall()
    if rows:
        return rows[0]
    return db.execute(
        "SELECT id, real_name, contact_info FROM sys_user WHERE username = ?", (CONSULTANT_USERNAME,)
    ).fetchone()


def _consultant_label(name: Optional[str]) -> str:
    """称呼统一：已经叫「陈顾问」就原样用，写成「陈静」才补成「顾问陈静」。"""
    name = (name or "顾问").strip()
    return name if name.endswith("顾问") else f"顾问{name}"


def _consultant_contact(owner) -> str:
    """留资后告诉访客负责顾问的电话；顾问没留电话就退回咨询热线。"""
    phone = re.sub(r"\D", "", (owner["contact_info"] or "") if "contact_info" in owner.keys() else "")
    # contact_info 可能是座机/带分机，保留原样更稳妥；纯 11 位手机号才做展示
    if re.fullmatch(r"1\d{10}", phone):
        return phone
    return "020-37628058"


def _handoff_msg(owner, repeated: bool = False) -> str:
    """留资成功后给访客的话：谁负责、怎么联系、什么时候联系。"""
    label = _consultant_label(owner["real_name"])
    extra = "（你之前留过联系方式，这次也记上了）" if repeated else ""
    return (
        f"已记录并转给{label}{extra}，{label}会在工作时间内按你留的号码联系你。"
        f"急的话也可以直接打给{label}：{_consultant_contact(owner)}。"
    )


@router.post("/lead", summary="登录页在线客服：留下联系方式，转给顾问")
def create_lead(body: LeadIn, db: sqlite3.Connection = Depends(get_db)):
    phone = re.sub(r"\D", "", body.phone or "")
    if not PHONE_RE.fullmatch(phone):
        raise HTTPException(status_code=400, detail="手机号格式不对")

    owner = _pick_consultant(db)
    if not owner:
        raise HTTPException(status_code=503, detail="暂未配置接待顾问")

    name = _clip(body.name, 20) or "未留名"
    intent = _clip(body.intent, 120)
    summary = _clip(body.summary, 300)
    stamp = time.strftime("%m-%d %H:%M")

    # 同一个号码还没流失：不重复建档，把这次咨询追加到跟进记录里
    old = db.execute(
        "SELECT id, customer_name FROM crm_lead "
        "WHERE contact_info = ? AND status != '已流失' ORDER BY id DESC LIMIT 1",
        (phone,),
    ).fetchone()
    if old:
        add = f"\n[{stamp}] 再次咨询（{SOURCE_TAG}）：{intent or '—'}｜{summary or '—'}"
        db.execute(
            "UPDATE crm_lead SET background_info = COALESCE(background_info,'') || ?, "
            "follow_up_history = COALESCE(follow_up_history,'') || ?, "
            "update_time = datetime('now','localtime') WHERE id = ?",
            (add, add, old["id"]),
        )
        db.commit()
        log_service.write(
            db,
            action="lead_repeat",
            summary=f"客服再次咨询：{old['customer_name'] or name}（{phone}）",
            detail=f"{intent or '—'}｜{summary or '—'}｜负责人 {owner['real_name']}",
            target_type="lead",
            target_id=old["id"],
        )
        return {
            "ok": True,
            "id": old["id"],
            "consultant": owner["real_name"],
            "consultant_phone": _consultant_contact(owner),
            "repeated": True,
            "msg": _handoff_msg(owner, repeated=True),
        }

    background = (
        f"来源：{SOURCE_TAG}\n"
        f"意向：{intent or '未填写'}\n"
        f"对话摘要：{summary or '—'}"
    )
    # create_time 显式写本地时间：表默认值是 UTC，会让新线索排到旧线索后面
    cur = db.execute(
        "INSERT INTO crm_lead (customer_name, contact_info, background_info, status, owner_employee_id, "
        "create_time, update_time) "
        "VALUES (?, ?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))",
        (name, phone, background, "新增意向", owner["id"]),
    )
    db.commit()
    class_service.attach_lead(db, cur.lastrowid)
    log_service.write(
        db,
        action="lead_create",
        summary=f"客服留资：{name}（{phone}）",
        detail=f"{intent or '—'}｜{summary or '—'}｜负责人 {owner['real_name']}",
        target_type="lead",
        target_id=cur.lastrowid,
    )
    return {
        "ok": True,
        "id": cur.lastrowid,
        "consultant": owner["real_name"],
        "consultant_phone": _consultant_contact(owner),
        "repeated": False,
        "msg": _handoff_msg(owner),
    }
