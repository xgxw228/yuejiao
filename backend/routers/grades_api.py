"""成绩：录入与查看，按「师生关系」严格隔离（前缀 /api/grades）。

规则只有一条：**成绩跟学生走，学生跟班主任走**。
- 班主任：只能看/录/改/删自己名下学生的成绩，别班的一条也拿不到；
- 学员：只能看自己的，接口不接受 student_id 参数；
- 管理员：能看全校，但只读（要改由班主任改，避免"管理员顺手改分"）；
- 顾问：与成绩无关，直接 403。

前端把 student_id 传成别人也没用，后端会用 token 里的 uid 重新算一遍范围，
和请假审批用的是同一套归属判断（sys_user.homeroom_teacher_id）。
"""

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from database import get_db
from models.base import ResponseModel
from services import auth_service, log_service

router = APIRouter()

LANGUAGE = ("雅思", "托福")


def _me(db: sqlite3.Connection, authorization: Optional[str]) -> dict:
    payload = auth_service.read_token(authorization)
    if not payload:
        raise HTTPException(status_code=401, detail="请先登录")
    me = auth_service.profile(db, payload.get("uid"))
    if not me:
        raise HTTPException(status_code=401, detail="登录信息已失效，请重新登录")
    return me


def _level(course: Optional[str], score: Optional[float]) -> str:
    if score is None:
        return "暂无"
    if any(k in (course or "") for k in LANGUAGE):
        return "语言成绩"
    if score >= 85:
        return "优秀"
    if score >= 75:
        return "良好"
    if score >= 60:
        return "及格"
    return "待提升"


def _short(ts: Optional[str]) -> str:
    return (ts or "")[:10]


def _students(db: sqlite3.Connection, where: str, args: tuple) -> list[dict]:
    return [
        dict(r)
        for r in db.execute(
            "SELECT u.id, u.real_name, u.username, u.contact_info, u.department, "
            "  (SELECT real_name FROM sys_user t WHERE t.id = u.homeroom_teacher_id) AS teacher_name, "
            "  (SELECT name FROM school_class c WHERE c.id = u.class_id) AS class_name "
            f"FROM sys_user u WHERE {where} ORDER BY u.id",
            args,
        )
    ]


def _board(db: sqlite3.Connection, students: list[dict]) -> list[dict]:
    rows = []
    for s in students:
        scores = [
            {
                "id": r["id"],
                "course": r["course_name"],
                "score": r["score"],
                "semester": r["semester"] or "—",
                "level": _level(r["course_name"], r["score"]),
                "created": _short(r["create_time"]),
            }
            for r in db.execute(
                "SELECT * FROM student_score WHERE student_id = ? ORDER BY id DESC", (s["id"],)
            )
        ]
        pct = [x["score"] for x in scores if not any(k in (x["course"] or "") for k in LANGUAGE)]
        avg = round(sum(pct) / len(pct), 1) if pct else None
        rows.append(
            {
                "id": s["id"],
                "name": s["real_name"],
                "dept": s["department"] or "—",
                "class_name": s.get("class_name") or "",
                "teacher": s.get("teacher_name") or "—",
                "avg": avg,
                "level": _level("", avg),
                "count": len(scores),
                "failed": sum(1 for v in pct if v < 60),
                "scores": scores,
            }
        )
    return rows


