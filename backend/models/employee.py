from pydantic import BaseModel
from typing import Optional

class CrmLeadCreate(BaseModel):
    customer_name: str
    contact_info: str
    background_info: Optional[str] = None
    owner_employee_id: int

class DailyReportCreate(BaseModel):
    employee_id: int
    report_date: str
    content: str