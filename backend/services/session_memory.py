"""按 conversation_id 记住最近几轮问答，供多轮指代消解使用。

为什么需要它：
员工问「给张三录入 Python 成绩 92 分」，紧接着问「这是哪个学期的成绩？」——
第二句既没有人名也没有课程名，实体全在上一轮里。Dify 的 LLM 节点有 memory 能看懂，
但 HTTP 节点发出去的 body 只有原始问句，后端拿到的是一句光秃秃的「这是哪个学期的成绩」，
于是只好把整张成绩表倒出来（20 条、多个学期），答非所问。

所以把「问 + 答摘要」放在进程内共享，nl2sql 通过 conversation_id 取回上文做补全。
只记内存不落库：这是会话级临时状态，重启丢失不影响业务数据。
"""

from __future__ import annotations

import threading

_MAX_CONV = 200
_TURNS = 4
_ANSWER_CHARS = 150

_LOCK = threading.Lock()
_STORE: dict[str, list[str]] = {}


def remember(conversation_id: str, query: str, answer: str) -> None:
    """记一轮问答：问句截 50 字，答句截 150 字（够放实体，不至于把上下文撑爆）。"""
    if not conversation_id:
        return
    with _LOCK:
        if len(_STORE) > _MAX_CONV:
            _STORE.pop(next(iter(_STORE)))
        turns = _STORE.setdefault(conversation_id, [])
        turns.append(f"问：{(query or '')[:50]}｜答：{(answer or '')[: _ANSWER_CHARS]}")
        del turns[:-_TURNS]


def hint(conversation_id: str, turns: int = _TURNS, max_chars: int = 700) -> str:
    """取最近几轮的上文摘要，拼成一行给模型/解析器看。"""
    with _LOCK:
        items = list(_STORE.get(conversation_id or "") or [])
    return "；".join(items[-turns:])[:max_chars]


def clear(conversation_id: str) -> None:
    with _LOCK:
        _STORE.pop(conversation_id or "", None)
