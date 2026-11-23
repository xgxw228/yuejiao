import sqlite3
from config import DB_PATH, SQL_PATH

# schema.sql 用的是 CREATE TABLE IF NOT EXISTS，老库不会自动加列，
# 这里做一次轻量迁移：缺哪列补哪列，不重建表、不动数据。
MIGRATIONS = {
    "sys_user": [
        ("homeroom_teacher_id", "INTEGER"),
        ("parent_of_student_id", "INTEGER"),
        ("created_by", "INTEGER"),
        ("class_id", "INTEGER"),
    ],
    "student_admin_service": [
        ("approve_time", "DATETIME"),
        ("approve_comment", "TEXT"),
    ],
    "school_class": [
        # 常规班 = 正式学员的班；试听班 = 活动项目老师带的有联系方式的意向学员
        ("kind", "TEXT DEFAULT '常规班'"),
    ],
    "crm_lead": [
        # 线索挂靠的班（目前只有活动试听班用），用来把「有联系方式的意向学员」拉进班里
        ("class_id", "INTEGER"),
    ],
    "student_psych_alert": [
        # 班主任处理预警时留下的沟通记录：谁处理的、什么时候、做了什么
        ("handler_id", "INTEGER"),
        ("handle_note", "TEXT"),
        ("handle_time", "DATETIME"),
        # 来源周记：周记高分触发的预警，处理时要回写周记状态，学生端才看得到
        ("journal_id", "INTEGER"),
    ],
    "student_feedback_ticket": [
        # 反馈分类：学生提交时选，老师按类型分派 / 统计
        ("category", "TEXT DEFAULT '其他'"),
        # 处理人（本班班主任）与处理时间：学生端只看得到回复内容，看不到内部处理链
        ("handler_id", "INTEGER"),
        ("handle_time", "DATETIME"),
    ],
}


def get_db():
    # check_same_thread=False：FastAPI 的同步依赖和同步接口不一定跑在同一个线程池线程里，
    # 并发请求时会在"初始化连接的线程"和"执行接口的线程"之间切换，
    # 默认检查会抛 ProgrammingError。这里每个请求独占一个连接，不会跨请求共享，关掉检查是安全的。
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # 允许通过字典方式访问
    try:
        yield conn
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    for table, columns in MIGRATIONS.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, decl in columns:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
                print(f" 数据迁移：{table} 新增列 {name}")
    # class_id 是后加的列，索引必须等 ALTER 之后再建
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sys_user_class ON sys_user(class_id)")
    # 反馈分类是后加的列，老工单没有分类，统一归「其他」，页面上不出现空白标签
    conn.execute(
        "UPDATE student_feedback_ticket SET category = '其他' "
        "WHERE category IS NULL OR TRIM(category) = ''"
    )


def init_db():
    with open(SQL_PATH, 'r', encoding='utf-8') as f:
        sql_script = f.read()
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(sql_script)
        _migrate(conn)
        conn.commit()
    print(" 数据库初始化完成，共 12 张表。")
