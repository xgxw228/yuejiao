"""在本地 Dify 实例中重建三个 Agent 的 Chatflow。

拓扑统一为：
    开始 → 拼接上下文(template, 把上一轮问答拼进查询) → 意图分类 → 各分支
                                                               ├─ HTTP 工具(调 FastAPI) → LLM 润色 → 回复
                                                               └─ 知识检索 → LLM → 回复

需要「先把口语拆成结构化参数」的分支，多插一个 LLM 抽取节点，
由它输出严格 JSON 直接作为 HTTP 请求体，避免模板拼接破坏 JSON 转义。

多轮上下文：`history_hint` 由后端代理按会话写入（上一轮问 + 上一轮答摘要），
经 template 节点拼成「[上文] … [当前问题] …」后再交给分类器与知识检索，
这样「学费多少」「那我们怎么报名」这类指代才能落到正确的国家/项目上。
"""

import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dify_api

HOST = "http://host.docker.internal:8000"
# 内部服务令牌：写操作接口会校验，防止"不登录也能改数据"
INTERNAL_TOKEN = os.environ.get("YJ_INTERNAL_TOKEN", "yj-internal-demo-2026")
INTERNAL_HEADERS = f"Content-Type:application/json\nX-Internal-Token:{INTERNAL_TOKEN}"

# 走 qwen3.8-flash：该模型当前有 100 万 tokens 免费额度（qwen-plus 的额度已用完/过期）
# enable_thinking=False 必须显式传，否则默认开思考链，会多花 reasoning tokens 且拖慢首字
MODEL_NAME = os.environ.get("YJ_MODEL", "qwen3.8-flash")
MODEL = {
    "provider": "langgenius/tongyi/tongyi",
    "name": MODEL_NAME,
    "mode": "chat",
    "completion_params": {"temperature": 0.3, "max_tokens": 2000, "enable_thinking": False},
}
MODEL_STRICT = {
    "provider": "langgenius/tongyi/tongyi",
    "name": MODEL_NAME,
    "mode": "chat",
    "completion_params": {"temperature": 0.0, "max_tokens": 800, "enable_thinking": False},
}

DS_HANDBOOK = "debc6ed5-1524-47ac-9431-45ecd8c25341"  # 员工制度手册（high_quality 语义索引）
DS_PROJECT = "ef37795b-f4f8-47da-933f-739942b47692"   # 留学项目资料库（high_quality 语义索引）

FEATURES = {
    "opening_statement": "",
    "suggested_questions": [],
    "suggested_questions_after_answer": {"enabled": False},
    "text_to_speech": {"enabled": False, "voice": "", "language": ""},
    "speech_to_text": {"enabled": False},
    "retriever_resource": {"enabled": True},
    "sensitive_word_avoidance": {"enabled": False},
    "file_upload": {
        "image": {"enabled": False, "number_limits": 3, "transfer_methods": ["local_file", "remote_url"]},
        "enabled": False,
        "allowed_file_types": ["image"],
        "allowed_file_extensions": [".JPG", ".JPEG", ".PNG", ".GIF", ".WEBP", ".SVG"],
        "allowed_file_upload_methods": ["local_file", "remote_url"],
        "number_limits": 3,
        "fileUploadConfig": {
            "file_size_limit": 15,
            "batch_count_limit": 5,
            "image_file_size_limit": 10,
            "video_file_size_limit": 100,
            "audio_file_size_limit": 50,
            "workflow_file_upload_limit": 10,
        },
    },
}

# 会话记忆：只给"要接着上文聊"的回答节点开，抽取节点一律不开（会污染 JSON 输出）
MEMORY = {
    "role_prefix": {"user": "用户", "assistant": "助手"},
    "window": {"enabled": True, "size": 4},
    "query_prompt_template": None,
}

PREPARE_TEMPLATE = (
    "{% if history_hint %}"
    "[上文] {{ history_hint }}\n"
    "[当前问题] {{ query }}"
    "{% else %}"
    "{{ query }}"
    "{% endif %}"
)


# ---------------------------------------------------------------------------
# 节点构造
# ---------------------------------------------------------------------------

def _wrap(node_id, data, x, y):
    return {
        "id": node_id,
        "type": "custom",
        "data": data,
        "position": {"x": x, "y": y},
        "positionAbsolute": {"x": x, "y": y},
        "targetPosition": "left",
        "sourcePosition": "right",
        "width": 242,
        "height": 100,
        "selected": False,
    }


def start_node(node_id, x, y, defaults):
    """defaults: [{"key","type","value"}]，调用方不传时用默认值填充。"""
    variables = []
    for item in defaults:
        variables.append({
            "variable": item["key"],
            "label": item["label"],
            "description": "",
            "type": item["type"],
            "required": False,
            "hide": False,
            "max_length": 48 if item["type"] == "text-input" else None,
            "options": [],
        })
    data = {
        "variables": variables,
        "type": "start",
        "title": "用户输入",
        "desc": "",
        "selected": False,
        "default_value": [
            {
                "key": d["key"],
                "type": "number" if d["type"] == "number" else "string",
                "value": d["value"],
            }
            for d in defaults
        ],
    }
    return _wrap(node_id, data, x, y)


def prepare_node(node_id, x, y):
    """把「上一轮问答摘要 + 当前问题」拼成一段，供分类器与知识检索使用。"""
    data = {
        "type": "template-transform",
        "title": "拼接上下文",
        "desc": "",
        "variables": [
            {"variable": "history_hint", "value_selector": ["start", "history_hint"]},
            {"variable": "query", "value_selector": ["sys", "query"]},
        ],
        "template": PREPARE_TEMPLATE,
        "selected": False,
    }
    return _wrap(node_id, data, x, y)


def classifier_node(node_id, x, y, classes, query_from="prepare"):
    data = {
        "type": "question-classifier",
        "title": "意图分类",
        "desc": "",
        "query_variable_selector": [query_from, "output" if query_from == "prepare" else "query"],
        "model": MODEL_STRICT,
        "classes": [{"id": c["id"], "name": c["name"]} for c in classes],
        "instruction": "",
        "instructions": "",
        "vision": {"enabled": False},
        "selected": False,
    }
    return _wrap(node_id, data, x, y)


def http_node(node_id, x, y, title, method, url, body_json=None, fail_hint=None):
    data = {
        "type": "http-request",
        "title": title,
        "desc": "",
        "method": method,
        "url": url,
        "authorization": {"type": "no-auth", "config": None},
        "headers": INTERNAL_HEADERS,
        "params": "",
        "body": {"type": "json", "data": [{"key": "", "type": "text", "value": body_json}]} if body_json else {"type": "none", "data": []},
        "timeout": {"connect": 10, "read": 30, "write": 10},
        "retry_config": {"retry_enabled": True, "max_retries": 2, "retry_interval": 500},
        "ssl_verify": True,
        "variables": [],
        "selected": False,
    }
    if fail_hint:
        data["error_strategy"] = "default-value"
        data["default_value"] = [
            {"key": "body", "type": "string", "value": json.dumps({"code": -1, "msg": fail_hint}, ensure_ascii=False)},
            {"key": "status_code", "type": "number", "value": 400},
        ]
    return _wrap(node_id, data, x, y)


def llm_node(node_id, x, y, title, system, user, context_selector=None, memory=False):
    data = {
        "type": "llm",
        "title": title,
        "desc": "",
        "model": MODEL,
        "prompt_template": [
            {"role": "system", "text": system, "id": str(uuid.uuid4())},
            {"role": "user", "text": user, "id": str(uuid.uuid4())},
        ],
        "context": {"enabled": bool(context_selector), "variable_selector": context_selector or []},
        "vision": {"enabled": False},
        "memory": MEMORY if memory else None,
        "reasoning_format": "separated",
        "selected": False,
    }
    return _wrap(node_id, data, x, y)


