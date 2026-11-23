"""把「心理关怀话术」节点恢复成改造前的样子（提示词 + 温度 0.3 + max_tokens 2000）。

用法：python dify_emotion_restore.py 生成 SQL，再
  docker exec -i docker-db-1 psql -U postgres -d dify -f - < dify_backup/restore.sql
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
BACKUP = os.path.join(HERE, "dify_backup")
TARGETS = {
    "student_published_graph.json": "96d6b945-dc3f-407a-9e7c-7ac7076d034e",
    "student_draft_graph.json": "e42b0336-f2ce-4b8e-9193-508f8b71e3ff",
}
parts = ["SET client_encoding='UTF8';"]
for fname, wid in TARGETS.items():
    raw = open(os.path.join(BACKUP, fname), encoding="utf-8").read().strip()
    json.loads(raw)  # 校验备份没被破坏
    parts.append(f"UPDATE workflows SET graph=$g${raw}$g$, updated_at=now() WHERE id='{wid}';")
out = os.path.join(BACKUP, "restore.sql")
open(out, "w", encoding="utf-8").write("\n".join(parts) + "\n")
print("已生成", out)
