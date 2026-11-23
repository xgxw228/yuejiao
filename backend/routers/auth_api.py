"""登录相关接口（前缀 /api/auth）。

/login  账号密码换 token
/me     用 token 换当前用户 + 角色 + 可见 Agent
/roles  登录页的演示角色卡（账号密码一键填充）
/logout 无状态 token，前端清掉即可，这里只做个语义化的返回
"""

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel

from database import get_db
from models.base import ResponseModel
from services import auth_service

router = APIRouter()


class LoginBody(BaseModel):
    username: str
    password: str


def _token(request: Request, token: Optional[str], authorization: Optional[str]) -> Optional[str]:
    return token or authorization or request.headers.get("authorization")


@router.get("/roles", response_model=ResponseModel, summary="演示账号（登录页一键填充，按身份分组）")
def list_roles(db: sqlite3.Connection = Depends(get_db)):
    try:
        rows = auth_service.demo_accounts(db)
    except sqlite3.Error:
        rows = auth_service.DEMO_ROLES
    return ResponseModel(
        msg=f"共 {len(rows)} 个演示账号，密码统一为 {auth_service.DEMO_PASSWORD}",
        data=rows or auth_service.DEMO_ROLES,
    )


@router.post("/login", response_model=ResponseModel, summary="账号登录")
def do_login(body: LoginBody, db: sqlite3.Connection = Depends(get_db)):
    out = auth_service.login(db, body.username, body.password)
    user = out["user"]
    # 登录本身不记账：日志只保留业务动作（审批 / 录入 / 跟进 / 留资 / 咨询）。
    return ResponseModel(msg=f"欢迎回来，{user['real_name']}（{user['role_label']}）", data=out)


@router.get("/me", response_model=ResponseModel, summary="当前登录用户")
def me(
    request: Request,
    token: Optional[str] = Query(None, description="也支持 ?token= 传参"),
    authorization: Optional[str] = Header(None),
    db: sqlite3.Connection = Depends(get_db),
):
    user = auth_service.current_user(db, _token(request, token, authorization))
    if not user:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return ResponseModel(data=user)


@router.post("/logout", response_model=ResponseModel, summary="退出登录")
def logout():
    return ResponseModel(msg="已退出登录")