def extract_node(node_id, x, y, title, system, user, memory=False):
    """参数抽取节点：只输出 JSON，直接作为下一个 HTTP 节点的请求体。"""
    return llm_node(node_id, x, y, title, system, user, memory=memory)


def kb_node(node_id, x, y, dataset_ids, top_k=8, query_from="sys", threshold=0.35):
    data = {
        "type": "knowledge-retrieval",
        "title": "知识检索",
        "desc": "",
        "query_variable_selector": [query_from, "output" if query_from == "prepare" else "query"],
        "dataset_ids": dataset_ids,
        "retrieval_mode": "multiple",
        "multiple_retrieval_config": {
            "top_k": top_k,
            "score_threshold": threshold,
            "score_threshold_enabled": threshold is not None,
            "reranking_mode": "reranking_model",
            "reranking_enable": False,
            "reranking_model": {
                "provider": "langgenius/tongyi/tongyi",
                "model": "qwen3-vl-rerank",
            },
        },
        "selected": False,
    }
    return _wrap(node_id, data, x, y)


def answer_node(node_id, x, y, var_selector, title="回复"):
    data = {
        "type": "answer",
        "title": title,
        "desc": "",
        "answer": "{{#" + ".".join(var_selector) + "#}}",
        "variables": [],
        "selected": False,
    }
    return _wrap(node_id, data, x, y)


def edge(src, tgt, source_type, target_type, handle="source"):
    return {
        "id": f"{src}-{handle}-{tgt}-target",
        "type": "custom",
        "source": src,
        "sourceHandle": handle,
        "target": tgt,
        "targetHandle": "target",
        "data": {
            "sourceType": source_type,
            "targetType": target_type,
            "isInIteration": False,
            "isInLoop": False,
        },
        "zIndex": 0,
    }


# ---------------------------------------------------------------------------
# 通用提示词片段
# ---------------------------------------------------------------------------

COMMON_RULES = """
【铁律】
1. 业务数据只能来自「工具返回」里的 data 字段，不许自己编造姓名、时间、分数、单号、名额。
2. 工具返回 code 不为 0，或出现 detail / msg 里带"未找到""不存在""已满""非法""没有权限"等字眼时，如实转述原因，并给出一个下一步建议；不要把失败说成成功。
3. 用中文口语回答，不要输出 JSON、不要暴露接口路径、不要提"工具""节点""API"这些词。
4. 回答控制在 4 句话以内，需要罗列信息时用简短列表。
5. 学生端输入若以上文形式给出（[上文] … [当前问题] …），只回答"当前问题"，绝不要复述[上文]里的内容。
""".strip()


# ---------------------------------------------------------------------------
# 一、留学生智能管家
# ---------------------------------------------------------------------------

