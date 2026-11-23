"""画像研判规则引擎：学历/意向归一化 + 项目规则匹配 + 匹配度评分。

对应需求 FR-001 ~ FR-005：
- FR-001 画像抽取（结构化字段优先，raw_text 正则兜底）
- FR-002 学历归一化
- FR-003 意向归一化
- FR-004 规则匹配
- FR-005 匹配度评分与排序

设计原则：纯确定性规则，不依赖 LLM，可独立单元测试；LLM 只负责把原文抽成结构化字段。
"""

import re
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# 项目库（与 course_project 表 seed 保持一致）
# ---------------------------------------------------------------------------

PROJECTS: List[Dict[str, Any]] = [
    {
        "project": "2+2 国际本科直通班",
        "edu_pool": {"初中", "高中", "中职技校"},
        "primary_edu": "初中",
        "rank": 2,
        "age_range": (14, 22),
        "intent": {"升学"},
        "note": "国内 2 年 + 海外 2 年，初中毕业即可起步，最终拿海外本科学位",
    },
    {
        "project": "0.5/1+2 新加坡定向培养本科班",
        "edu_pool": {"高中", "中职技校", "专科"},
        "primary_edu": "高中",
        "rank": 1,
        "age_range": (17, 25),
        "intent": {"升学"},
        "note": "国内 0.5~1 年语言与专业衔接 + 新加坡 2 年本科，周期短、学历可认证",
    },
    {
        "project": "2+2+1 国际本硕连读",
        "edu_pool": {"高中", "中职技校", "专科"},
        "primary_edu": None,
        "rank": 3,
        "age_range": (17, 28),
        "intent": {"升学"},
        "note": "本科 + 硕士一贯制，适合目标明确的升学学员",
    },
    {
        "project": "一年制专升本",
        "edu_pool": {"专科"},
        "primary_edu": "专科",
        "rank": 1,
        "age_range": (18, 40),
        "intent": {"升学", "就业"},
        "note": "专科升本科，一年制快速拿到本科学历",
    },
    {
        "project": "一年制本升硕",
        "edu_pool": {"本科"},
        "primary_edu": "本科",
        "rank": 1,
        "age_range": (20, 45),
        "intent": {"升学"},
        "note": "本科升硕士，一年制，适合快速提升学历",
    },
    {
        "project": "6+6 酒店运营大专就业班",
        "edu_pool": {"中职技校"},
        "primary_edu": "中职技校",
        "rank": 1,
        "age_range": (17, 35),
        "intent": {"就业", "移民"},
        "note": "新加坡 6 个月理论 + 6 个月带薪实习，一年取得大专文凭，100% 推荐就业",
    },
    {
        "project": "9+6 航空运营大专就业班",
        "edu_pool": {"中职技校", "高中"},
        "primary_edu": "中职技校",
        "rank": 2,
        "age_range": (17, 35),
        "intent": {"就业", "移民"},
        "note": "新加坡 9 个月理论 + 6 个月带薪实习，就业薪资 15000 元/月以上",
    },
    {
        "project": "德国双元制职业教育",
        "edu_pool": {"初中", "高中", "中职技校", "专科"},
        "primary_edu": "中职技校",
        "rank": 3,
        "age_range": (18, 35),
        "intent": {"就业", "移民"},
        "note": "企业 + 学校双元培养，需德语基础与动手能力，毕业可直接就业",
    },
]

# ---------------------------------------------------------------------------
# FR-002 / FR-003 归一化
# ---------------------------------------------------------------------------

EDU_KEYWORDS = [
    ("硕士", ["硕士", "研究生", "博士", "master"]),
    ("本科", ["本科", "学士", "大学本科", "bachelor"]),
    ("专科", ["专科", "大专", "高职", "college"]),
    ("中职技校", ["中职", "技校", "职高", "中专", "职业学校", "技师"]),
    ("高中", ["高中", "普高", "高一", "高二", "高三", "高中在读"]),
    ("初中", ["初中", "中考"]),
]

CN_NUM = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def normalize_education(text: Optional[str]) -> Optional[str]:
    """把自然语言学历归一化到标准桶。无法归一时原样返回。"""
    if not text:
        return None
    raw = str(text).strip()
    for bucket, words in EDU_KEYWORDS:
        if any(w in raw for w in words):
            return bucket
    return raw


