"""调试用：直接跑某个应用的草稿工作流，打印节点执行轨迹与最终回复。"""

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dify_api

APPS = {
    "student": "638eb8a4-447e-4f28-b8a6-9c6b70a0f485",
    "employee": "c4b69cae-f343-4260-9d38-383149c43d8f",
    "customer": "6d7af072-af9e-400c-b59d-6078455ba1f0",
}


def run_draft(app_id, query, inputs=None):
    url = f"http://localhost/console/api/apps/{app_id}/advanced-chat/workflows/draft/run"
    payload = json.dumps({
        "inputs": inputs or {},
        "files": [],
        "query": query,
        "conversation_id": None,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=dify_api.headers(), method="POST")
    answer, errors, trace = [], [], []
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            for raw in r:
                line = raw.decode("utf-8", "ignore").strip()
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if not chunk or chunk == "[DONE]":
                    continue
                try:
                    ev = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                event = ev.get("event")
                if event in ("node_started",):
                    trace.append(f"  → {ev.get('data', {}).get('title')}")
                elif event == "node_finished":
                    d = ev.get("data", {})
                    status = d.get("status")
                    if status != "succeeded":
                        errors.append(f"{d.get('title')}: {str(d.get('error'))[:300]}")
                    else:
                        trace.append(f"  ✓ {d.get('title')}")
                elif event in ("message", "agent_message"):
                    answer.append(ev.get("answer", ""))
                elif event == "workflow_finished":
                    data = ev.get("data", {})
                    err = data.get("error")
                    if err:
                        errors.append(str(err)[:400])
                elif event == "error":
                    errors.append(f"{ev.get('code')}: {ev.get('message')}")
    except urllib.error.HTTPError as e:
        errors.append(f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}")
    return "".join(answer), errors, trace


if __name__ == "__main__":
    key = sys.argv[1]
    query = sys.argv[2]
    inputs = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    ans, errs, tr = run_draft(APPS[key], query, inputs)
    print("\n".join(tr))
    print("=== ANSWER ===")
    print(ans.strip() or "(空)")
    if errs:
        print("=== ERRORS ===")
        for e in errs:
            print(" ! ", e)
