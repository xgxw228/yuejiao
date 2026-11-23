"""情绪评估引擎（FR-009 ~ FR-011）。

两级来源：
1. 优先采用 Dify 的 LLM 已判定的 emotion_tag / emotion_score；
2. 未提供时用关键词兜底，保证脱离 LLM 也能独立验收（ACC-008 降级要求）。

阈值约定（与需求文档 8.2.6 一致）：
- score >= 70 → 高危，写预警表并通知班主任
- 40 <= score < 70 → 关注，仅累积心理画像
- score < 40 → 正常
"""

from typing import Any, Dict, Optional, Tuple

HIGH_RISK_WORDS = [
    "自杀", "自残", "想死", "去死", "活不下去", "不想活", "结束生命",
    "没有意义", "死了算了", "活着没意思", "跳楼", "割腕",
]
NEGATIVE_WORDS = [
    "焦虑", "抑郁", "失眠", "压力", "难过", "孤独", "崩溃", "委屈",
    "害怕", "烦躁", "emo", "哭了", "想哭", "无助", "撑不住", "厌学",
]
POSITIVE_WORDS = [
    "开心", "高兴", "谢谢", "顺利", "喜欢", "进步", "期待", "满意",
    "不错", "太棒", "放心", "有动力",
]

HIGH_RISK_WORDS = [w.lower() for w in HIGH_RISK_WORDS]
NEGATIVE_WORDS = [w.lower() for w in NEGATIVE_WORDS]
POSITIVE_WORDS = [w.lower() for w in POSITIVE_WORDS]


def evaluate_by_keyword(text: str) -> Tuple[str, int, str]:
    """关键词兜底评估，返回 (情绪标签, 分值, 命中依据)。"""
    content = (text or "").lower()

    hit_high = [w for w in HIGH_RISK_WORDS if w in content]
    if hit_high:
        return "高危", 90, "、".join(hit_high)

    hit_neg = [w for w in NEGATIVE_WORDS if w in content]
    if hit_neg:
        return "焦虑", 55, "、".join(hit_neg)

    hit_pos = [w for w in POSITIVE_WORDS if w in content]
    if hit_pos:
        return "积极", 15, "、".join(hit_pos)

    return "平稳", 20, "未命中情绪关键词"


def risk_level_of(score: int) -> str:
    if score >= 70:
        return "高"
    if score >= 40:
        return "中"
    return "低"


def evaluate(
    text: str,
    llm_tag: Optional[str] = None,
    llm_score: Optional[int] = None,
) -> Dict[str, Any]:
    """统一情绪评估入口。LLM 结果优先，缺失时关键词兜底。"""
    if llm_score is not None:
        tag = llm_tag or "未知"
        score = int(max(0, min(100, llm_score)))
        basis = "LLM 语义判定"
    else:
        tag, score, basis = evaluate_by_keyword(text)

    return {
        "emotion_tag": tag,
        "emotion_score": score,
        "risk_level": risk_level_of(score),
        "basis": basis,
        "need_alert": score >= 70,
        "need_watch": 40 <= score < 70,
    }
