from fastapi import APIRouter, Depends
import sqlite3
from models.base import ResponseModel
from models.agent import ChatLogCreate
from database import get_db
from services.profile_engine import update_psych_profile
from services.alert_engine import check_and_create_alert

router = APIRouter()

@router.post("/log-conversation", response_model=ResponseModel)
def log_conversation(data: ChatLogCreate, db: sqlite3.Connection = Depends(get_db)):
    """供 Dify 调用的对话记录接口，联动更新画像与预警"""
    cursor = db.cursor()
    
    # 1. 写入对话日志
    cursor.execute(
        """INSERT INTO conversation_log 
           (user_id, agent_type, user_input, ai_output, emotion_tag) 
           VALUES (?, ?, ?, ?, ?)""",
        (data.user_id, data.agent_type, data.user_input, data.ai_output, data.emotion_tag)
    )
    db.commit()

    # 2. 如果是学生对话，且带情绪标签，联动心理画像引擎
    if data.agent_type == "STUDENT" and data.emotion_tag:
        # 模拟根据情绪标签推导分值 (实际项目中由 Dify 的 LLM 直接输出 0-100 分值)
        score_map = {"焦虑": 30, "抑郁": 20, "平稳": 80, "开心": 95}
        score = score_map.get(data.emotion_tag, 60)
        
        update_psych_profile(db, data.user_id, data.emotion_tag, score)
        
        # 3. 触发高危预警 (阈值判断)
        if score < 40:
            check_and_create_alert(
                db, 
                student_id=data.user_id, 
                trigger_reason=f"对话情绪分析: {data.emotion_tag}，原话: {data.user_input}", 
                risk_level="高"
            )

    return ResponseModel(msg="对话已记录并触发数据流转")