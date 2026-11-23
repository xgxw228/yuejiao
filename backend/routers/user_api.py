from fastapi import APIRouter, Depends
import sqlite3
from pydantic import BaseModel
from typing import Optional
from models.base import ResponseModel
from database import get_db

router = APIRouter()

class UserCreate(BaseModel):
    username: str
    password_hash: str
    real_name: str
    user_type: str
    contact_info: Optional[str] = None

class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    status: Optional[str] = None

@router.get("/list", response_model=ResponseModel, summary="1.查-获取用户列表")
def get_users(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT id, username, real_name, user_type, status FROM sys_user")
    return ResponseModel(data=[dict(row) for row in cursor.fetchall()])

@router.post("/create", response_model=ResponseModel, summary="2.增-新增用户")
def create_user(data: UserCreate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("INSERT INTO sys_user (username, password_hash, real_name, user_type, contact_info) VALUES (?,?,?,?,?)", 
                   (data.username, data.password_hash, data.real_name, data.user_type, data.contact_info))
    db.commit()
    return ResponseModel(msg="新增成功")

@router.put("/update/{id}", response_model=ResponseModel, summary="3.改-更新用户")
def update_user(id: int, data: UserUpdate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("UPDATE sys_user SET real_name=?, status=? WHERE id=?", (data.real_name, data.status, id))
    db.commit()
    return ResponseModel(msg="更新成功")

@router.delete("/delete/{id}", response_model=ResponseModel, summary="4.删-删除用户")
def delete_user(id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM sys_user WHERE id = ?", (id,))
    db.commit()
    return ResponseModel(msg="删除成功")