def normalize_intent(text: Optional[str]) -> Optional[str]:
    """把意向归一化为 升学 / 就业 / 移民。"""
    if not text:
        return None
    raw = str(text)
    if any(w in raw for w in ["移民", "永居", "绿卡", "定居"]):
        return "移民"
    if any(w in raw for w in ["就业", "工作", "打工", "实习", "挣钱", "就业导向"]):
        return "就业"
    if any(w in raw for w in ["升学", "学历", "本科", "硕士", "留学", "深造", "读研", "考大学"]):
        return "升学"
    return None


# ---------------------------------------------------------------------------
# FR-001 画像抽取（正则兜底）
# ---------------------------------------------------------------------------

def extract_profile_from_text(raw_text: str) -> Dict[str, Any]:
    """从非结构化文本中兜底抽取画像字段。仅在调用方未提供结构化字段时使用。"""
    text = raw_text or ""
    profile: Dict[str, Any] = {}

    # 姓名：常见「我叫X」「我是X同学」「X同学」
    m = re.search(r"我(?:叫|是)\s*([\u4e00-\u9fa5]{2,3})(?:同学|学生)?", text)
    if m:
        profile["name"] = m.group(1)
    else:
        m = re.search(r"([\u4e00-\u9fa5]{2,3})同学", text)
        if m:
            profile["name"] = m.group(1)

    # 年龄
    m = re.search(r"(\d{1,2})\s*(?:岁|周岁)", text)
    if m:
        profile["age"] = int(m.group(1))

    # 学历：注意区分「高中毕业」（当前学历）与「想拿本科」（目标学历）。
    # 只认「X 毕业 / X 在读 / X 读完 / X 毕业证」这种当前状态的表述，
    # 不能把「想拿本科学历」里的「本科学历」当成当前学历。
    current_edu = None
    for bucket, words in EDU_KEYWORDS:
        for w in words:
            if re.search(rf"{w}\s*(?:刚)?\s*(?:毕业|在读|读完|毕业证|应届)", text):
                current_edu = bucket
                break
        if current_edu:
            break
    if current_edu:
        profile["education"] = current_edu
    else:
        profile["education"] = normalize_education(text)

    # 意向
    profile["intent"] = normalize_intent(text)

    # 语言基础：德语 / 雅思 / 托福 / 英语
    langs = []
    if "德语" in text:
        langs.append("德语")
    if "雅思" in text or "托福" in text or "英语" in text:
        langs.append("英语")
    if langs:
        profile["language"] = "、".join(langs)

    # 动手能力
    if re.search(r"动手|实操|技术控|喜欢拆|机械|电子|汽修|手工", text):
        profile["hands_on"] = "强"

    # 经济条件（量化到 3 档，供项目池参考，不影响硬规则）
    if re.search(r"预算(?:有限|不高)|经济一般|普通家庭|便宜|性价比", text):
        profile["economy"] = "普通"
    elif re.search(r"预算充足|不差钱|经济条件好", text):
        profile["economy"] = "较好"

    return profile


def build_profile(payload: Dict[str, Any]) -> Dict[str, Any]:
    """合并结构化字段与正则兜底结果。结构化字段优先。"""
    raw_text = payload.get("raw_text") or ""
    fallback = extract_profile_from_text(raw_text)

    profile: Dict[str, Any] = {}
    for key in ["name", "age", "education", "intent", "language", "hands_on", "economy"]:
        value = payload.get(key)
        if value in (None, "", []):
            value = fallback.get(key)
        profile[key] = value

    profile["education"] = normalize_education(profile.get("education"))
    profile["intent"] = normalize_intent(profile.get("intent"))
    return profile


# ---------------------------------------------------------------------------
# FR-004 / FR-005 规则匹配与评分
# ---------------------------------------------------------------------------

