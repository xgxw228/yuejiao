import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def call(method, path, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body


CASES = [
    ("画像研判 ACC-001", "POST", "/api/agent/profile-evaluate",
     {"raw_text": "我家孩子19岁、高中刚毕业、想快点拿本科学历"}),
    ("情绪高危 ACC-002", "POST", "/api/agent/emotion-evaluate",
     {"student_id": 1, "text": "最近压力好大，感觉活不下去了"}),
    ("请假解析 ACC-005", "POST", "/api/agent/leave-apply",
     {"student_id": 1, "reason": "我明天要请假一天，家里有事"}),
    ("NL2SQL ACC-003", "POST", "/api/agent/nl2sql",
     {"query": "帮我查一下许同学的跟进记录"}),
    ("满额报名 ACC-004", "POST", "/api/agent/event-register",
     {"event_name": "德国双元制项目说明会", "customer_id": 1}),
    ("正常报名 ACC-004", "POST", "/api/agent/event-register",
     {"event_name": "新加坡留学分享会", "customer_id": 1}),
    ("非法状态 ACC-006", "PUT", "/api/agent/lead-status/1", {"status": "成交了"}),
    ("合法流转 ACC-006", "PUT", "/api/agent/lead-status/2", {"status": "跟进中"}),
    ("成绩查询 ACC", "GET", "/api/agent/score-list/1", None),
    ("请假列表", "GET", "/api/agent/leave-list?student_id=1", None),
    ("心理画像", "GET", "/api/agent/psych-profile/1", None),
]

for name, method, path, payload in CASES:
    code, data = call(method, path, payload)
    text = json.dumps(data, ensure_ascii=False)
    print(f"[{code}] {name}: {text[:260]}")
