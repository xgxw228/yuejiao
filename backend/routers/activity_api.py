"""活动安排（前缀 /api/activities）+ 登录页公开报名（/api/public/activities）。

业务口径：
- 顾问设计活动：讲什么、谁来讲、什么时候、多少名额；
- 活动是公开信息，登录页的小粤同学可以推荐，访客报个名就行；
- 名额按「已报名人数 >= 名额」判定，满了直接 409，并给出其它还有名额的活动；
- 报名必须留 11 位手机号（纯数字、1 开头），格式不对回 400「电话格式错误，请重新填写」；
- 报名同时写一条客户线索，归活动创建者（顾问）名下，顾问在活动里点开就能看到人。

权限：
- 顾问：只看自己设计的活动、只能看自己活动的报名人；
- 管理员：可看全部，但活动的增删仍以顾问为主（管理员可建、可看）；
- 班主任、学员：没有这个模块，接口 403。
"""

import re
import sqlite3
import time
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from database import get_db
from models.base import ResponseModel
from services import auth_service, class_service, log_service

router = APIRouter()
public_router = APIRouter()

PHONE_RE = re.compile(r"^1\d{10}$")
SOURCE_TAG = "登录页客服 · 活动报名"
STATUS_OPEN = "开放报名"


def _me(db: sqlite3.Connection, authorization: Optional[str]) -> dict:
    payload = auth_service.read_token(authorization)
    if not payload:
        raise HTTPException(status_code=401, detail="请先登录")
    me = auth_service.profile(db, payload.get("uid"))
    if not me:
        raise HTTPException(status_code=401, detail="登录信息已失效，请重新登录")
    return me


def _require_staff(me: dict) -> None:
    if me["role"] not in ("staff", "admin"):
        raise HTTPException(status_code=403, detail="活动安排只对顾问和管理员开放")


def _clip(value: Optional[str], limit: int) -> str:
    return (value or "").strip().replace("\r", "")[:limit]


def _fmt(ts: Optional[str]) -> str:
    """把 '2026-11-22 19:00:00' 变成 '11-22 19:00'。"""
    t = (ts or "").replace("T", " ")
    return t[5:16] if len(t) >= 16 else t


def _signed(db: sqlite3.Connection, activity_id: int) -> int:
    return db.execute(
        "SELECT COUNT(*) FROM activity_signup WHERE activity_id = ? AND status != '已取消'",
        (activity_id,),
    ).fetchone()[0]


def _pick_consultant(db: sqlite3.Connection) -> Optional[sqlite3.Row]:
    """报名归活动创建者；创建者是管理员时，找手上线索最少的顾问接手。"""
    rows = db.execute(
        "SELECT u.id, u.real_name, "
        "  (SELECT COUNT(*) FROM crm_lead l "
        "     WHERE l.owner_employee_id = u.id AND l.status != '已流失') AS load "
        "FROM sys_user u "
        "WHERE u.user_type = 'EMPLOYEE' "
        "  AND COALESCE(u.employee_role,'') NOT IN ('管理员', '领导') "
        "  AND COALESCE(u.status,'正常') = '正常' "
        "  AND NOT EXISTS (SELECT 1 FROM sys_user s WHERE s.homeroom_teacher_id = u.id) "
        "ORDER BY load ASC, u.id ASC"
    ).fetchall()
    return rows[0] if rows else None


def _owner_of(db: sqlite3.Connection, activity: sqlite3.Row):
    """活动的归属顾问：创建者是顾问就用他，否则按负载分。"""
    if activity["created_by"]:
        row = db.execute(
            "SELECT id, real_name, user_type, employee_role FROM sys_user WHERE id = ?",
            (activity["created_by"],),
        ).fetchone()
        if row and (row["employee_role"] or "") not in ("管理员", "领导"):
            return row
    return _pick_consultant(db)