def build_student():
    nodes, edges = [], []
    start_id, prep_id, cls_id = "start", "prepare", "classifier"

    nodes.append(start_node(start_id, 40, 420, [
        {"key": "user_id", "label": "学生ID", "type": "number", "value": 1},
        {"key": "student_name", "label": "学生姓名", "type": "text-input", "value": "张三"},
        {"key": "history_hint", "label": "上文摘要", "type": "paragraph", "value": ""},
    ]))
    nodes.append(prepare_node(prep_id, 280, 420))
    edges.append(edge(start_id, prep_id, "start", "template-transform"))
    edges.append(edge(prep_id, cls_id, "template-transform", "question-classifier"))

    classes = [
        {"id": "c_leave_apply", "name": "请假申请：明确说了请假时间（哪天、几号、明天）和事由，要提交一张请假单，例如「我明天要请假一天，家里有事」「12月20号到22号要请假」"},
        {"id": "c_leave_query", "name": "请假查询与催办：查自己交过的请假单、问审批到哪一步、催老师批、或者要求「帮我审批通过」（学生没有审批权，这类也归到这里），例如「我的请假批了吗」"},
        {"id": "c_emotion", "name": "情绪倾诉：表达压力大、焦虑、失眠、难过、孤独，或说出「活不下去」「不想活」这类极端情绪"},
        {"id": "c_feedback", "name": "售后反馈：投诉、对课程或住宿服务不满意、要求退费或换项目，例如「宿舍热水器坏了没人修」"},
        {"id": "c_score", "name": "成绩查询：查考试成绩、某门课考了多少分，例如「我雅思听力多少分」"},
        {"id": "c_policy", "name": "升学政策咨询（已指明国家或项目）：问某个国家或某个项目的政策、费用、院校、申请材料、签证，问题里出现了新加坡、德国、马来西亚、中国港澳、英美澳、双元制、本硕连读等具体国家或项目名，例如「德国留学一年多少钱」"},
        {"id": "c_policy_geo", "name": "泛问留学但没指明国家：问留学费用、申请条件、哪个国家好、怎么选等，但问题里完全没有出现任何国家、地区或项目名，例如「留学费用大概多少钱」"},
        {"id": "c_other", "name": "其他与敏感请求：要 API Key、密码、数据库连接串、内部系统权限这类不该给的东西；或者与留学生服务完全无关的问题（天气、写代码、闲聊）；或者系统明显办不到的事"},
    ]
    nodes.append(classifier_node(cls_id, 520, 200, classes))

    persona = "你是「粤教服务」的留学生智能管家，负责在读留学生的请假、情绪关怀、售后反馈、成绩查询和升学咨询。"

    def branch(cid, target_id, tgt_type="http-request"):
        edges.append(edge(cls_id, target_id, "question-classifier", tgt_type, handle=cid))

    # --- 请假申请
    y = 40
    nodes.append(http_node(
        "leave_apply_http", 860, y, "提交请假",
        "post", f"{HOST}/api/agent/leave-apply",
        '{"student_id":"{{#start.user_id#}}","reason":"{{#sys.query#}}","service_type":"请假"}',
        fail_hint="请假没有提交成功：可能是没说清时间或事由，请让对方补充哪天请假、请多久、什么原因。",
    ))
    nodes.append(llm_node(
        "leave_apply_llm", 1180, y, "请假回执",
        persona + "\n学生刚提交了请假申请，你要把申请结果清楚地告诉他。\n" + COMMON_RULES + """
6. 必须说出审批人是谁：取 data.teacher.name（或 record.approver_name）的班主任姓名，
   说成"等你班主任李老师审批"这种自然说法，不许只说"等待审批"。
7. 如果返回里 detail 说"没有审批权限"或"没有识别到请假时间"，就照实说明，并告诉他下一步怎么做。
""",
        "学生说：{{#sys.query#}}\n\n工具返回：{{#leave_apply_http.body#}}\n\n"
        "请告诉他：申请单号、请假起止时间、天数、当前状态，以及由哪位班主任审批。",
    ))
    nodes.append(answer_node("leave_apply_ans", 1500, y, ["leave_apply_llm", "text"], "请假回复"))
    branch("c_leave_apply", "leave_apply_http")
    edges.append(edge("leave_apply_http", "leave_apply_llm", "http-request", "llm"))
    edges.append(edge("leave_apply_llm", "leave_apply_ans", "llm", "answer"))

    # --- 请假查询
    y += 220
    nodes.append(http_node(
        "leave_query_http", 860, y, "查询请假记录",
        "get", f"{HOST}/api/agent/leave-list?student_id={{{{#start.user_id#}}}}",
    ))
    nodes.append(llm_node(
        "leave_query_llm", 1180, y, "请假记录播报",
        persona + "\n学生要查自己的请假记录。\n" + COMMON_RULES + """
6. 每条记录都必须说清审批人是谁：优先照抄 status_text，例如「已通过（李老师审批）」「待李老师审批」，
   不许只写"已通过"却不说是哪位班主任批的。数据在 records[].status_text / records[].approver_name。
7. approve_comment 有内容时，把审批意见顺带转述一句。
8. 只要学生的话是在要求审批、催批、让你「直接通过」「帮我批」，第一句就必须先说明：
   学生身份没有审批权限，请假只能由班主任在系统里处理；然后再把最新状态和班主任姓名告诉他。
   不管这些单子当前是什么状态，都不许省略这句说明，更不许说「已帮你审批通过」。
""",
        "学生说：{{#sys.query#}}\n\n工具返回：{{#leave_query_http.body#}}\n\n"
        "请按时间从新到旧列出他的请假记录（起止时间、事由、状态、审批人），没有记录就直说没有。",
    ))
    nodes.append(answer_node("leave_query_ans", 1500, y, ["leave_query_llm", "text"], "请假查询回复"))
    branch("c_leave_query", "leave_query_http")
    edges.append(edge("leave_query_http", "leave_query_llm", "http-request", "llm"))
    edges.append(edge("leave_query_llm", "leave_query_ans", "llm", "answer"))

    # --- 情绪倾诉
    y += 220
    nodes.append(http_node(
        "emotion_http", 860, y, "情绪评估与预警",
        "post", f"{HOST}/api/agent/emotion-evaluate",
        '{"student_id":"{{#start.user_id#}}","text":"{{#sys.query#}}"}',
    ))
    nodes.append(llm_node(
        "emotion_llm", 1180, y, "心理关怀话术",
        persona + """
学生正在向你倾诉情绪，你要先共情、再给支持，绝对不能说教。
""" + COMMON_RULES + """
6. 如果返回里 alerted 为 true，必须明确告诉他「已经通知班主任关注你」，并且给出一个可以马上做的小建议。
7. 不许做医学诊断，不许承诺保密，不许说"我完全理解你的感受"这类空话。
""",
        "学生说：{{#sys.query#}}\n\n工具返回：{{#emotion_http.body#}}\n\n"
        "请用温和、具体的语气回应他，先接住情绪，再说明系统已经做了什么。",
    ))
    nodes.append(answer_node("emotion_ans", 1500, y, ["emotion_llm", "text"], "关怀回复"))
    branch("c_emotion", "emotion_http")
    edges.append(edge("emotion_http", "emotion_llm", "http-request", "llm"))
    edges.append(edge("emotion_llm", "emotion_ans", "llm", "answer"))

    # --- 售后反馈
    y += 220
    nodes.append(http_node(
        "feedback_http", 860, y, "创建反馈工单",
        "post", f"{HOST}/api/agent/feedback-create",
        '{"student_id":"{{#start.user_id#}}","content":"{{#sys.query#}}"}',
        fail_hint="这条反馈没有生成工单：可能不是真实的服务反馈，请如实说明原因。",
    ))
    nodes.append(llm_node(
        "feedback_llm", 1180, y, "工单回执",
        persona + "\n学生提交了售后反馈，你要给他工单回执。\n" + COMMON_RULES,
        "学生说：{{#sys.query#}}\n\n工具返回：{{#feedback_http.body#}}\n\n"
        "请告诉他工单编号、当前处理状态，以及大概多久会有老师联系他；如果没建成，就说清为什么。",
    ))
    nodes.append(answer_node("feedback_ans", 1500, y, ["feedback_llm", "text"], "反馈回复"))
    branch("c_feedback", "feedback_http")
    edges.append(edge("feedback_http", "feedback_llm", "http-request", "llm"))
    edges.append(edge("feedback_llm", "feedback_ans", "llm", "answer"))

    # --- 成绩查询（支持按课程过滤）
    y += 220
    nodes.append(http_node(
        "score_http", 860, y, "查询成绩",
        "get", f"{HOST}/api/agent/score-list?student_id={{{{#start.user_id#}}}}&course={{{{#sys.query#}}}}",
    ))
    nodes.append(llm_node(
        "score_llm", 1180, y, "成绩播报",
        persona + "\n学生要查成绩。\n" + COMMON_RULES + """
6. 如果问的是某一门课（例如雅思听力），只答那一门；返回 data 为空就直说「系统里还没有这门课的成绩」，
   一句话说完即可，不许拿别的课程顶替，不许编分数，也不许列出"课程名：无/分数：无"这种空壳字段。
""",
        "学生说：{{#sys.query#}}\n\n工具返回：{{#score_http.body#}}\n\n"
        "请用列表列出课程名、分数、学期，并顺带说一句平均分；只问一门课就直接报那一门。",
    ))
    nodes.append(answer_node("score_ans", 1500, y, ["score_llm", "text"], "成绩回复"))
    branch("c_score", "score_http")
    edges.append(edge("score_http", "score_llm", "http-request", "llm"))
    edges.append(edge("score_llm", "score_ans", "llm", "answer"))

    # --- 泛问留学（未指明国家）→ 先反问国家
    y += 220
    nodes.append(llm_node(
        "geo_ask_llm", 1180, y, "反问国家",
        "你是「粤教服务」的留学顾问。学生问了一个留学相关问题，但没有说明想去哪个国家或地区。\n"
        "你的任务：先用一句话确认他想了解哪个国家/地区，再列出你们主要做的方向让他选。\n"
        "可选方向：新加坡、德国、马来西亚、中国港澳、英国/澳洲、中外合作办学（2+2、本硕连读）。\n"
        "如果[上文]里已经提到过某个国家或项目，就直接按那个国家回答，不要再反问。\n"
        "不要直接报某一国的费用或条件，不要编造数字。整段控制在 4 句话以内。",
        "学生对你说：{{#sys.query#}}\n\n上文：{{#start.history_hint#}}\n\n请反问他具体想了解哪个国家或地区。",
    ))
    nodes.append(answer_node("geo_ask_ans", 1500, y, ["geo_ask_llm", "text"], "反问回复"))
    branch("c_policy_geo", "geo_ask_llm", tgt_type="llm")
    edges.append(edge("geo_ask_llm", "geo_ask_ans", "llm", "answer"))

    # --- 知识库分支
    y += 220
    nodes.append(kb_node("kb_retrieval", 860, y, [DS_PROJECT], top_k=10, threshold=0.3))
    nodes.append(llm_node(
        "kb_llm", 1180, y, "知识库问答",
        "你是「粤教服务」的留学政策顾问，回答学生关于政策、费用、院校、申请材料、签证的问题。\n"
        "【判断国家】只有当问题（含[上文]）里完全没出现国家、地区或项目名（新加坡、德国、马来西亚、中国港澳、英美澳、双元制、本硕连读等）时，才先反问「你想了解哪个国家/地区」；只要出现了，就直接回答那一国，绝对不要反问。\n"
        "【承接上文】如果[上文]里提到过某个项目（例如「0.5/1+2 本硕连读」），而当前问题只是「学费多少」「怎么报名」「要什么条件」，就理解为在问那个项目，按那个项目回答。\n"
        "【报名类问题】问到「怎么报名 / 报名流程 / 要准备什么材料」时，必须按资料给出完整五步：提交报名材料 → 材料核查通过 → 参加入学笔试及面试 → 入学条件审核通过后缴纳第一年费用 → 发放入学通知/Offer；可以补充笔试(40%)+面试(60%)的构成。不能只回一句「找顾问老师」。\n"
        "只依据下面检索到的资料回答；涉及费用、分数、年限、时间节点时照抄资料原文，不要自己换算或编造。\n"
        "资料没覆盖的，直接说「这个我不确定，建议你联系顾问老师确认」。\n"
        "打工时长、签证条款、移民条件这类法规细节，资料里没明确写就不要自己补数字，改为「具体以官方最新政策为准，建议顾问老师帮你确认」。\n"
        "学生说清了国家和问题时，第一句先直接回答，再用分条补充细节，整体控制在 6 句话以内。",
        "学生问：{{#sys.query#}}\n\n上文：{{#start.history_hint#}}\n\n参考资料：{{#context#}}",
        context_selector=["kb_retrieval", "result"],
        memory=True,
    ))
    nodes.append(answer_node("kb_ans", 1500, y, ["kb_llm", "text"], "咨询回复"))
    branch("c_policy", "kb_retrieval", tgt_type="knowledge-retrieval")
    edges.append(edge("kb_retrieval", "kb_llm", "knowledge-retrieval", "llm"))
    edges.append(edge("kb_llm", "kb_ans", "llm", "answer"))

    # --- 其他 / 敏感请求：不调任何工具，只解释能力边界
    y += 220
    nodes.append(llm_node(
        "other_llm", 1180, y, "能力边界说明",
        persona + """
学生提了一个你不能办的请求。你要做的是：说清边界 + 给出正确的办理方式，不要道歉过度、不要编造。
- 要密钥、密码、数据库连接串、后台权限：明确拒绝，说明这些信息不对学生开放，也不会通过对话给出。
- 与技术实现、代码、其他同学数据相关：说明你只负责本人的留学事务。
- 与留学完全无关（天气、闲聊）：一句话说清你的职责范围，并把话题拉回留学服务。
- 办不到的事：说清需要找谁（班主任 / 顾问老师 / 行政）。
""" + COMMON_RULES,
        "学生说：{{#sys.query#}}\n\n",
    ))
    nodes.append(answer_node("other_ans", 1500, y, ["other_llm", "text"], "说明回复"))
    branch("c_other", "other_llm", tgt_type="llm")
    edges.append(edge("other_llm", "other_ans", "llm", "answer"))

    return {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 0.6}}


