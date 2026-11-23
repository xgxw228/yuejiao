"""演示前端 -> Dify 服务 API 的代理层

为什么不让浏览器直连 Dify：
1. Dify 的 nginx 默认不给 /v1 加 CORS 头，浏览器会被拦；
2. API Key 一旦写进前端 JS 就等于公开；
3. 后端代理可以顺便把 SSE 事件裁剪成前端好用的格式。
"""

import json
import re
import sqlite3
from typing import AsyncGenerator, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from database import get_db, DB_PATH
from dify_agents import AGENTS, DIFY_API_BASE, DIFY_TIMEOUT
from services import auth_service, emotion_engine, log_service, session_memory

router = APIRouter()

# 多轮上下文：按 conversation_id 记住最近几轮的「问 + 答摘要」。
# 为什么不只记问句：客户第一轮问的是"19岁高中毕业想快点拿本科学历"，
# 第二轮只问"学费多少"，项目名其实出现在**上一轮的回答**里（0.5/1+2 本硕连读），
# 所以要连回答一起记，指代才能落到具体项目上。
# 存储挪到 services/session_memory.py：NL2SQL 也要读同一份上文做指代补全。
_history_hint = session_memory.hint
_remember = session_memory.remember


class ChatRequest(BaseModel):
    agent: str
    query: str
    user_id: int = 1
    conversation_id: str = ""
    user: Optional[str] = None
    token: Optional[str] = None
    public: bool = False  # 登录页在线客服：匿名、只答公开信息


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ---- 公开访客护栏 ------------------------------------------------------
# 客服 Agent 挂了 CRM / 成绩工具，匿名访客问一句「张三成绩」就能拿到真实学员数据。
# 所以登录页来的匿名问答在后端先过一道：命中个人数据意图直接回引导，不转给 Dify。
_PUBLIC_BLOCK = re.compile(
    r"(我的|我家|我孩子|孩子的|学生的|学员的|家长的)[^。？！?!]{0,8}"
    r"(成绩|分数|请假|审批|进度|状态|记录|缴费|合同|电话|手机号|身份证)"
    r"|(查|查询|看一下|看看|调出|列出|查查)[^。？！?!]{0,10}"
    r"(成绩|请假|缴费|名单|客户|线索|电话|手机号)"
    r"|(同学|学员|学生|客户)[^。？！?!]{0,6}(成绩|分数|请假|记录|电话|手机号)"
)
_PUBLIC_TIP = (
    "涉及在读学员的个人信息（成绩、请假、缴费、进度这类），需要登录后才能查看；"
    "点右上角「进入系统」登录就行。项目、费用、申请条件、开班时间这些是公开的，我现在就能答。"
)

# 注册/开户类问题：账号由顾问在签约后统一创建，不把知识库里的「报名缴费账号」甩给还没签约的访客
_REGISTER_INTENT = re.compile(
    r"(注册|开户|开通|创建|申请)[^。？！?!]{0,8}(账户|账号|帐号)"
    r"|(账户|账号|帐号)[^。？！?!]{0,8}(怎么|如何|怎样|注册|开户|开通|个人|办)"
    r"|个人[^。？！?!]{0,4}(账户|账号|帐号)"
    r"|(我想|我要|怎么|如何|怎样|能不能|可以)[^。？！?!]{0,4}(注册|开户)"
)
_REGISTER_TIP = (
    "我们这边的系统账号是由顾问在签约确认后统一创建的，个人暂时不用自己注册，也不需要提前缴费。"
    "你留个姓名和手机号，我让顾问联系你、确认好项目后帮你把账号开好；"
    "急的话可以直接打 020-37628058 找顾问老师。"
)
# 这些是称谓不是姓名，不参与"提到学员姓名"的拦截
_NOT_A_NAME = {"李老师", "王主任", "孙老师", "赵老师", "郑主任", "陈顾问", "同学们"}


def _public_blocked(db: sqlite3.Connection, query: str) -> bool:
    if _PUBLIC_BLOCK.search(query):
        return True
    try:
        rows = db.execute("SELECT real_name FROM sys_user").fetchall()
    except sqlite3.Error:
        return False
    for row in rows:
        name = (row["real_name"] or "").strip()
        if 2 <= len(name) <= 3 and name not in _NOT_A_NAME and name in query:
            return True
    return False


