import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dify_api

APPS = {
    "student": "638eb8a4-447e-4f28-b8a6-9c6b70a0f485",  # 留学生管家
    "employee": "c4b69cae-f343-4260-9d38-383149c43d8f",  # 员工助手
    "customer": "6d7af072-af9e-400c-b59d-6078455ba1f0",  # 客服与活动
}

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "dumps")
os.makedirs(OUT, exist_ok=True)

for key, app_id in APPS.items():
    code, data = dify_api.call("GET", f"/apps/{app_id}/workflows/draft")
    print("=" * 50, key, code)
    if code != 200:
        print(data)
        continue
    with open(os.path.join(OUT, f"{key}_draft.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    g = data.get("graph", {})
    print("nodes:", len(g.get("nodes", [])), "edges:", len(g.get("edges", [])))
    for n in g.get("nodes", []):
        d = n["data"]
        print(f"  {n['id']:<20} {d.get('type'):<20} {d.get('title')}")
    for e in g.get("edges", []):
        print(f"  edge {e.get('source')} -> {e.get('target')}")