# ---------------------------------------------------------------------------
# 二、企业员工智能业务助手
# ---------------------------------------------------------------------------

def build_employee():
    nodes, edges = [], []
    start_id, prep_id, cls_id = "start", "prepare", "classifier"

    nodes.append(start_node(start_id, 40, 420, [
        {"key": "user_id", "label": "员工ID", "type": "number", "value": 3},
        {"key": "employee_name", "label": "员工姓名", "type": "text-input", "value": "李老师"},
        {"key": "history_hint", "label": "上文摘要", "type": "paragraph", "value": ""},
    ]))
    nodes.append(prepare_node(prep_id, 280, 420))
    edges.append(edge(start_id, prep_id, "start", "template-transform"))
    edges.append(edge(prep_id, cls_id, "template-transform", "question-classifier"))

    classes = [
        {"id": "c_query", "name": "业务查询与催办：查客户档案与跟进记录、学生成绩、请假审批进度、员工日报、投诉工单、心理预警、活动名额；也包括「把张三的请假批了」「这条投诉标记为已解决」这类要改数据的话（系统不直接执行，会说明该去哪办），例如「许同学跟进到哪一步了」「张三雅思听力多少分」「昨天日报写了什么」「有哪些待处理的投诉」"},
        {"id": "c_lead_create", "name": "客户录入：录入新的意向客户、新建销售线索，话里带姓名和背景信息，例如「新录入一个客户，叫陈晨，19岁，家长电话13800138000」"},
        {"id": "c_lead_status", "name": "客户状态流转：只处理客户档案的状态字段，话里必须出现「改成/改为/设为」+ 已签约/跟进中/新增意向/已流失之一，例如「把许明的状态改成已签约」。请假审批、投诉处理、成绩修改都不属于这一类"},
        {"id": "c_daily_report", "name": "写日报：让你把他的工作整理成日报或周报并保存，例如「帮我写今天的日报：跟进了5个客户，签约1个」。注意：只是查昨天日报写了什么属于业务查询"},
        {"id": "c_score_entry", "name": "成绩录入：给某个学生录入某门课的成绩，话里必须同时有学生姓名、课程名和具体分数，例如「给张三录入Python课程成绩92分」"},
        {"id": "c_alert_handle", "name": "预警处理：要给某个学生的心理预警改状态（认领、跟进、解除），话里出现学生姓名 + 状态变化，例如「把许明的预警标记为跟进中」「张三的预警解除掉」。注意：只是查有哪些预警属于业务查询"},
        {"id": "c_handbook", "name": "公司制度与新人指引：组织架构、报销流程、入职材料、办公设施、IT 支持、公司介绍、常见问题"},
        {"id": "c_other", "name": "其他：与业务无关的问题（天气、写代码、闲聊），或要密钥、密码、数据库连接串这类不该给的东西，或系统明显办不到的请求"},
    ]
    nodes.append(classifier_node(cls_id, 520, 200, classes))

    persona = "你是「粤教服务」的企业内部业务助手，服务对象是留学顾问和班主任，负责 CRM、日报、成绩和制度查询。"

    def to_branch(cid, node_id, tgt_type="http-request"):
        edges.append(edge(cls_id, node_id, "question-classifier", tgt_type, handle=cid))

    # --- 业务查询（NL2SQL：客户/成绩/请假/日报/投诉/预警/活动）
    y = 40
    nodes.append(http_node(
        "query_http", 860, y, "业务数据查询",
        "post", f"{HOST}/api/agent/nl2sql",
        # 带上 conversation_id：后端据此取本会话上文，把「这是哪个学期的成绩」
        # 这类指代追问还原成「张三 Python 哪个学期」，否则只能 WHERE 1=1 倒全表
        '{"query":"{{#sys.query#}}","user_id":{{#start.user_id#}},'
        '"conversation_id":"{{#sys.conversation_id#}}"}',
        fail_hint="没有查到符合条件的数据，可能条件不对或系统暂时不可用。",
    ))
    nodes.append(llm_node(
        "query_llm", 1180, y, "查询结果播报",
        persona + """
员工要查一条业务数据，后端已按意图生成 SQL 并返回结果。
""" + COMMON_RULES + """
6. 有数据时先用一句话点明查的是哪类数据（例如「查到 2 条投诉工单」）再播报 rows，最多播 5 条，多的说「还有 N 条」；
   没有数据时直接说「没有查到」，不要先说「查到 0 条」。
7. 严格按 hint 的提示组织语言；rows 为空时说"没有查到"，并给出可调整的条件，绝不许编数据。
7.1 如果 data.need_clarify 为 true：这是承接上一轮、但没听出要查谁要查哪门课的追问。
    不要播报数据、不要说「没有查到」，直接用一句话反问对方想查哪位学生、哪门课。反问完就结束。
7.2 如果 data.resolved_query 有值（说明系统是结合上文理解的），开头先说清「你问的是…」，
    只针对那一条回答（例如报出姓名、课程、分数、学期），不要罗列其它学生或其它课程。
8. 最后一行：如果 data.sql_line 有值，就把这一整行原样照抄（它已包含「查询语句：」和 SQL）；
   data.sql_line 为空时，回答到上一句就结束，不要自己写「查询语句」四个字，也不要留空行。
9. 如果 intent 是 crm_lead_update，说明这是修改操作，让对方确认后再走「客户状态流转」。
""",
        "员工说：{{#sys.query#}}\n\n工具返回：{{#query_http.body#}}\n\n"
        "请按 hint 播报结果。只有当工具返回里 data.sql_line 有值时才把这一整行照抄到末尾；"
        "data.sql_line 为空或不存在时，正常收尾，不要出现「查询语句」四个字。",
    ))
    nodes.append(answer_node("query_ans", 1500, y, ["query_llm", "text"], "查询回复"))
    to_branch("c_query", "query_http")
    edges.append(edge("query_http", "query_llm", "http-request", "llm"))
    edges.append(edge("query_llm", "query_ans", "llm", "answer"))

    # --- 客户录入（抽取 + 入库）
    y += 230
    nodes.append(extract_node(
        "lead_create_extract", 860, y, "抽取客户信息",
        "你是一个信息抽取器。把员工的话转成客户档案 JSON，只输出 JSON，不要任何解释、不要 markdown 代码块。\n"
        "输出格式：\n"
        '{"customer_name":"客户姓名","contact_info":"手机号，没有就填空字符串",'
        '"background_info":"年龄、学历、意向等背景","follow_up_history":"本次沟通记录",'
        f'"owner_employee_id":"{{{{#start.user_id#}}}}"}}\n'
        "客户姓名抽不出来时填「未提供」。",
        "员工说：{{#sys.query#}}",
    ))
    nodes.append(http_node(
        "lead_create_http", 1180, y, "写入客户档案",
        "post", f"{HOST}/api/agent/lead-create", "{{#lead_create_extract.text#}}",
        fail_hint="客户没有录入成功：姓名或联系方式可能不完整，请补充后再试。",
    ))
    nodes.append(llm_node(
        "lead_create_llm", 1500, y, "录入回执",
        persona + "\n客户刚录入系统，你要给员工确认。\n" + COMMON_RULES,
        "员工说：{{#sys.query#}}\n\n工具返回：{{#lead_create_http.body#}}\n\n"
        "请确认已录入的客户姓名、背景和当前状态（新增意向），并提示他记得补跟进记录。",
    ))
    nodes.append(answer_node("lead_create_ans", 1820, y, ["lead_create_llm", "text"], "客户录入回复"))
    to_branch("c_lead_create", "lead_create_extract", tgt_type="llm")
    edges.append(edge("lead_create_extract", "lead_create_http", "llm", "http-request"))
    edges.append(edge("lead_create_http", "lead_create_llm", "http-request", "llm"))
    edges.append(edge("lead_create_llm", "lead_create_ans", "llm", "answer"))

    # --- 状态流转
    y += 230
    nodes.append(extract_node(
        "lead_status_extract", 860, y, "抽取流转参数",
        "你是一个信息抽取器。提取客户姓名和目标状态，只输出 JSON，不要解释、不要代码块。\n"
        "status 只能是 新增意向 / 跟进中 / 已签约 / 已流失 之一。\n"
        '输出格式：{"customer_name":"客户姓名","status":"目标状态"}',
        "员工说：{{#sys.query#}}",
    ))
    nodes.append(http_node(
        "lead_status_http", 1180, y, "更新客户状态",
        "put", f"{HOST}/api/agent/lead-status-by-name", "{{#lead_status_extract.text#}}",
        fail_hint="没有找到这位客户：档案里可能没有这个名字，或姓名不唯一、状态值不合法。请让对方确认姓名是否已录入，不要编造客户。",
    ))
    nodes.append(llm_node(
        "lead_status_llm", 1500, y, "流转回执",
        persona + "\n客户状态刚被更新，你要向员工确认结果。\n" + COMMON_RULES,
        "员工说：{{#sys.query#}}\n\n工具返回：{{#lead_status_http.body#}}\n\n"
        "请说明：哪个客户、从什么状态变成了什么状态。",
    ))
    nodes.append(answer_node("lead_status_ans", 1820, y, ["lead_status_llm", "text"], "状态流转回复"))
    to_branch("c_lead_status", "lead_status_extract", tgt_type="llm")
    edges.append(edge("lead_status_extract", "lead_status_http", "llm", "http-request"))
    edges.append(edge("lead_status_http", "lead_status_llm", "http-request", "llm"))
    edges.append(edge("lead_status_llm", "lead_status_ans", "llm", "answer"))

    # --- 日报
    y += 230
    nodes.append(http_node(
        "report_http", 860, y, "保存日报",
        "post", f"{HOST}/api/agent/report-create",
        '{"employee_id":"{{#start.user_id#}}","content":"{{#sys.query#}}"}',
    ))
    nodes.append(llm_node(
        "report_llm", 1180, y, "日报回执",
        persona + "\n员工刚提交日报，你要做结构化复述。\n" + COMMON_RULES,
        "员工说：{{#sys.query#}}\n\n工具返回：{{#report_http.body#}}\n\n"
        "请把日报内容整理成三条要点复述给他，不要篡改事实。",
    ))
    nodes.append(answer_node("report_ans", 1500, y, ["report_llm", "text"], "日报回复"))
    to_branch("c_daily_report", "report_http")
    edges.append(edge("report_http", "report_llm", "http-request", "llm"))
    edges.append(edge("report_llm", "report_ans", "llm", "answer"))

    # --- 成绩录入
    y += 230
    nodes.append(extract_node(
        "score_extract", 860, y, "抽取成绩参数",
        "你是一个信息抽取器。提取学生姓名、课程名、分数，只输出 JSON，不要解释、不要代码块。\n"
        "如果是查询（没有给出具体分数），score 填 null，不要猜一个分数。\n"
        "overwrite：员工说「覆盖」「改成」「改一下」「按这个改」时填 true，否则 false。\n"
        "如果员工这句话只说「覆盖」而没给姓名/课程/分数，就从[上文]里找回上一轮提到的那位学生、"
        "那门课，以及上一轮提示里要改成的分数。\n"
        '输出格式：{"student_name":"学生姓名","course_name":"课程名","score":分数数字或null,'
        '"semester":"学期，没有就填空字符串","overwrite":false}',
        "员工说：{{#sys.query#}}",
        memory=True,
    ))
    nodes.append(http_node(
        "score_entry_http", 1180, y, "写入成绩",
        "post", f"{HOST}/api/agent/score-create-by-name", "{{#score_extract.text#}}",
        fail_hint="成绩录入失败：可能没给具体分数、学生不存在，或分数超出该课程的量纲（雅思 0~9、其他 0~100），请核对后重试。",
    ))
    nodes.append(llm_node(
        "score_entry_llm", 1500, y, "录入回执",
        persona + "\n成绩刚录入系统，你要确认结果。\n" + COMMON_RULES + """
6. 如果返回里没有分数（detail 说需要分数），就说明这是查询而不是录入，让他去查成绩，不要声称已录入。
7. 如果 data.need_confirm 为 true：说明这门课已经有成绩了，本次【没有】写入。要把学生、课程、原分数、想改成多少都说清楚，并问他要不要覆盖。绝不能说"已录入"。
8. 如果 data.updated 为 true：说明是覆盖修改，要说明「从 X 分改为 Y 分」。
9. 回执里必须带上 data.semester 的学期（例如「记入 2025-2026 第二学期」）。
   如果 data.semester_auto 为 true，说明员工没提学期、系统按该生所在学期自动归档，
   要补一句「没指定学期，按他所在学期归档了，要改的话告诉我学期」——不能只说分数不提学期。
""",
        "员工说：{{#sys.query#}}\n\n工具返回：{{#score_entry_http.body#}}\n\n"
        "请按 data 里的 duplicated / updated 字段如实确认结果。",
    ))
    nodes.append(answer_node("score_entry_ans", 1820, y, ["score_entry_llm", "text"], "成绩录入回复"))
    to_branch("c_score_entry", "score_extract", tgt_type="llm")
    edges.append(edge("score_extract", "score_entry_http", "llm", "http-request"))
    edges.append(edge("score_entry_http", "score_entry_llm", "http-request", "llm"))
    edges.append(edge("score_entry_llm", "score_entry_ans", "llm", "answer"))

    # --- 预警处理（认领 / 解除）
    y += 230
    nodes.append(extract_node(
        "alert_extract", 860, y, "抽取预警参数",
        "你是一个信息抽取器。提取学生姓名和要改成的状态，只输出 JSON，不要解释、不要代码块。\n"
        "status 只能是 未处理 / 跟进中 / 已解除 之一：\n"
        "- 「认领」「跟进」「我接手」「处理中」→ 跟进中\n"
        "- 「解除」「关闭」「解决」「处理完」→ 已解除\n"
        "- 「重置」「恢复」→ 未处理\n"
        '输出格式：{"student_name":"学生姓名","status":"跟进中"}',
        "员工说：{{#sys.query#}}",
    ))
    nodes.append(http_node(
        "alert_http", 1180, y, "更新预警状态",
        "put", f"{HOST}/api/agent/alert-status-by-name", "{{#alert_extract.text#}}",
        fail_hint="预警状态没改成功：可能这个名字匹配不到学生，或者状态说法不清楚，请核对姓名。",
    ))
    nodes.append(llm_node(
        "alert_llm", 1500, y, "预警回执",
        persona + "\n员工刚处理了一条心理预警，你要给回执。\n" + COMMON_RULES + """
6. 有 data.old_status 时说明「从 X 改为 Y」，并带上风险等级；不要展开学生隐私细节。
7. 如果 data.has_alert 为 false，说明这位学生目前没有预警记录，不需要处理。
""",
        "员工说：{{#sys.query#}}\n\n工具返回：{{#alert_http.body#}}\n\n请如实确认处理结果。",
    ))
    nodes.append(answer_node("alert_ans", 1820, y, ["alert_llm", "text"], "预警处理回复"))
    to_branch("c_alert_handle", "alert_extract", tgt_type="llm")
    edges.append(edge("alert_extract", "alert_http", "llm", "http-request"))
    edges.append(edge("alert_http", "alert_llm", "http-request", "llm"))
    edges.append(edge("alert_llm", "alert_ans", "llm", "answer"))

    # --- 制度与新人指引
    y += 230
    nodes.append(kb_node("handbook_kb", 860, y, [DS_HANDBOOK], top_k=6, threshold=0.3))
    nodes.append(llm_node(
        "handbook_llm", 1180, y, "制度问答",
        "你是「粤教服务」的内部行政助手，负责回答新人入职、办公设施、IT 支持、公司福利、制度流程等问题。\n"
        "只依据下面检索到的《公司新人指南》内容回答；涉及人名、分机、电话、位置、时间时照原文给出，不要自己编。\n"
        "检索内容没覆盖的，直接说「手册里没有这条，建议问行政同事（分机 8001）」。\n"
        "如果员工问的是学生请假审批进度、还有哪些请假待批，不要引用手册内容，直接告诉他：页面右上角有「请假审批」面板，点开就能看到待审批的学生、请假时间和事由，并可以直接通过或驳回。\n"
        "回答用中文，控制在 6 句话以内，能分条的就分条列。",
        "员工问：{{#sys.query#}}\n\n参考资料：{{#context#}}",
        context_selector=["handbook_kb", "result"],
    ))
    nodes.append(answer_node("handbook_ans", 1500, y, ["handbook_llm", "text"], "制度回复"))
    to_branch("c_handbook", "handbook_kb", tgt_type="knowledge-retrieval")
    edges.append(edge("handbook_kb", "handbook_llm", "knowledge-retrieval", "llm"))
    edges.append(edge("handbook_llm", "handbook_ans", "llm", "answer"))

    # --- 其他：能力清单
    y += 230
    nodes.append(llm_node(
        "emp_other_llm", 1180, y, "能力说明",
        persona + """
员工提了一个你办不到的请求。要说清边界并给出可行替代：
- 要密钥、密码、数据库连接串：明确拒绝，说明这些不对普通员工开放，需要走 IT 工单。
- 与业务无关（天气、写代码、闲聊）：先用一句话带过，然后**必须**列出你能做的事，
  至少覆盖五项：查客户档案、查学生成绩、查请假审批进度、查员工日报、查投诉工单、查心理预警。
  不要只回一句「帮不上忙」就结束。
- 其他做不到的事：说清该找哪个部门。
不要编造数据，不要承诺系统没有的功能。
""" + COMMON_RULES,
        "员工说：{{#sys.query#}}",
    ))
    nodes.append(answer_node("emp_other_ans", 1500, y, ["emp_other_llm", "text"], "说明回复"))
    to_branch("c_other", "emp_other_llm", tgt_type="llm")
    edges.append(edge("emp_other_llm", "emp_other_ans", "llm", "answer"))

    return {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 0.6}}