def _canned(text: str) -> StreamingResponse:
    """不调模型，直接回一段固定话术（仍然是 SSE，前端解析逻辑不用改）。"""
    async def gen():
        yield _sse("delta", {"text": text})
        yield _sse("done", {"conversation_id": "", "message_id": None, "usage": {}})
    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---- 请假进度这类问题，直接查库回答，不交给模型 --------------------------
# 模型答"批没批"只能靠猜；这里用固定规则把学生/老师最常问的两句接住，
# 答案里带具体日期和状态，同时把这次查询记进日志。
_LEAVE_WORD = re.compile(r"(请假|假期|休假)")
_QUERY_WORD = re.compile(r"(请完|批了|批没|批好|批准|通过|状态|进度|记录|结果|几天|多久|查|看|还有|待批|待处理|哪些|谁|几个|多少)")


def _fmt_day(ts: Optional[str]) -> str:
    return (ts or "")[5:10]


def _status_answer(db: sqlite3.Connection, me: dict, query: str) -> Optional[str]:
    if not (_LEAVE_WORD.search(query) and _QUERY_WORD.search(query)):
        return None
    role = me["role"]

    if role == "student":
        rows = db.execute(
            "SELECT v.*, u.real_name AS teacher FROM student_admin_service v "
            "LEFT JOIN sys_user u ON u.id = v.approver_id "
            "WHERE v.student_id = ? ORDER BY v.start_time DESC LIMIT 5",
            (me["id"],),
        ).fetchall()
        if not rows:
            return "你这边还没有请假记录。要请假的话直接告诉我日期和事由，我帮你提交。"
        pending = [r for r in rows if r["status"] == "待审批"]
        lines = [f"你最近 {len(rows)} 条请假记录："]
        for r in rows:
            tail = ""
            if r["status"] == "待审批" and r["teacher"]:
                tail = f"，等 {r['teacher']} 审批"
            elif r["status"] != "待审批" and r["approve_comment"]:
                tail = f"，意见：{r['approve_comment']}"
            lines.append(
                f"· {_fmt_day(r['start_time'])} → {_fmt_day(r['end_time'])}（{r['reason'][:18]}）：{r['status']}{tail}"
            )
        if pending:
            lines.append(f"还有 {len(pending)} 条在审批中，批完这里会同步更新。")
        else:
            lines.append("目前没有待审批的请假，最近几条都已经处理完了。")
        lines.append("左侧「请假记录」也能看到同样的状态。")
        return "\n".join(lines)

    if role == "admin":
        rows = db.execute(
            "SELECT v.*, u.real_name FROM student_admin_service v "
            "JOIN sys_user u ON u.id = v.student_id "
            "WHERE v.status = '待审批' ORDER BY v.start_time"
        ).fetchall()
        if not rows:
            return "现在没有待审批的请假。请假由各班主任审批，你可以在数据后台查看全量记录。"
        lines = [f"全校还有 {len(rows)} 条请假待批："]
        for r in rows[:6]:
            lines.append(f"· {r['real_name']}：{_fmt_day(r['start_time'])} → {_fmt_day(r['end_time'])}，{r['reason'][:18]}")
        lines.append("这些由学生所在班主任审批，你这边只查看不代批；数据后台「请假审批」可看全量。")
        return "\n".join(lines)

    if role == "teacher":
        rows = db.execute(
            "SELECT v.*, u.real_name FROM student_admin_service v "
            "JOIN sys_user u ON u.id = v.student_id "
            "WHERE v.status = '待审批' AND u.homeroom_teacher_id = ? "
            "ORDER BY v.start_time",
            (me["id"],),
        ).fetchall()
        if not rows:
            return "现在没有待审批的请假，学生新提交的会自动出现在左侧「待处理请假」里。"
        lines = [f"还有 {len(rows)} 条请假待批："]
        for r in rows[:6]:
            lines.append(f"· {r['real_name']}：{_fmt_day(r['start_time'])} → {_fmt_day(r['end_time'])}，{r['reason'][:18]}")
        lines.append("左侧「待处理请假」可以直接通过或驳回，处理完会记进你的日志。")
        return "\n".join(lines)

    if role == "staff":
        rows = db.execute(
            "SELECT * FROM crm_lead WHERE owner_employee_id = ? AND status != '已流失' "
            "ORDER BY update_time DESC LIMIT 6",
            (me["id"],),
        ).fetchall()
        if not rows:
            return "你名下暂时没有在跟的线索。客户在登录页留了联系方式，会自动分到你这里。"
        fresh = sum(1 for r in rows if r["status"] == "新增意向")
        lines = [f"你名下 {len(rows)} 条线索，其中 {fresh} 条新增意向："]
        for r in rows:
            lines.append(f"· {r['customer_name'] or '未留名'}（{r['contact_info'] or '—'}）：{r['status']}")
        lines.append("左侧「待跟进线索」点一条就能写跟进、改状态。")
        return "\n".join(lines)
    return None


