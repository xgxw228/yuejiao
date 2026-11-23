"""学生侧「请假 / 行政申请」的通用增删改查（前缀 /api/student）。

这组接口最早是给联调用的，原来四个口子全开：列全表、替任何人提交、
改任何一条的状态、删任何一条。**请假是审批数据，不能这么敞着**。
现在统一按登录身份收口，规则和 /api/leave、/api/grades 保持一致：

- 学员：只能看/提交/删除自己的，且不能改审批状态（那是班主任的事）；
- 班主任：只能看/改/删自己名下学生的；
- 管理员：全量可看，代批可以，删除也留痕；
- 顾问：与请假无关，一律 403。

Dify 的工作流不走这里（走 /api/agent/*），所以收紧不影响对话链路。
"""

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from database import get_db
from models.base import ResponseModel
from services import auth_service, log_service

router = APIRouter()


class StudentServiceCreate(BaseModel):
    student_id: int
    service_type: str
    reason: Optional[str] = None


class StudentServiceUpdate(BaseModel):
    status: Optional[str] = None
    approver_id: Optional[int] = None


def _me(db: sqlite3.Connection, authorization: Optional[str]) -> dict:
    payload = auth_service.read_token(authorization)
    if not payload:
        raise HTTPException(status_code=401, detail="请先登录")
    me = auth_service.profile(db, payload.get("uid"))
    if not me:
        raise HTTPException(status_code=401, detail="登录信息已失效，请重新登录")
    return me


def _scope_ids(db: sqlite3.Connection, me: dict) -> Optional[list[int]]:
    """返回此人可见的学生 id 列表；None 表示全校（管理员）。"""
    if me["role"] == "admin":
        return None
    if me["role"] == "teacher":
        return [
            r["id"]
            for r in db.execute(
                "SELECT id FROM sys_user WHERE homeroom_teacher_id = ?", (me["id"],)
            )
        ]
    if me["role"] == "student":
        return [me["id"]]
    raise HTTPException(status_code=403, detail="当前身份不能查看请假申请")


def _guard_student(db: sqlite3.Connection, me: dict, student_id: int) -> None:
    ids = _scope_ids(db, me)
    if ids is not None and int(student_id) not in [int(i) for i in ids]:
        raise HTTPException(status_code=403, detail="这名学生不在你的权限范围内")


@router.get("/list", response_model=ResponseModel, summary="1.查-请假/行政申请列表（按身份限定范围）")
def get_services(
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    ids = _scope_ids(db, me)
    if ids is None:
        rows = db.execute("SELECT * FROM student_admin_service ORDER BY id DESC").fetchall()
    elif not ids:
        rows = []
    else:
        holes = ",".join("?" * len(ids))
        rows = db.execute(
            f"SELECT * FROM student_admin_service WHERE student_id IN ({holes}) ORDER BY id DESC",
            ids,
        ).fetchall()
    return ResponseModel(msg=f"共 {len(rows)} 条", data=[dict(r) for r in rows])


@router.post("/create", response_model=ResponseModel, summary="2.增-提交申请（学员只能给自己提）")
def create_service(
    data: StudentServiceCreate,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    if me["role"] == "student":
        # 学员传别人的 id 也按本人处理
        student_id = me["id"]
    else:
        _guard_student(db, me, data.student_id)
        student_id = data.student_id

    teacher = db.execute(
        "SELECT homeroom_teacher_id FROM sys_user WHERE id = ?", (student_id,)
    ).fetchone()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO student_admin_service (student_id, service_type, reason, approver_id) "
        "VALUES (?,?,?,?)",
        (student_id, data.service_type, data.reason, (teacher["homeroom_teacher_id"] if teacher else None)),
    )
    db.commit()
    log_service.write(
        db,
        actor=me,
        action="leave_apply",
        summary=f"提交{data.service_type}：{(data.reason or '')[:40]}",
        target_type="leave",
        target_id=cursor.lastrowid,
    )
    return ResponseModel(msg="提交成功，已转给班主任审批")


@router.put("/update/{id}", response_model=ResponseModel, summary="3.改-更新审批状态（学员不可改）")
def update_service(
    id: int,
    data: StudentServiceUpdate,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    if me["role"] == "student":
        raise HTTPException(status_code=403, detail="审批状态由班主任修改，学员不能改")
    if me["role"] not in ("teacher", "admin"):
        raise HTTPException(status_code=403, detail="当前身份不能修改请假申请")

    row = db.execute("SELECT * FROM student_admin_service WHERE id = ?", (id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="申请不存在")
    _guard_student(db, me, row["student_id"])

    approver_id = data.approver_id if me["role"] == "admin" else me["id"]
    db.execute(
        "UPDATE student_admin_service SET status=?, approver_id=? WHERE id=?",
        (data.status, approver_id, id),
    )
    db.commit()
    log_service.write(
        db,
        actor=me,
        action="leave_approve",
        summary=f"更新审批状态：{row['service_type']} #{id} → {data.status or '未变'}",
        target_type="leave",
        target_id=id,
    )
    return ResponseModel(msg="更新成功")


@router.delete("/delete/{id}", response_model=ResponseModel, summary="4.删-删除申请（仅本人 / 本人学生）")
def delete_service(
    id: int,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    row = db.execute("SELECT * FROM student_admin_service WHERE id = ?", (id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="申请不存在")
    if me["role"] == "student" and int(row["student_id"]) != int(me["id"]):
        raise HTTPException(status_code=403, detail="只能删除自己的申请")
    _guard_student(db, me, row["student_id"])

    db.execute("DELETE FROM student_admin_service WHERE id = ?", (id,))
    db.commit()
    log_service.write(
        db,
        actor=me,
        action="leave_delete",
        summary=f"删除请假申请 #{id}",
        target_type="leave",
        target_id=id,
    )
    return ResponseModel(msg="删除成功")