# ---------------------------------------------------------------------------
# 三、客服与活动
# ---------------------------------------------------------------------------

def build_customer():
    nodes, edges = [], []
    start_id, prep_id, cls_id = "start", "prepare", "classifier"

    nodes.append(start_node(start_id, 40, 420, [
        {"key": "user_id", "label": "客户ID", "type": "number", "value": 1},
        {"key": "customer_name", "label": "客户称呼", "type": "text-input", "value": "陈女士"},
        {"key": "history_hint", "label": "上文摘要", "type": "paragraph", "value": ""},
    ]))
    nodes.append(prepare_node(prep_id, 280, 420))
    edges.append(edge(start_id, prep_id, "start", "template-transform"))
    edges.append(edge(prep_id, cls_id, "template-transform", "question-classifier"))

    classes = [
        {"id": "c_recommend", "name": "留学项目推荐：描述年龄、学历、预算、意向，希望匹配适合的留学项目，例如「19岁高中刚毕业想快点拿本科学历」。只表达意向但没说条件的（例如「想出国」「我想留学」「不知道读什么」）也归这一类"},
        {"id": "c_project_query", "name": "项目或课程查询：问有哪些项目、某个项目读几年、学什么课程、包含哪些服务、适合什么人，例如「德国双元制项目是什么」「0.5+1 要读几年」"},
        {"id": "c_event_query", "name": "活动查询：问最近有什么讲座、分享会、说明会，某场活动还有没有名额、已经有哪些人报名（名单），例如「这周有什么活动」「新加坡分享会还有名额吗」「这场活动都谁报名了」"},
        {"id": "c_event_register", "name": "活动报名：客户**自己**要报名某场活动（讲座/分享会/说明会/沙龙），主语是「我」要参加，例如「我要报名新加坡留学分享会」「帮我报个名」。注意：问「谁报名了」「有哪些人报名」是查名单，不属于这里；报名某个留学项目属于项目咨询"},
        {"id": "c_leave_contact", "name": "留资登记：客户报出自己的姓名、手机号、微信，希望顾问联系他，例如「我叫陈晨，电话13800138000，帮我安排老师联系」"},
        {"id": "c_child_query", "name": "家长查孩子：家长问自己孩子的成绩、考得怎么样、请假批了没、报了什么活动，例如「我孩子这次考了多少分」「孩子请假通过了吗」。注意：问留学项目、费用、活动报名不属于这一类"},
        {"id": "c_faq", "name": "公司与政策咨询：学费多少钱、费用与预算、申请条件、入学要求、留学政策、签证与材料清单、公司介绍、某个项目怎么申请怎么报名，以及不属于上面任何一类的问题"},
    ]
    nodes.append(classifier_node(cls_id, 520, 200, classes))

    persona = "你是「粤教服务」的售前顾问，服务对象是想出国留学的学生和家长，负责项目推荐、课程查询、活动报名和公司政策咨询。"

    def to_branch(cid, node_id, tgt_type="http-request"):
        edges.append(edge(cls_id, node_id, "question-classifier", tgt_type, handle=cid))

    # --- 项目推荐（画像研判）
    y = 40
    nodes.append(http_node(
        "recommend_http", 860, y, "画像研判推荐",
        "post", f"{HOST}/api/agent/profile-evaluate",
        '{"raw_text":"{{#sys.query#}}"}',
    ))
    nodes.append(llm_node(
        "recommend_llm", 1180, y, "推荐话术",
        persona + """
客户正在咨询该读什么项目，你要基于规则引擎的匹配结果做推荐。
""" + COMMON_RULES + """
6. 必须说出推荐项目的全名和匹配度分值，再给 2 条推荐理由。
7. 如果 matches 为空（用户没说年龄或学历），本次回答**只做一件事：追问**。第一句就必须是问题，问最高学历（在读还是已毕业）和年龄。
   整段回答里禁止出现任何国家名、项目名、费用数字，禁止列「你可以考虑 A/B/C 几个方向」这类清单。
   最多补一句「不同学历对应的路径差别很大」，然后立刻提问。
8. 不要承诺录取结果、不要报出资料里没有的费用数字。
9. 结尾必须问一句：方便留个姓名和手机号吗，我让顾问老师把项目资料发给你（引导留资）。
""",
        "客户说：{{#sys.query#}}\n\n工具返回：{{#recommend_http.body#}}\n\n"
        "请先复述你从他的话里读到的画像（年龄、学历、意向），再推荐最适合的项目。",
        memory=True,
    ))
    nodes.append(answer_node("recommend_ans", 1500, y, ["recommend_llm", "text"], "推荐回复"))
    to_branch("c_recommend", "recommend_http")
    edges.append(edge("recommend_http", "recommend_llm", "http-request", "llm"))
    edges.append(edge("recommend_llm", "recommend_ans", "llm", "answer"))

    # --- 项目查询
    y += 230
    nodes.append(http_node(
        "project_http", 860, y, "项目列表查询",
        "get", f"{HOST}/api/agent/project-list",
    ))
    nodes.append(llm_node(
        "project_llm", 1180, y, "项目介绍",
        persona + "\n客户想了解具体项目，你要从项目清单里挑出相关的介绍。\n" + COMMON_RULES + """
6. 如果[上文]提到过某个项目而当前问题只是「学费多少/读几年/怎么报名」，就按那个项目回答，不要换成别的国家。
""",
        "客户问：{{#sys.query#}}\n\n上文：{{#start.history_hint#}}\n\n工具返回：{{#project_http.body#}}\n\n"
        "请只讲和他问题相关的项目（项目名、适合人群、学制、特点），不要把所有项目都念一遍；项目清单里没有费用数字就说「费用让顾问老师给你准确报价」。",
        memory=True,
    ))
    nodes.append(answer_node("project_ans", 1500, y, ["project_llm", "text"], "项目回复"))
    to_branch("c_project_query", "project_http")
    edges.append(edge("project_http", "project_llm", "http-request", "llm"))
    edges.append(edge("project_llm", "project_ans", "llm", "answer"))

    # --- 活动查询
    y += 230
    nodes.append(http_node(
        "event_http", 860, y, "活动与名单查询",
        "post", f"{HOST}/api/agent/nl2sql",
        # 同样带上会话：客户问「那场讲座还有名额吗」时后端要能回到上文找活动名
        '{"query":"{{#sys.query#}}","user_id":{{#start.user_id#}},'
        '"conversation_id":"{{#sys.conversation_id#}}"}',
    ))
    nodes.append(llm_node(
        "event_llm", 1180, y, "活动播报",
        persona + "\n客户在问活动，也可能在问某场活动已经有哪些人报名。\n" + COMMON_RULES + """
6. data.rows 里是活动（有 event_name + remaining）时：报名称、时间、地点、剩余名额，并邀请他报名。
7. data.rows 里是报名人（有 customer_name）时：报活动名和报名人姓名，不要邀请他报名。
""",
        "客户问：{{#sys.query#}}\n\n工具返回：{{#event_http.body#}}\n\n按返回内容判断这次是活动清单还是报名名单。",
    ))
    nodes.append(answer_node("event_ans", 1500, y, ["event_llm", "text"], "活动回复"))
    to_branch("c_event_query", "event_http")
    edges.append(edge("event_http", "event_llm", "http-request", "llm"))
    edges.append(edge("event_llm", "event_ans", "llm", "answer"))

    # --- 活动报名
    y += 230
    nodes.append(extract_node(
        "register_extract", 860, y, "抽取报名信息",
        "你是一个信息抽取器。提取客户想报名的活动名称，只输出 JSON，不要解释、不要代码块。\n"
        "owner_employee_id 固定填 3（由李老师接手）。\n"
        '输出格式：{"event_name":"活动名称","customer_id":"{{#start.user_id#}}"}',
        "客户说：{{#sys.query#}}",
    ))
    nodes.append(http_node(
        "register_http", 1180, y, "活动报名",
        "post", f"{HOST}/api/agent/event-register?soft_fail=1", "{{#register_extract.text#}}",
        fail_hint="报名接口暂时不可用（网络或服务异常），请稍后再试一次。",
    ))
    nodes.append(llm_node(
        "register_llm", 1500, y, "报名回执",
        persona + "\n客户刚报名了活动，你要给回执。\n" + COMMON_RULES + """
6. 先看工具返回的 data.success：
   - true（或返回里没有 success 字段且 msg 含「报名成功」）：确认活动名称、时间、地点，说明名额已占用。
   - false：说明 msg 里的真实原因，**原样引用活动名和人数**（例如「名额已满（30/30）」）。禁止写「可能是名额已满」「请核对活动名称」这类猜测措辞，因为你已经知道确切原因了。
7. 如果 data.duplicated 为 true，告诉他之前已经报过这一场，不用重复提交，回执号保持不变。
""",
        "客户说：{{#sys.query#}}\n\n工具返回：{{#register_http.body#}}\n\n"
        "请按 data.success 和 msg 如实给回执。",
    ))
    nodes.append(answer_node("register_ans", 1820, y, ["register_llm", "text"], "报名回复"))
    to_branch("c_event_register", "register_extract", tgt_type="llm")
    edges.append(edge("register_extract", "register_http", "llm", "http-request"))
    edges.append(edge("register_http", "register_llm", "http-request", "llm"))
    edges.append(edge("register_llm", "register_ans", "llm", "answer"))

    # --- 留资登记（FR-024）
    y += 230
    nodes.append(extract_node(
        "contact_extract", 860, y, "抽取联系方式",
        "你是一个信息抽取器。提取客户姓名、手机号、意向方向与备注，只输出 JSON，不要解释、不要代码块。\n"
        "客户ID固定用下面的值；没有手机号就填空字符串。\n"
        '输出格式：{"customer_name":"姓名","contact_info":"手机号","background_info":"意向方向",'
        '"follow_up_history":"对话中的诉求","owner_employee_id":3}',
        "客户说：{{#sys.query#}}\n\n上文：{{#start.history_hint#}}",
    ))
    nodes.append(http_node(
        "contact_http", 1180, y, "写入客户线索",
        "post", f"{HOST}/api/agent/lead-create", "{{#contact_extract.text#}}",
        fail_hint="留资没有保存成功：联系方式可能识别失败，请让对方再报一次手机号。",
    ))
    nodes.append(llm_node(
        "contact_llm", 1500, y, "留资回执",
        persona + "\n客户留下了联系方式，你要给回执。\n" + COMMON_RULES,
        "客户说：{{#sys.query#}}\n\n工具返回：{{#contact_http.body#}}\n\n"
        "请确认已登记，并说明顾问会在多久内联系他；不要重复索要已经给过的信息。",
    ))
    nodes.append(answer_node("contact_ans", 1820, y, ["contact_llm", "text"], "留资回复"))
    to_branch("c_leave_contact", "contact_extract", tgt_type="llm")
    edges.append(edge("contact_extract", "contact_http", "llm", "http-request"))
    edges.append(edge("contact_http", "contact_llm", "http-request", "llm"))
    edges.append(edge("contact_llm", "contact_ans", "llm", "answer"))

    # --- 家长查孩子（成绩 / 请假 / 活动）
    y += 230
    nodes.append(http_node(
        "child_http", 860, y, "家长视图查询",
        "get", f"{HOST}/api/agent/parent-view?parent_id={{{{#start.user_id#}}}}",
        fail_hint="这个账号没有绑定学生档案，可能不是家长账号；请说明只有家长账号能查孩子信息。",
    ))
    nodes.append(llm_node(
        "child_llm", 1500, y, "家长播报",
        persona + "\n对方是学生家长，问的是自己孩子的情况。\n" + COMMON_RULES + """
6. 只讲 data 里这位孩子的情况，不要提到别的学生。
7. 问成绩就给各科分数和平均分（平均分不含雅思/托福）；问请假就说最近一次的状态和审批人；问活动就说报名了哪一场。
8. 如果 data.bound 为 false，说明这个账号还没绑定学生，请家长联系教务老师。
""",
        "家长问：{{#sys.query#}}\n\n工具返回：{{#child_http.body#}}\n\n请用家长能听懂的话回答。",
    ))
    nodes.append(answer_node("child_ans", 1820, y, ["child_llm", "text"], "家长回复"))
    to_branch("c_child_query", "child_http")
    edges.append(edge("child_http", "child_llm", "http-request", "llm"))
    edges.append(edge("child_llm", "child_ans", "llm", "answer"))

    # --- 公司与政策
    y += 230
    nodes.append(kb_node("faq_kb", 860, y, [DS_PROJECT], top_k=10, threshold=0.3))
    nodes.append(llm_node(
        "faq_llm", 1180, y, "政策问答",
        "你是「粤教服务」的咨询顾问，回答公司介绍、留学政策、费用标准、签证材料、申请流程等问题。\n"
        "只依据下面检索到的资料回答。涉及学费、学制、分数、时间、政策条款时，照抄资料里的数字和表述，不许自己算、不许编。\n"
        "资料没覆盖的，直接说「这个我需要让顾问老师跟你确认」。\n"
        "第一句先直接回答客户问的那件事，再补充相关细节，不要跑题去介绍别的项目。\n"
        "如果[上文]提到过某个项目或国家，而当前问题很简短（例如「学费多少」「怎么报名」），就沿用上文那个项目回答。\n"
        "客户问申请条件、政策、材料、费用时，按资料里的条款直接答，不要用某个项目班的招生介绍来代替。\n"
        "资料里同时给了「培训津贴」和「毕业后薪资」时，两个都要说：培训期间是津贴（例如第一年 880 欧/月、第二年 950、第三年 1030），毕业后才是工资（例如 2100-3500 欧/月），要把两者区分开，不要只挑一个。\n"
        "如果客户只说了「想出国」「想留学」这类没有具体对象的诉求，不要罗列国家清单、不要报费用，先用一句话问清最高学历（在读还是已毕业）和年龄。\n"
        "回答用中文，控制在 6 句话以内，信息多就分条列。",
        "客户问：{{#sys.query#}}\n\n上文：{{#start.history_hint#}}\n\n参考资料：{{#context#}}",
        context_selector=["faq_kb", "result"],
        memory=True,
    ))
    nodes.append(answer_node("faq_ans", 1500, y, ["faq_llm", "text"], "咨询回复"))
    to_branch("c_faq", "faq_kb", tgt_type="knowledge-retrieval")
    edges.append(edge("faq_kb", "faq_llm", "knowledge-retrieval", "llm"))
    edges.append(edge("faq_llm", "faq_ans", "llm", "answer"))

    return {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 0.6}}


