from fastapi import APIRouter, Depends
import sqlite3
from pydantic import BaseModel
from typing import Optional
from models.base import ResponseModel
from database import get_db
from services import class_service

router = APIRouter()

class CrmCreate(BaseModel):
    customer_name: str
    owner_employee_id: int
    background_info: Optional[str] = None

class CrmUpdate(BaseModel):
    status: Optional[str] = None
    follow_up_history: Optional[str] = None

@router.get("/list", response_model=ResponseModel, summary="1.查-意向客户列表")
def get_crm(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM crm_lead")
    return ResponseModel(data=[dict(row) for row in cursor.fetchall()])

@router.post("/create", response_model=ResponseModel, summary="2.增-录入意向客户")
def create_crm(data: CrmCreate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("INSERT INTO crm_lead (customer_name, owner_employee_id, background_info) VALUES (?,?,?)", 
                   (data.customer_name, data.owner_employee_id, data.background_info))
    db.commit()
    # 有手机号的线索自动进活动项目老师的试听班（没留电话的不进）
    class_service.attach_lead(db, cursor.lastrowid)
    return ResponseModel(msg="录入成功")

@router.put("/update/{id}", response_model=ResponseModel, summary="3.改-更新客户状态")
def update_crm(id: int, data: CrmUpdate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("UPDATE crm_lead SET status=?, follow_up_history=? WHERE id=?", (data.status, data.follow_up_history, id))
    db.commit()
    # 状态改成已签约 / 已流失时，试听班名单跟着变
    class_service.attach_lead(db, id)
    return ResponseModel(msg="更新成功")

@router.delete("/delete/{id}", response_model=ResponseModel, summary="4.删-删除客户")
def delete_crm(id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM crm_lead WHERE id = ?", (id,))
    db.commit()
    return ResponseModel(msg="删除成功")