@router.get("", response_model=ResponseModel, summary="成绩册（按身份限定范围）")
def grade_board(
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    role = me["role"]

    if role == "student":
        students = _students(db, "u.id = ? AND u.user_type = 'STUDENT'", (me["id"],))
        can_edit, scope, note = False, "self", "只能看到自己的成绩"
    elif role == "teacher":
        students = _students(
            db, "u.homeroom_teacher_id = ? AND u.user_type = 'STUDENT'", (me["id"],)
        )
        can_edit, scope = True, "own"
        note = f"只看 {me['real_name']} 名下 {len(students)} 名学生，别班学生不在范围内"
    elif role == "admin":
        students = _students(db, "u.user_type = 'STUDENT'", ())
        can_edit, scope, note = False, "all", "管理员可看全校成绩，只读；修改请由班主任操作"
    else:
        raise HTTPException(status_code=403, detail="顾问不涉及学员成绩，无权查看")

    rows = _board(db, students)
    vals = [s["score"] for r in rows for s in r["scores"]]
    pct = [
        s["score"]
        for r in rows
        for s in r["scores"]
        if not any(k in (s["course"] or "") for k in LANGUAGE)
    ]
    return ResponseModel(
        msg=f"{len(rows)} 名学生 · {len(vals)} 条成绩",
        data={
            "rows": rows,
            "can_edit": can_edit,
            "scope": scope,
            "note": note,
            "role": role,
            "summary": {
                "students": len(rows),
                "records": len(vals),
                "avg": round(sum(pct) / len(pct), 1) if pct else None,
                "failed": sum(1 for v in pct if v < 60),
                "missing": sum(1 for r in rows if r["count"] == 0),
            },
        },
    )


class ScoreIn(BaseModel):
    student_id: int
    course_name: str
    score: float
    semester: Optional[str] = None


def _owned_student(db: sqlite3.Connection, me: dict, student_id: int) -> dict:
    """校验这个学生是不是当前老师名下的，不是就 403。"""
    row = db.execute(
        "SELECT id, real_name, homeroom_teacher_id FROM sys_user "
        "WHERE id = ? AND user_type = 'STUDENT'",
        (student_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="学生不存在")
    if int(row["homeroom_teacher_id"] or 0) != int(me["id"]):
        teacher = db.execute(
            "SELECT real_name FROM sys_user WHERE id = ?", (row["homeroom_teacher_id"],)
        ).fetchone() if row["homeroom_teacher_id"] else None
        who = teacher["real_name"] if teacher else "其他班主任"
        raise HTTPException(
            status_code=403,
            detail=f"{row['real_name']} 是{who}名下的学生，你只能录入自己学生的成绩",
        )
    return {"id": row["id"], "name": row["real_name"]}


def _require_teacher(me: dict) -> None:
    if me["role"] == "admin":
        raise HTTPException(status_code=403, detail="管理员只读成绩；需要修改请让班主任操作")
    if me["role"] != "teacher":
        raise HTTPException(status_code=403, detail="只有班主任可以录入成绩")


@router.post("", response_model=ResponseModel, summary="录入成绩（仅本人名下学生）")
def create_score(
    body: ScoreIn,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    _require_teacher(me)
    student = _owned_student(db, me, body.student_id)

    course = (body.course_name or "").strip()
    if not course:
        raise HTTPException(status_code=400, detail="请填写课程名称")
    if not (0 <= body.score <= 150):
        raise HTTPException(status_code=400, detail="分数需在 0~150 之间")
    semester = (body.semester or "").strip() or "2025-2026 第一学期"

    old = db.execute(
        "SELECT id, score FROM student_score WHERE student_id = ? AND course_name = ? "
        "AND COALESCE(semester,'') = ?",
        (student["id"], course, semester),
    ).fetchone()
    if old:
        db.execute(
            "UPDATE student_score SET score = ?, create_time = datetime('now','localtime') WHERE id = ?",
            (body.score, old["id"]),
        )
        word, detail = "已更新", f"{old['score']} → {body.score}"
    else:
        db.execute(
            "INSERT INTO student_score (student_id, course_name, score, semester, create_time) "
            "VALUES (?, ?, ?, ?, datetime('now','localtime'))",
            (student["id"], course, body.score, semester),
        )
        word, detail = "已录入", f"{body.score} 分"

    db.commit()
    log_service.write(
        db,
        actor=me,
        action="score_save",
        summary=f"{word}成绩：{student['name']} · {course} {detail}",
        detail=f"学期：{semester}（范围：{me['real_name']} 名下学生）",
        target_type="score",
        target_id=student["id"],
    )
    return ResponseModel(msg=f"{word}：{student['name']} · {course} {body.score} 分")


class ScorePatch(BaseModel):
    score: float


@router.put("/{score_id}", response_model=ResponseModel, summary="修改成绩（仅本人名下学生）")
def update_score(
    score_id: int,
    body: ScorePatch,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    _require_teacher(me)
    row = db.execute("SELECT * FROM student_score WHERE id = ?", (score_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="成绩记录不存在")
    student = _owned_student(db, me, row["student_id"])
    if not (0 <= body.score <= 150):
        raise HTTPException(status_code=400, detail="分数需在 0~150 之间")

    db.execute("UPDATE student_score SET score = ? WHERE id = ?", (body.score, score_id))
    db.commit()
    log_service.write(
        db,
        actor=me,
        action="score_save",
        summary=f"修改成绩：{student['name']} · {row['course_name']}（{row['score']} → {body.score}）",
        target_type="score",
        target_id=student["id"],
    )
    return ResponseModel(msg=f"已修改：{student['name']} · {row['course_name']} {body.score} 分")


@router.delete("/{score_id}", response_model=ResponseModel, summary="删除成绩（仅本人名下学生）")
def delete_score(
    score_id: int,
    db: sqlite3.Connection = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    me = _me(db, authorization)
    _require_teacher(me)
    row = db.execute("SELECT * FROM student_score WHERE id = ?", (score_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="成绩记录不存在")
    student = _owned_student(db, me, row["student_id"])

    db.execute("DELETE FROM student_score WHERE id = ?", (score_id,))
    db.commit()
    log_service.write(
        db,
        actor=me,
        action="score_delete",
        summary=f"删除成绩：{student['name']} · {row['course_name']}（{row['score']} 分）",
        target_type="score",
        target_id=student["id"],
    )
    return ResponseModel(msg=f"已删除：{student['name']} · {row['course_name']}")
