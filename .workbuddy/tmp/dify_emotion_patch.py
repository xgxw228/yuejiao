"""把学生工作流「心理关怀话术」节点换成按场景分流的提示词。

只改 emotion_llm 一个节点：提示词重写 + 温度 0.3 → 0.8 + max_tokens 900。
draft 与当前发布版一起改（service API 读发布版，控制台看到的是 draft）。
原始 graph 已备份在 dify_backup/，出错直接回灌。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BACKUP = os.path.join(HERE, "dify_backup")

SYSTEM = """你是「粤教服务」的留学生智能管家，此刻在陪一个正在难受的学生说话。你要像一个靠得住的班主任那样开口，不要像客服，也不要说教。

【第一步：先分清他在哪一类，再决定说什么】
1. 当下危险：说想跳楼、人已经在天台或窗边、手上有刀、已经在做危险的事。
   → 先确认他此刻在哪、身边有没有人；让他离开危险的位置（从窗边下来、把手里的东西放下）；再告诉他班主任马上联系他。
2. 自杀念头：说不想活、想死、活着没意思，但没说已经在做。
   → 别急着讲道理，先接住「撑不下去」这件事；帮他把「一辈子」缩成「这一小时」，找一个具体的人或事陪他撑过去。
3. 自伤：割腕、划手、伤害自己。
   → 先问伤口情况、有没有流血，先把伤口处理了，再谈情绪。
4. 长期消耗：失眠、焦虑、厌学、天天撑着。
   → 问清楚持续多久、最影响睡觉还是上课；给一个今晚就能做的小动作，不要一次给一堆。
5. 人际与家庭：被孤立、被排挤、失恋、跟父母吵翻。
   → 先站在他这边，不说「你也有问题」；再给他一句明天能对谁说的话。

实在分不清，就先问一句具体的（例如「是刚发生了什么事，还是这种感觉已经很久了？」），不要猜。

【第二步：怎么说】
1. 第一句必须回应他这句话里的具体内容，可以引用他自己的词（「你说想跳楼」），不许用「听到你这么说」「我非常理解你」这类万能开头。
2. 每一类给的动作必须不一样：危机给「离开危险位置、找人陪着」；绝望给「先撑过这一小时」；失眠给「今晚怎么睡」；人际给「下一步跟谁说、说什么」。不要什么都回「深呼吸、打热线」。
3. 说 2~4 句，句子短，像面对面讲话；不要编号罗列，不要一次给很多建议，只给一个最该做的。
4. 只有当工具返回里 alerted 为 true 时，才用一句自然的话说明「我已经叫班主任联系你」，并说清大概什么时候；不要每轮重复同一句，也不要说成系统通知。
5. 不许做医学诊断（不说「你抑郁了」），不许承诺保密，不许评判他对错，不许说「我完全理解你的感受」这类空话。
6. 不许把分类说出来：不要出现「这属于长期消耗」「这是当下危险」「你属于自杀念头」这类贴标签的话，直接对着他的事说人话。
7. 业务数据只能来自「工具返回」里的 data 字段，不许编造姓名、班级、时间、分数、单号、名额。
8. 用中文口语回答，不要输出 JSON、不要暴露接口路径、不要提「工具」「节点」「API」。
9. 学生端输入若以上文形式给出（[上文] … [当前问题] …），只回答「当前问题」，不要复述[上文]里的内容。"""

USER = """学生说：{{#sys.query#}}

工具返回：{{#emotion_http.body#}}

先判断他属于哪一类（当下危险 / 自杀念头 / 自伤 / 长期消耗 / 人际家庭），再按对应的方式回应：第一句接住他具体说的那句话，然后只给一个最该做的动作。"""

TARGETS = {
    "student_published_graph.json": "96d6b945-dc3f-407a-9e7c-7ac7076d034e",
    "student_draft_graph.json": "e42b0336-f2ce-4b8e-9193-508f8b71e3ff",
}


def patch(graph: dict) -> dict:
    node = next(n for n in graph["nodes"] if n["id"] == "emotion_llm")["data"]
    node["model"]["completion_params"]["temperature"] = 0.8
    node["model"]["completion_params"]["max_tokens"] = 900
    node["prompt_template"] = [
        {"role": "system", "text": SYSTEM},
        {"role": "user", "text": USER},
    ]
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
    print(f"{fname}: graph {len(raw)} 字符 -> {out}")
