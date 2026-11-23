from fastapi import APIRouter, Depends
import sqlite3
from pydantic import BaseModel
from typing import Optional
from models.base import ResponseModel
from database import get_db

router = APIRouter()

class EventCreate(BaseModel):
    event_name: str
    start_time: str
    max_participants: int

class EventUpdate(BaseModel):
    location: Optional[str] = None
    max_participants: Optional[int] = None

@router.get("/list", response_model=ResponseModel, summary="1.查-活动列表")
def get_events(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM event_lecture")
    return ResponseModel(data=[dict(row) for row in cursor.fetchall()])

@router.post("/create", response_model=ResponseModel, summary="2.增-发布新活动")
def create_event(data: EventCreate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("INSERT INTO event_lecture (event_name, start_time, max_participants) VALUES (?,?,?)", 
                   (data.event_name, data.start_time, data.max_participants))
    db.commit()
    return ResponseModel(msg="发布成功")

@router.put("/update/{id}", response_model=ResponseModel, summary="3.改-更新活动信息")
def update_event(id: int, data: EventUpdate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("UPDATE event_lecture SET location=?, max_participants=? WHERE id=?", (data.location, data.max_participants, id))
    db.commit()
    return ResponseModel(msg="更新成功")

@router.delete("/delete/{id}", response_model=ResponseModel, summary="4.删-删除活动")
def delete_event(id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM event_lecture WHERE id = ?", (id,))
    db.commit()
    return ResponseModel(msg="删除成功")