def _row(db: sqlite3.Connection, a: sqlite3.Row, with_signups: bool = True) -> dict:
    signed = _signed(db, a["id"])
    capacity = int(a["capacity"] or 0)
    remain = max(capacity - signed, 0)
    out = {
        "id": a["id"],
        "title": a["title"],
        "category": a["category"] or "活动",
        "description": a["description"] or "",
        "speaker": a["speaker"] or "待定",
        "start": _fmt(a["start_time"]),
        "start_full": a["start_time"] or "",
        "end": _fmt(a["end_time"]),
        "location": a["location"] or "待定",
        "capacity": capacity,
        "signed": signed,
        "remaining": remain,
        "full": signed >= capacity,
        "status": a["status"] or STATUS_OPEN,
        "created_by_name": db.execute(
            "SELECT real_name FROM sys_user WHERE id = ?", (a["created_by"],)
        ).fetchone()["real_name"] if a["created_by"] else "—",
        "created": _fmt(a["create_time"]),
    }
    if with_signups:
        signups = []
        for s in db.execute(
            "SELECT * FROM activity_signup WHERE activity_id = ? ORDER BY id DESC", (a["id"],)
        ):
            # 报名时会同步写线索，这里把线索状态带出来，顾问不用再切到「客户线索」查
            lead = None
            if s["lead_id"]:
                lead = db.execute(
                    "SELECT id, status FROM crm_lead WHERE id = ?", (s["lead_id"],)
                ).fetchone()
            if not lead:
                lead = db.execute(
                    "SELECT id, status FROM crm_lead WHERE contact_info = ? "
                    "ORDER BY id DESC LIMIT 1",
                    (s["phone"],),
                ).fetchone()
            signups.append(
                {
                    "id": s["id"],
                    "name": s["name"],
                    "phone": s["phone"],
                    "remark": s["remark"] or "",
                    "status": s["status"] or "已报名",
                    "time": (s["create_time"] or "")[5:16],
                    "lead_id": lead["id"] if lead else s["lead_id"],
                    "lead_status": lead["status"] if lead else "",
                }
            )
        out["signups"] = signups
    return out


def _visible(db: sqlite3.Connection, me: dict) -> list[sqlite3.Row]:
    if me["role"] == "admin":
        return db.execute("SELECT * FROM activity ORDER BY start_time ASC, id DESC").fetchall()
    return db.execute(
        "SELECT * FROM activity WHERE created_by = ? ORDER BY start_time ASC, id DESC",
        (me["id"],),
    ).fetchall()


def _brief_dept(department: Optional[str]) -> str:
    """「留学事业部 · 咨询二组（德国方向）」→「德国方向」，下拉里只留方向，括号不套括号。"""
    text = (department or "").strip()
    if "（" in text and "）" in text:
        text = text[text.index("（") + 1 : text.rindex("）")]
    elif "·" in text:
        text = text.split("·")[-1]
    return text.strip()


# ---------------------------------------------------------------------------
# 中台：顾问/管理员的「活动安排」
# ---------------------------------------------------------------------------
@router.get("", response_model=ResponseModel, summary="活动列表（含报名人）")
def list_activities(
    authorization: Optional[str] = Header(None),
    db: sqlite3.Connection = Depends(get_db),
):
    me = _me(db, authorization)
    _require_staff(me)
    rows = [_row(db, a) for a in _visible(db, me)]
    total_signup = sum(r["signed"] for r in rows)
    # 主讲老师下拉：活动项目老师（试听 / 项目介绍）排最前，后面是在职班主任（带方向）
    speakers = [
        {"name": r["real_name"], "dept": _brief_dept(r["department"])}
        for r in db.execute(
            "SELECT real_name, department FROM sys_user u "
            "WHERE u.user_type = 'EMPLOYEE' AND COALESCE(u.status,'正常') = '正常' "
            "  AND (COALESCE(u.employee_role,'') IN ('班主任', '活动项目老师') "
            "       OR EXISTS (SELECT 1 FROM sys_user s WHERE s.homeroom_teacher_id = u.id) "
            "       OR EXISTS (SELECT 1 FROM school_class c WHERE c.teacher_id = u.id)) "
            "ORDER BY CASE WHEN COALESCE(u.employee_role,'') = '活动项目老师' THEN 0 ELSE 1 END,"
            "         u.id"
        ).fetchall()
    ]
    return ResponseModel(
        msg=f"共 {len(rows)} 场活动 · {total_signup} 人报名",
        data={
            "rows": rows,
            "role": me["role"],
            "can_create": True,
            "can_manage": me["role"] in ("staff", "admin"),
            "speakers": speakers,
            "note": "学员报名后会同时进客户线索",
        },
    )


class ActivityIn(BaseModel):
    title: str
    category: Optional[str] = None
    description: Optional[str] = None
    speaker: Optional[str] = None
    start_time: str
    end_time: Optional[str] = None
    location: Optional[str] = None
    capacity: int = 30