def _log_conversation(uid: int, agent: str, query: str, answer: str) -> None:
    """FR-029 对话记录沉淀：每轮问答落一条，学生侧顺便打情绪标签。

    用独立连接写入：流式响应结束时请求依赖可能已回收，不能复用请求级连接。
    """
    if not query or not answer:
        return
    tag = None
    if agent == "student":
        try:
            tag = emotion_engine.evaluate_by_keyword(query)[0]
        except Exception:
            tag = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
        try:
            conn.execute(
                "INSERT INTO conversation_log (user_id, agent_type, user_input, ai_output, emotion_tag)"
                " VALUES (?, ?, ?, ?, ?)",
                (uid, agent.upper(), query[:1000], answer[:4000], tag),
            )
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        pass  # 记日志失败不能影响对话本身


@router.get("/agents", summary="演示端可用的 Agent 列表")
def list_agents():
    out = []
    for key, cfg in AGENTS.items():
        out.append(
            {
                "key": key,
                "name": cfg["name"],
                "icon": cfg["icon"],
                "tagline": cfg["tagline"],
                "accent": cfg["accent"],
                "welcome": cfg["welcome"],
                "prompts": cfg["prompts"],
                "users": cfg["users"],
            }
        )
    return {"data": out}


@router.post("/stream", summary="流式对话（代理 Dify chat-messages）")
async def stream(req: ChatRequest, db: sqlite3.Connection = Depends(get_db)):
    cfg = AGENTS.get(req.agent)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"未知 Agent：{req.agent}")
    if not (req.query or "").strip():
        raise HTTPException(status_code=400, detail="query 不能为空")

    # 带 token 时以登录身份为准：学生无法通过改 user_id 冒充别人；管理员可模拟任意身份
    uid = req.user_id
    me = auth_service.current_user(db, req.token) if req.token else None
    if me:
        if req.agent not in me["agents"]:
            raise HTTPException(
                status_code=403,
                detail=f"当前身份（{me['role_label']}）没有「{cfg['name']}」的使用权限",
            )
        if not me["features"].get("admin"):
            uid = me["id"]

    # 登录页在线客服：匿名 + 只答公开信息（命中个人数据直接挡住）
    public = bool(req.public) and not me
    if public and _REGISTER_INTENT.search(req.query or ""):
        return _canned(_REGISTER_TIP)
    if public and _public_blocked(db, req.query):
        return _canned(_PUBLIC_TIP)

    # 登录用户问「请假批没批」「还有哪些待批」：固定规则查库，避免模型编状态
    if me and not public:
        status_text = _status_answer(db, me, req.query)
        if status_text:
            log_service.write(
                db,
                actor=me,
                action="leave_query" if me["role"] in ("student", "teacher", "admin") else "chat",
                summary=f"查询进度：{req.query.strip()[:40]}",
                detail=(status_text.splitlines()[0] + "｜" + status_text.splitlines()[-1])[:200],
                target_type="leave" if me["role"] in ("student", "teacher", "admin") else "lead",
            )
            return _canned(status_text)

    if public:
        # 公开访客不绑定任何真实档案：uid=0 让业务工具查不到数据，
        # 名字给「访客」，避免客服把它当成某位家长而报出学员信息。
        user = {"id": 0, "name": "访客"}
    else:
        user = next((u for u in cfg["users"] if u["id"] == uid), None)
        if not user:
            row = db.execute("SELECT real_name FROM sys_user WHERE id = ?", (uid,)).fetchone()
            if not row:
                raise HTTPException(status_code=400, detail=f"未知用户 ID：{uid}")
            user = {"id": uid, "name": row["real_name"]}

    payload = {
        "inputs": {
            "user_id": int(user["id"]),
            cfg["name_var"]: user["name"],
            "history_hint": _history_hint(req.conversation_id),
        },
        "query": req.query.strip(),
        "response_mode": "streaming",
        "conversation_id": req.conversation_id or "",
        "user": req.user or f"demo-{req.agent}-{user['id']}",
        "auto_generate_name": False,
    }
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    async def gen() -> AsyncGenerator[str, None]:
        timeout = httpx.Timeout(DIFY_TIMEOUT, connect=10.0)
        answer_parts: list[str] = []
        conv_id = req.conversation_id or ""
        finished = False
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", f"{DIFY_API_BASE}/chat-messages", json=payload, headers=headers
                ) as resp:
                    if resp.status_code >= 400:
                        body = (await resp.aread()).decode("utf-8", "ignore")
                        yield _sse("error", {"message": f"Dify {resp.status_code}: {body[:300]}"})
                        return

                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if not raw or raw == "[DONE]":
                            continue
                        try:
                            evt = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        name = evt.get("event")
                        if name in ("message", "agent_message"):
                            text = evt.get("answer") or ""
                            if text:
                                answer_parts.append(text)
                                yield _sse("delta", {"text": text})
                        elif name == "message_end":
                            conv_id = evt.get("conversation_id") or conv_id
                            final_text = "".join(answer_parts)
                            _remember(conv_id, req.query.strip(), final_text)
                            if not public:
                                _log_conversation(uid, req.agent, req.query.strip(), final_text)
                                actor = auth_service.profile(db, uid)
                                log_service.write(
                                    db,
                                    actor=actor,
                                    action="chat",
                                    summary=f"问小粤同学：{req.query.strip()[:40]}",
                                    detail=final_text.split("查询语句")[0][:200],
                                    target_type="conversation",
                                    target_id=None,
                                )
                            meta = evt.get("metadata") or {}
                            finished = True
                            yield _sse(
                                "done",
                                {
                                    "conversation_id": conv_id,
                                    "message_id": evt.get("message_id"),
                                    "usage": meta.get("usage") or {},
                                },
                            )
                        elif name == "node_started":
                            data = evt.get("data") or {}
                            title = data.get("title") or ""
                            # 只透出业务节点，开始/结束/回复节点不展示
                            if title and data.get("node_type") in (
                                "http-request",
                                "knowledge-retrieval",
                                "code",
                                "llm",
                            ):
                                yield _sse("node", {"title": title})
                        elif name == "error":
                            yield _sse("error", {"message": evt.get("message") or "Dify 执行出错"})
                            return
        except (httpx.ConnectError, httpx.ConnectTimeout):
            # Dify 整个不可达（容器停止/重启），给用户能听懂的话 + 兜底联系方式
            yield _sse("error", {
                "message": "智能助手暂时连不上（服务可能在重启），请稍等一分钟再试；"
                           "急着咨询的话可以直接致电 020-37628058。",
                "degraded": True,
            })
            return
        except httpx.TimeoutException:
            yield _sse("error", {
                "message": "这次回答等太久没出来，麻烦再问一次；如果一直这样，请致电 020-37628058 找顾问老师。",
                "degraded": True,
            })
            return
        except httpx.HTTPError as e:
            yield _sse("error", {
                "message": f"智能助手这边出了点问题（{type(e).__name__}），请稍后再试。",
                "degraded": True,
            })
            return

        # 模型/工作流返回了空内容时，明确报错，避免前端出现空气泡
        if finished and not answer_parts:
            yield _sse("error", {"message": "模型这次没有返回内容，请重试或换个说法再问一次。"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
