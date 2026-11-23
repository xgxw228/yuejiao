"""端到端复现：录入成绩 → 追问「这是哪个学期的成绩？」"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"


def stream(agent, query, user_id=3, conv_id=""):
    body = {"agent": agent, "query": query, "user_id": user_id, "conversation_id": conv_id}
    req = urllib.request.Request(
        f"{BASE}/api/chat/stream",
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
    )
    text, new_conv = "", conv_id
    with urllib.request.urlopen(req, timeout=180) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            try:
                evt = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            if "text" in evt:
                text += evt["text"]
            if evt.get("conversation_id"):
                new_conv = evt["conversation_id"]
            if evt.get("message") and "degraded" in evt:
                text += f"\n[降级] {evt['message']}"
    return text.strip(), new_conv


if __name__ == "__main__":
    turns = sys.argv[1:] or ["给张三录入线性代数课程成绩88分", "这是哪个学期的成绩？"]
    conv = ""
    for q in turns:
        ans, conv = stream("employee", q, 3, conv)
        print(f"\n>>> {q}\n{ans}")
