import sqlite3
from config import DB_PATH

def execute_nl2sql(query: str) -> list:
    """演示: 简单规则匹配 NL2SQL 查询员工相关数据"""
    if "客户" in query or "线索" in query:
        sql = "SELECT * FROM crm_lead LIMIT 10;"
    elif "成绩" in query:
        sql = "SELECT * FROM student_score LIMIT 10;"
    else:
        return [{"error": "无法解析该自然语言查询"}]
        
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        return [dict(row) for row in cursor.fetchall()]