# ---------------------------------------------------------------------------
# 写入 Dify
# ---------------------------------------------------------------------------

APPS = {
    "student": ("638eb8a4-447e-4f28-b8a6-9c6b70a0f485", build_student),
    "employee": ("c4b69cae-f343-4260-9d38-383149c43d8f", build_employee),
    "customer": ("6d7af072-af9e-400c-b59d-6078455ba1f0", build_customer),
}


def push(key, only=None):
    app_id, builder = APPS[key]
    if only and key not in only:
        return
    graph = builder()
    print(f"[{key}] nodes={len(graph['nodes'])} edges={len(graph['edges'])}")

    # Dify 的草稿接口带乐观锁，必须回传当前草稿的 hash
    code, current = dify_api.call("GET", f"/apps/{app_id}/workflows/draft")
    current_hash = current.get("hash") if code == 200 else None

    payload = {
        "graph": graph,
        "features": FEATURES,
        "environment_variables": [],
        "conversation_variables": [],
    }
    if current_hash:
        payload["hash"] = current_hash
    code, data = dify_api.call("POST", f"/apps/{app_id}/workflows/draft", payload)
    print(f"[{key}] draft update -> HTTP {code}")
    if code != 200:
        print(json.dumps(data, ensure_ascii=False)[:1500])
        return
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), f"graph_{key}.json"), "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=1)
    print(f"[{key}] ok, hash={data.get('hash')}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    auto_publish = "--publish" in sys.argv[1:]
    only = args or None
    for key in APPS:
        if only and key not in only:
            continue
        push(key, only)
        if not auto_publish:
            continue
        # 只更新草稿不会生效，必须发布；这里顺带校验 published_at 真的变了
        app_id = APPS[key][0]
        code, before = dify_api.call("GET", f"/apps/{app_id}/workflows/publish")
        old_at = (before.get("created_at") if code == 200 else None) or {}
        code, res = dify_api.call("POST", f"/apps/{app_id}/workflows/publish")
        if code != 200:
            print(f"[{key}] !! publish 失败 HTTP {code}：{json.dumps(res, ensure_ascii=False)[:300]}")
            print(f"[{key}] !! 当前线上仍是旧版本，别拿它做测试")
            continue
        code, after = dify_api.call("GET", f"/apps/{app_id}/workflows/publish")
        new_at = (after.get("created_at") if code == 200 else None) or {}
        if new_at and old_at and new_at == old_at:
            print(f"[{key}] !! published_at 没变（{new_at}），发布可能没生效")
        else:
            print(f"[{key}] published at {new_at}")
