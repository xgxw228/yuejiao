import sqlite3


def check_and_create_alert(
    db: sqlite3.Connection,
    student_id: int,
    trigger_reason: str,
    risk_level: str = "中",
    journal_id: int | None = None,
) -> int:
    """触发心理预警并写入预警表，返回预警记录 ID。

    顺手把学生当时的班主任记进 teacher_id：预警是发给班主任的活，
    后台「跟进老师」一列不该空着；之后换班也不改这条历史记录。

    journal_id：由心理周记高分触发时传入，老师处理预警后要回写周记，
    否则学生端还停在「待跟进」——预警和周记是同一件事的两个视图。
    """
    row = db.execute(
        "SELECT homeroom_teacher_id FROM sys_user WHERE id = ?", (student_id,)
    ).fetchone()
    teacher_id = row[0] if row else None

    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO student_psych_alert "
        "(student_id, trigger_reason, risk_level, teacher_id, journal_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (student_id, trigger_reason, risk_level, teacher_id, journal_id),
    )
    db.commit()
    return cursor.lastrowid
