import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import init_db
from config import BASE_DIR
from routers import (
    user_api,
    student_api,
    employee_api,
    customer_api,
    agent_hook_api,
    agent_tool_api,
    demo_chat_api,
    leave_api,
    auth_api,
    system_api,
    public_api,
    workspace_api,
    grades_api,
    accounts_api,
    activity_api,
)

app = FastAPI(
    title="粤教服务 API",
    description="对接 Dify 的多智能体业务后端",
    version="2.0.0",
    servers=[{"url": "http://127.0.0.1:8000", "description": "本地开发环境"}] 
)


# 跨域配置 (供 index.html 调用)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 所有 HTML 页面禁缓存：前端迭代频繁，浏览器按 Last-Modified 做启发式缓存时
# 会出现「代码已改、页面还是旧的」——统一由这里兜底，省掉手动强刷。
@app.middleware("http")
async def no_store_html(request, call_next):
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.on_event("startup")
def startup():
    init_db()
    # 班级表为空时按现有班主任初始化（粤教1班 / 2班 / 3班…），老数据不用手工搬
    import sqlite3

    from config import DB_PATH
    from services import class_service

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        class_service.ensure_classes(conn)
    finally:
        conn.close()

# 挂载路由
app.include_router(user_api.router, prefix="/api/user", tags=["系统-用户"])
app.include_router(student_api.router, prefix="/api/student", tags=["学生侧-留学生管家"])
app.include_router(employee_api.router, prefix="/api/employee", tags=["员工侧-业务助手"])
app.include_router(customer_api.router, prefix="/api/customer", tags=["客服侧-活动助手"])
app.include_router(agent_hook_api.router, prefix="/api/agent", tags=["Dify调用的工具接口"])
app.include_router(agent_tool_api.router, prefix="/api/agent", tags=["Agent业务工具"])
app.include_router(leave_api.router, prefix="/api/leave", tags=["请假审批面板"])
app.include_router(demo_chat_api.router, prefix="/api/chat", tags=["演示前端-对话代理"])
app.include_router(auth_api.router, prefix="/api/auth", tags=["登录与权限"])
app.include_router(system_api.router, prefix="/api", tags=["系统-健康检查与后台"])
app.include_router(public_api.router, prefix="/api/public", tags=["公开-在线客服留资"])
app.include_router(workspace_api.router, prefix="/api", tags=["我的工作台-按身份取数"])
app.include_router(grades_api.router, prefix="/api/grades", tags=["成绩-按师生关系隔离"])
app.include_router(accounts_api.router, prefix="/api/accounts", tags=["账户管理-开户与停用"])
app.include_router(activity_api.router, prefix="/api/activities", tags=["活动安排-设计活动与报名"])
app.include_router(activity_api.public_router, prefix="/api/public", tags=["公开-活动推荐与报名"])

# 演示前端（与后端同源，免跨域、不暴露 Dify API Key）
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/demo", StaticFiles(directory=FRONTEND_DIR, html=True), name="demo")

    # /login 返回的是单个 HTML 文件，它里面的相对路径 assets/... 会解析成 /assets/...，
    # 所以这里要单独挂一次；/demo/login.html 走 /demo 挂载时同样能命中。
    ASSETS_DIR = os.path.join(FRONTEND_DIR, "assets")
    if os.path.isdir(ASSETS_DIR):
        app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

    LOGIN_PAGE = os.path.join(FRONTEND_DIR, "login.html")
    PORTAL_PAGE = os.path.join(FRONTEND_DIR, "portal.html")

    # 视频门户首页：/ 与 /portal 都进门户，登录弹窗里挂的是 /api/auth/*
    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(PORTAL_PAGE)

    @app.get("/portal", include_in_schema=False)
    def portal_page():
        return FileResponse(PORTAL_PAGE)

    @app.get("/login", include_in_schema=False)
    def login_page():
        return FileResponse(LOGIN_PAGE)

    @app.get("/admin", include_in_schema=False)
    def admin_page():
        # 后台页迭代频繁，禁缓存，避免浏览器/预览面板命中旧快照导致「刷新还是旧界面」
        return FileResponse(
            os.path.join(FRONTEND_DIR, "admin.html"),
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache"},
        )