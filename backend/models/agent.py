from pydantic import BaseModel
from typing import Optional

class ChatLogCreate(BaseModel):
    user_id: int
    agent_type: str
    user_input: str
    ai_output: str
    emotion_tag: Optional[str] = None  # 供心理画像累积使用