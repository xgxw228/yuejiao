import sqlite3
import json
from datetime import datetime

def update_psych_profile(db: sqlite3.Connection, student_id: int, emotion_tag: str, score: int):
    """更新心理画像（维护 emotion_history JSON 及最新情绪）"""
    cursor = db.cursor()
    cursor.execute("SELECT emotion_history FROM student_psych_profile WHERE student_id = ?", (student_id,))
    row = cursor.fetchone()
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_record = {"time": now_str, "tag": emotion_tag, "score": score}
    
    if row:
        # 追加历史记录（需求要求仅保留最近 50 条）
        history = json.loads(row["emotion_history"]) if row["emotion_history"] else []
        history.append(new_record)
        history = history[-50:]
        
        cursor.execute(
            """UPDATE student_psych_profile 
               SET latest_emotion_tag=?, emotion_score=?, last_interaction_time=?, emotion_history=?, update_time=? 
               WHERE student_id=?""",
            (emotion_tag, score, now_str, json.dumps(history, ensure_ascii=False), now_str, student_id)
        )
    else:
        # 初始化画像
        history = [new_record]
        cursor.execute(
            """INSERT INTO student_psych_profile 
               (student_id, latest_emotion_tag, emotion_score, last_interaction_time, emotion_history) 
               VALUES (?, ?, ?, ?, ?)""",
            (student_id, emotion_tag, score, now_str, json.dumps(history, ensure_ascii=False))
        )
    db.commit()