@router.post("", response_model=ResponseModel, summary="设计一场活动")
def create_activity(
    body: ActivityIn,
    authorization: Optional[str] = Header(None),
    db: sqlite3.Connection = Depends(get_db),
):
    me = _me(db, authorization)
    _require_staff(me)

    title = _clip(body.title, 40)
    start = _clip(body.start_time, 19).replace("T", " ")
    if not title:
        raise HTTPException(status_code=400, detail="活动名称不能为空")
    if len(start) < 10:
        raise HTTPException(status_code=400, detail="请选择活动时间")
    if len(start) == 16:
        start += ":00"
    if body.capacity < 1 or body.capacity > 500:
        raise HTTPException(status_code=400, detail="名额要在 1~500 之间")

    end = _clip(body.end_time, 19).replace("T", " ")
    if len(end) == 16:
        end += ":00"

    cur = db.execute(
        "INSERT INTO activity (title, category, description, speaker, start_time, end_time, "
        "location, capacity, status, created_by, create_time) "
        "VALUES (?,?,?,?,?,?,?,?,?,?, datetime('now','localtime'))",
        (
            title,
            _clip(body.category, 20) or "线下分享会",
            _clip(body.description, 300),
            _clip(body.speaker, 40) or "待定",
            start,
            end or None,
            _clip(body.location, 60),
            body.capacity,
            STATUS_OPEN,
            me["id"],
        ),
    )
    db.commit()
    log_service.write(
        db,
        actor=me,
        action="activity_create",
        summary=f"新建活动：{title}（{_fmt(start)} · 名额 {body.capacity}）",
        detail=f"主讲 {_clip(body.speaker, 40) or '待定'}｜{_clip(body.location, 60) or '待定'}",
        target_type="activity",
        target_id=cur.lastrowid,
    )
    return ResponseModel(msg="活动已创建", data={"id": cur.lastrowid})


@router.post("/{activity_id}/status", response_model=ResponseModel, summary="结束/恢复报名")
def set_status(
    activity_id: int,
    body: dict,
    authorization: Optional[str] = Header(None),
    db: sqlite3.Connection = Depends(get_db),
):
    me = _me(db, authorization)
    _require_staff(me)
    a = db.execute("SELECT * FROM activity WHERE id = ?", (activity_id,)).fetchone()
    if not a:
        raise HTTPException(status_code=404, detail="活动不存在")
    if me["role"] != "admin" and int(a["created_by"] or 0) != me["id"]:
        raise HTTPException(status_code=403, detail="只能管理自己设计的活动")

    status = "已结束" if (body.get("action") == "close") else STATUS_OPEN
    db.execute("UPDATE activity SET status = ? WHERE id = ?", (status, activity_id))
    db.commit()
    log_service.write(
        db,
        actor=me,
        action="activity_status",
        summary=f"{'结束报名' if status == '已结束' else '恢复报名'}：{a['title']}",
        target_type="activity",
        target_id=activity_id,
    )
    return ResponseModel(msg="已" + ("结束报名" if status == "已结束" else "恢复报名"))


@router.delete("/{activity_id}", response_model=ResponseModel, summary="删除活动（无人报名时）")
def delete_activity(
    activity_id: int,
    authorization: Optional[str] = Header(None),
    db: sqlite3.Connection = Depends(get_db),
):
    me = _me(db, authorization)
    _require_staff(me)
    a = db.execute("SELECT * FROM activity WHERE id = ?", (activity_id,)).fetchone()
    if not a:
        raise HTTPException(status_code=404, detail="活动不存在")
    if me["role"] != "admin" and int(a["created_by"] or 0) != me["id"]:
        raise HTTPException(status_code=403, detail="只能删除自己设计的活动")
    if _signed(db, activity_id):
        raise HTTPException(status_code=400, detail="已经有人报名，不能删除；可以「结束报名」")
    db.execute("DELETE FROM activity WHERE id = ?", (activity_id,))
    db.commit()
    log_service.write(
        db,
        actor=me,
        action="activity_delete",
        summary=f"删除活动：{a['title']}",
        target_type="activity",
        target_id=activity_id,
    )
    return ResponseModel(msg="活动已删除")


# ---------------------------------------------------------------------------
# 登录页公开接口：活动列表 + 报名
# ---------------------------------------------------------------------------
@public_router.get("/activities", response_model=ResponseModel, summary="公开活动（客服推荐用）")
def public_activities(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT * FROM activity WHERE COALESCE(status,'开放报名') = ? "
        "ORDER BY start_time ASC",
        (STATUS_OPEN,),
    ).fetchall()
    out = []
    for a in rows:
        signed = _signed(db, a["id"])
        cap = int(a["capacity"] or 0)
        out.append(
            {
                "id": a["id"],
                "title": a["title"],
                "category": a["category"] or "活动",
                "speaker": a["speaker"] or "待定",
                "start": _fmt(a["start_time"]),
                "location": a["location"] or "待定",
                "capacity": cap,
                "signed": signed,
                "remaining": max(cap - signed, 0),
                "full": signed >= cap,
                "description": a["description"] or "",
            }
        )
    return ResponseModel(msg=f"共 {len(out)} 场活动", data=out)


class SignupIn(BaseModel):
    activity_id: int
    name: Optional[str] = None
    phone: str
    remark: Optional[str] = None


