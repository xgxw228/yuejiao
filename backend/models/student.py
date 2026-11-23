from pydantic import BaseModel
from typing import Optional

class AdminServiceCreate(BaseModel):
    student_id: int
    service_type: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    reason: Optional[str] = None

class FeedbackCreate(BaseModel):
    student_id: int
    content: str
    detail: Optional[str] = None