def _score_project(project: Dict[str, Any], profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """对单个项目打分。硬条件不满足返回 None（直接排除，不做兜底推荐）。"""
    edu = profile.get("education")
    age = profile.get("age")
    intent = profile.get("intent")
    language = profile.get("language") or ""
    hands_on = profile.get("hands_on") or ""

    reasons: List[str] = []
    score = 65  # 基础分

    # 硬条件 1：学历池
    if edu not in project["edu_pool"]:
        return None
    if edu:
        if project.get("primary_edu") == edu:
            score += 25
            reasons.append(f"学历【{edu}】正是该项目的首选起点")
        else:
            score += 20
            reasons.append(f"学历【{edu}】符合项目起点要求")

    # 硬条件 2：年龄区间（双元制/就业类项目严格执行）
    lo, hi = project["age_range"]
    if isinstance(age, int):
        if not (lo <= age <= hi):
            return None
        reasons.append(f"年龄 {age} 岁在 {lo}-{hi} 岁招生区间内")

    # 硬条件 3：德国双元制必须有德语基础
    if "双元制" in project["project"] and "德语" not in language:
        return None

    # 硬条件 4：双元制/就业类要求动手能力不能是"弱"（需求 FR-004 的三条件是「与」关系）
    if ("双元制" in project["project"] or "就业" in project["project"]) and hands_on == "弱":
        return None

    # 加分：意向匹配
    if intent and intent in project["intent"]:
        if intent == "就业" and ("6+6" in project["project"] or "9+6" in project["project"] or "双元制" in project["project"]):
            score += 5
            reasons.append("就业意向与项目培养方向一致")
        elif intent == "移民" and ("双元制" in project["project"] or "6+6" in project["project"]):
            score += 5
            reasons.append("移民意向可通过项目转工作签路径实现")
        elif intent == "升学" and any(k in project["project"] for k in ["本科", "硕士", "本硕"]):
            score += 3
            reasons.append("升学意向匹配项目的学历产出")

    # 加分：语言基础
    if "德语" in language and "德国" in project["project"]:
        score += 5
        reasons.append("已有德语基础，语言衔接成本低")

    # 加分：动手能力
    if hands_on == "强" and ("双元制" in project["project"] or "就业" in project["project"]):
        score += 5
        reasons.append("动手能力强，适合技能型培养")

    score = max(0, min(100, score))
    return {
        "project": project["project"],
        "reason": "；".join(reasons) + f"。{project['note']}",
        "score": score,
        "rank": project.get("rank", 9),
    }


def recommend(payload: Dict[str, Any]) -> Dict[str, Any]:
    """画像研判主入口，返回 profile / matches / best_match / summary。"""
    profile = build_profile(payload)
    matches: List[Dict[str, Any]] = []

    for project in PROJECTS:
        item = _score_project(project, profile)
        if item:
            matches.append(item)

    # 去重（同项目保留最高分）+ 按匹配度降序，同分时按项目推荐优先级排
    dedup: Dict[str, Dict[str, Any]] = {}
    for item in matches:
        cur = dedup.get(item["project"])
        if not cur or item["score"] > cur["score"]:
            dedup[item["project"]] = item
    matches = sorted(
        dedup.values(), key=lambda x: (-x["score"], x.get("rank", 9))
    )

    best = matches[0] if matches else None

    name = profile.get("name") or "该同学"
    if best:
        summary = (
            f"{name}（{profile.get('education') or '学历待确认'}，"
            f"{profile.get('age') or '年龄待确认'}）最推荐【{best['project']}】，"
            f"匹配度 {best['score']} 分。推荐理由：{best['reason']}"
        )
        # 主推之外再给 1~2 个备选（带分值），让客户有的选；理由取项目简介那段
        runners = matches[1:3]
        if runners:
            alts = "；".join(
                f"备选【{m['project']}】匹配度 {m['score']} 分，{m['reason'].split('。')[-1]}"
                for m in runners
            )
            summary += "另外还有备选：" + alts + "。"
    else:
        summary = (
            f"根据目前的画像信息（学历：{profile.get('education') or '未知'}，"
            f"年龄：{profile.get('age') or '未知'}，意向：{profile.get('intent') or '未知'}），"
            "暂未匹配到合适的留学项目。建议补充学历层次或意向方向后再做研判。"
        )

    return {
        "profile": profile,
        "matches": matches,
        "best_match": best,
        "summary": summary,
    }