def _other_options(db: sqlite3.Connection, exclude_id: int, limit: int = 3) -> list[dict]:
    rows = db.execute(
        "SELECT * FROM activity WHERE COALESCE(status,'开放报名') = ? AND id != ? "
        "ORDER BY start_time ASC",
        (STATUS_OPEN, exclude_id),
    ).fetchall()
    out = []
    for a in rows:
        signed = _signed(db, a["id"])
        cap = int(a["capacity"] or 0)
        if signed >= cap:
            continue
        out.append({"id": a["id"], "title": a["title"], "start": _fmt(a["start_time"]), "remaining": cap - signed})
        if len(out) >= limit:
            break
    return out


@public_router.post("/activity-signup", response_model=ResponseModel, summary="公开报名（姓名 + 手机号）")
def public_signup(body: SignupIn, db: sqlite3.Connection = Depends(get_db)):
    phone = (body.phone or "").strip()
    # 不做「提取数字」的宽容处理：11 位纯数字才算对，少一位或多一个字母都要重填
    if not PHONE_RE.fullmatch(phone):
        raise HTTPException(status_code=400, detail="电话格式错误，请重新填写")

    name = _clip(body.name, 20)
    if not name:
        raise HTTPException(status_code=400, detail="请补充报名人姓名")

    a = db.execute("SELECT * FROM activity WHERE id = ?", (body.activity_id,)).fetchone()
    if not a:
        raise HTTPException(status_code=404, detail="活动不存在")
    if (a["status"] or STATUS_OPEN) != STATUS_OPEN:
        raise HTTPException(
            status_code=400,
            detail={"msg": "该活动已结束报名", "alternatives": _other_options(db, a["id"])},
        )

    signed = _signed(db, a["id"])
    if signed >= int(a["capacity"] or 0):
        raise HTTPException(
            status_code=409,
            detail={
                "msg": "该活动已满",
                "activity": a["title"],
                "alternatives": _other_options(db, a["id"]),
            },
        )

    dup = db.execute(
        "SELECT id FROM activity_signup WHERE activity_id = ? AND phone = ?", (a["id"], phone)
    ).fetchone()
    if dup:
        return ResponseModel(
            msg="这个号码已经报过名了",
            data={"id": dup["id"], "repeated": True, "activity": a["title"], "alternatives": []},
        )

    owner = _owner_of(db, a)
    stamp = time.strftime("%m-%d %H:%M")
    remark = _clip(body.remark, 200)
    lead_id = None

    if owner:
        old = db.execute(
            "SELECT id, customer_name FROM crm_lead WHERE contact_info = ? AND status != '已流失' "
            "ORDER BY id DESC LIMIT 1",
            (phone,),
        ).fetchone()
        if old:
            add = f"\n[{stamp}] 报名活动：{a['title']}（{_fmt(a['start_time'])}）"
            db.execute(
                "UPDATE crm_lead SET follow_up_history = COALESCE(follow_up_history,'') || ?, "
                "update_time = datetime('now','localtime') WHERE id = ?",
                (add, old["id"]),
            )
            lead_id = old["id"]
        else:
            background = (
                f"来源：{SOURCE_TAG}\n"
                f"活动：{a['title']}（{_fmt(a['start_time'])} · {a['location'] or '待定'}）\n"
                f"意向：{remark or '活动报名'}"
            )
            cur = db.execute(
                "INSERT INTO crm_lead (customer_name, contact_info, background_info, status, "
                "owner_employee_id, create_time, update_time) "
                "VALUES (?,?,?,?,?, datetime('now','localtime'), datetime('now','localtime'))",
                (name, phone, background, "新增意向", owner["id"]),
            )
            lead_id = cur.lastrowid

    cur = db.execute(
        "INSERT INTO activity_signup (activity_id, name, phone, lead_id, remark, status, create_time) "
        "VALUES (?,?,?,?,?, '已报名', datetime('now','localtime'))",
        (a["id"], name, phone, lead_id, remark),
    )
    db.commit()
    # 报名就是一条有联系方式的线索，直接进活动项目老师的试听班
    class_service.attach_lead(db, lead_id)

    log_service.write(
        db,
        action="activity_signup",
        summary=f"活动报名：{name}（{phone}）报名「{a['title']}」",
        detail=f"{_fmt(a['start_time'])}｜{a['speaker'] or '待定'}｜{owner['real_name'] if owner else '未分配'}",
        target_type="activity",
        target_id=a["id"],
    )
    return ResponseModel(
        msg=f"报名成功，{a['title']}",
        data={
            "id": cur.lastrowid,
            "repeated": False,
            "activity": a["title"],
            "start": _fmt(a["start_time"]),
            "location": a["location"] or "待定",
            "consultant": owner["real_name"] if owner else "顾问",
            "alternatives": [],
        },
    )
