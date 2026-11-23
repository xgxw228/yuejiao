"""客服工作流「推荐话术」节点：主推之外再多给 1~2 个备选项目并附匹配分。

只改 recommend_llm 一个节点的提示词（铁律第 4、6 条 + user 结尾指引），
published 与 draft 一起改（service API 读发布版，控制台看到的是 draft）。
原始 graph 已备份在 dify_backup/cust_{published,draft}_graph.json，出错直接回灌。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BACKUP = os.path.join(HERE, "dify_backup")

TARGETS = {
    "cust_published_graph.json": "42b0da8a-b042-4a16-b6ff-bf6be44416c1",
    "cust_draft_graph.json": "6d565d1a-bfc8-411e-bdcc-9250769d31a1",
}


def patch(graph: dict) -> dict:
    node = next(n for n in graph["nodes"] if n["id"] == "recommend_llm")["data"]
    for p in node["prompt_template"]:
        if p.get("role") != "system":
            continue
        text = p["text"]
        # 第 4 条：句子上限放宽，备选需要多两三句
        text = text.replace(
            "4. 回答控制在 4 句话以内，需要罗列信息时用简短列表。",
            "4. 回答控制在 6 句话以内，需要罗列信息时用简短列表。",
        )
        # 第 6 条：主推 + 备选，各附匹配分
        text = text.replace(
            "6. 必须说出推荐项目的全名和匹配度分值，再给 2 条推荐理由。",
            "6. 推荐要有主次：先说出最推荐项目的全名和匹配度分值，再给 2 条推荐理由；"
            "然后从工具返回的 matches 里再挑 1~2 个备选项目，各附匹配度分值和一句话理由"
            "（例如「备选：××班，匹配度 85 分，理由……」），让客户有的选。"
            "备选的项目名和分值同样只能来自工具返回，matches 里没有的项目不许提。"
            "matches 里只有主推一个时，就只说主推，不要提「没有备选」「工具返回」这类词。",
        )
        p["text"] = text
    # user 提示词结尾同步改指引
    for p in node["prompt_template"]:
        if p.get("role") == "user":
            p["text"] = p["text"].replace(
                "请先复述你从他的话里读到的画像（年龄、学历、意向），再推荐最适合的项目。",
                "请先复述你从他的话里读到的画像（年龄、学历、意向），再按「主推 + 备选」推荐："
                "主推荐给出全名、匹配度和 2 条理由，之后附 1~2 个备选项目及各自匹配度和一句话理由，让客户有的选。",
            )
    return graph


for fname, wid in TARGETS.items():
    path = os.path.join(BACKUP, fname)
    with open(path, encoding="utf-8") as f:
        graph = json.load(f)
    graph = patch(graph)
    raw = json.dumps(graph, ensure_ascii=False, separators=(",", ":"))
    sql = (
        "SET client_encoding='UTF8';\n"
        f"UPDATE workflows SET graph=$g${raw}$g$, updated_at=now() WHERE id='{wid}';\n"
    )
    out = os.path.join(BACKUP, fname.replace(".json", ".sql"))
    with open(out, "w", encoding="utf-8") as f:
        f.write(sql)
    print(f"{fname}: graph {len(raw)} chars -> {out}")
