"""请假事由时间解析（FR-006 兜底规则）。

当 Dify / 前端没有传起止时间时，从「我明天要请假一天，家里有事」这类口语里解析出
起止时间。支持：
- 相对日期：今天 / 明天 / 后天 / 大后天
- 明确日期：2026-11-25、11月25日、11/25
- 只说到日子：25号 / 25日 / 下个月25号 / 这个月25号（跨月、跨年自动顺延）
- 星期：周三 / 这周三 / 下周三 / 星期五 / 下礼拜一
- 时长：半天 / 一天 / 三天 / 两周 / 3 天，支持中文数字
"""

import calendar
import re
from datetime import date, datetime, timedelta
from typing import Optional, Tuple

CN_NUM = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

RELATIVE_DAYS = {"今天": 0, "今日": 0, "明天": 1, "明日": 1, "后天": 2, "大后天": 3}

WEEKDAY = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}


def _make_date(year: int, month: int, day: int) -> date:
    """构造日期，月份溢出顺延到下一年，日溢出则取当月最后一天。"""
    while month > 12:
        month -= 12
        year += 1
    while month < 1:
        month += 12
        year -= 1
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last))


def _day_of_month(day: int, today: date, hint: Optional[str] = None) -> date:
    """把「25号」这种只说了日子的说法，落到具体年月。

    hint: None 自动判断 / "this" 本月 / "next" 下月
    """
    if day > 31:
        return today + timedelta(days=1)

    if hint == "next":
        year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        return _make_date(year, month, day)
    if hint == "this":
        return _make_date(today.year, today.month, day)

    last_of_month = calendar.monthrange(today.year, today.month)[1]
    # 当月的这一天已经过去（或本月没有这一天）→ 顺延到下一月
    if day <= today.day or day > last_of_month:
        year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        return _make_date(year, month, day)
    return _make_date(today.year, today.month, day)


# 单个日期片段（全部用非捕获组，方便在区间正则里复用）
_DATE_TOKEN = (
    r"(?:\d{4}\s*[-/年]\s*\d{1,2}\s*[-/月]\s*\d{1,2}"
    r"|\d{1,2}\s*月\s*\d{1,2}\s*[日号]"
    r"|(?<!\d)\d{1,2}\s*[日号]"
    r"|(?:下个?|这个?|本)?\s*(?:周|星期|礼拜)\s*[一二三四五六日天])"
)
_RANGE_RE = re.compile(
    rf"({_DATE_TOKEN})\s*(?:开始|起)?\s*(?:请假|休假)?\s*"
    rf"(?:到|至|~|～|—{{1,2}}|->)\s*(?:请假|休假)?\s*({_DATE_TOKEN})"
)


def _try_parse_date(text: str, today: Optional[date] = None) -> Optional[date]:
    """解析单个日期片段，解析不出来返回 None（不兜底）。"""
    today = today or date.today()

    for word, offset in RELATIVE_DAYS.items():
        if word in text:
            return today + timedelta(days=offset)

    m = re.search(r"(\d{4})\s*[-/年]\s*(\d{1,2})\s*[-/月]\s*(\d{1,2})", text)
    if m:
        return _make_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    m = re.search(r"(下个?月|下月)\s*(\d{1,2})\s*[日号]", text)
    if m:
        return _day_of_month(int(m.group(2)), today, "next")
    m = re.search(r"(这个?月|本月)\s*(\d{1,2})\s*[日号]", text)
    if m:
        return _day_of_month(int(m.group(2)), today, "this")

    m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = today.year if month >= today.month else today.year + 1
        return _make_date(year, month, day)

    m = re.search(r"(?<!\d)(\d{1,2})\s*[日号]", text)
    if m:
        return _day_of_month(int(m.group(1)), today)

    m = re.search(r"(下个?|这个?|本)?\s*(?:周|星期|礼拜)\s*([一二三四五六日天])", text)
    if m:
        prefix = m.group(1) or ""
        target = WEEKDAY[m.group(2)]
        if prefix.startswith("下"):
            days_ahead = (7 - today.weekday()) + target
        elif prefix.startswith(("这", "本")):
            days_ahead = (target - today.weekday()) % 7
        else:
            days_ahead = (target - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
        return today + timedelta(days=days_ahead)

    m = re.search(r"(?<!\d)(\d{1,2})\s*[/]\s*(\d{1,2})(?!\d)", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            year = today.year if month >= today.month else today.year + 1
            return _make_date(year, month, day)

    return None


def _parse_explicit_range(text: str, today: date) -> Optional[Tuple[date, date]]:
    """处理「25号到27号」「12月20日至12月22日」这类显式区间。"""
    m = _RANGE_RE.search(text)
    if not m:
        return None
    start = _try_parse_date(m.group(1), today)
    end = _try_parse_date(m.group(2), today)
    if not start or not end:
        return None
    if end < start:
        # 结束日早于开始日，按同一个月重新落一次（例如「25号到3号」跨月）
        end = _make_date(start.year, start.month, end.day)
        if end < start:
            year, month = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
            end = _make_date(year, month, end.day)
    return start, end


def _parse_start_date(text: str, today: Optional[date] = None) -> date:
    today = today or date.today()

    # 1) 相对日期（今天/明天/后天）
    for word, offset in RELATIVE_DAYS.items():
        if word in text:
            return today + timedelta(days=offset)

    # 2) 完整日期 2026-11-25 / 2026年11月25日
    m = re.search(r"(\d{4})\s*[-/年]\s*(\d{1,2})\s*[-/月]\s*(\d{1,2})", text)
    if m:
        return _make_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # 3) 下个月25号 / 这个月25号
    m = re.search(r"(下个?月|下月)\s*(\d{1,2})\s*[日号]", text)
    if m:
        return _day_of_month(int(m.group(2)), today, "next")
    m = re.search(r"(这个?月|本月)\s*(\d{1,2})\s*[日号]", text)
    if m:
        return _day_of_month(int(m.group(2)), today, "this")

    # 4) 11月25日 / 11月25号
    m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = today.year if month >= today.month else today.year + 1
        return _make_date(year, month, day)

    # 5) 只说日子：25号 / 25日
    m = re.search(r"(?<!\d)(\d{1,2})\s*[日号]", text)
    if m:
        return _day_of_month(int(m.group(1)), today)

    # 6) 星期：下周三 / 这周三 / 周三 / 星期五 / 下礼拜一
    m = re.search(r"(下个?|这个?|本)?\s*(?:周|星期|礼拜)\s*([一二三四五六日天])", text)
    if m:
        prefix = m.group(1) or ""
        target = WEEKDAY[m.group(2)]
        if prefix.startswith("下"):
            days_ahead = (7 - today.weekday()) + target
        elif prefix.startswith(("这", "本")):
            days_ahead = (target - today.weekday()) % 7
        else:
            days_ahead = (target - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
        return today + timedelta(days=days_ahead)

    # 7) 11/25
    m = re.search(r"(?<!\d)(\d{1,2})\s*[/]\s*(\d{1,2})(?!\d)", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            year = today.year if month >= today.month else today.year + 1
            return _make_date(year, month, day)

    return today + timedelta(days=1)  # 默认明天


def has_time_expression(text: str) -> bool:
    """判断文本里有没有「真说过时间」。

    用途：接口层拦掉「帮我把请假审批通过」这类没有时间的语句 ——
    它们落库后会被兜底成"明天"，变成一条莫名其妙的请假单。
    """
    text = text or ""
    if any(word in text for word in RELATIVE_DAYS):
        return True
    if _RANGE_RE.search(text):
        return True
    if re.search(r"(?:下个?月|这个?月|本月)\s*\d{1,2}\s*[日号]", text):
        return True
    if re.search(r"\d{1,2}\s*月\s*\d{1,2}\s*[日号]", text):
        return True
    if re.search(r"\d{4}\s*[-/年]\s*\d{1,2}", text):
        return True
    if re.search(r"(?<!\d)\d{1,2}\s*[日号]", text):
        return True
    if re.search(r"(?:周|星期|礼拜)\s*[一二三四五六日天]", text):
        return True
    if re.search(r"(?<!\d)\d{1,2}\s*[/]\s*\d{1,2}(?!\d)", text):
        return True
    # 只说时长也算（「请两天假」「请假半天」），否则会被"没有时间"的护栏误拦
    if re.search(r"[0-9一二两三四五六七八九十]+\s*天", text) or "半天" in text or "两周" in text:
        return True
    return False


def _parse_duration_days(text: str) -> float:
    """返回请假天数，支持半天 = 0.5。"""
    if "半天" in text:
        return 0.5

    m = re.search(r"([0-9]+(?:\.[0-9])?)\s*天", text)
    if m:
        return float(m.group(1))

    m = re.search(r"([一二两三四五六七八九十]+)\s*天", text)
    if m:
        raw = m.group(1)
        if raw == "十":
            return 10
        if len(raw) == 1:
            return float(CN_NUM.get(raw, 1))
        if raw.startswith("十") and len(raw) == 2:
            return float(10 + CN_NUM.get(raw[1], 0))
        if len(raw) == 2 and raw[1] == "十":
            return float(CN_NUM.get(raw[0], 1) * 10)
        if len(raw) == 3 and raw[1] == "十":
            return float(CN_NUM.get(raw[0], 1) * 10 + CN_NUM.get(raw[2], 0))

    if "两周" in text or "两星期" in text or "2周" in text:
        return 14.0
    if "一周" in text or "一星期" in text or "1周" in text or "7天" in text:
        return 7.0

    return 1.0  # 未说时长默认一天


def parse_leave_time(reason: str) -> Tuple[str, str]:
    """从事由文本解析起止时间，返回 ('YYYY-MM-DD HH:MM:SS', ...)。"""
    text = reason or ""
    today = date.today()

    # 显式区间优先：「25号到27号」「12月20日至12月22日」
    rng = _parse_explicit_range(text, today)
    if rng:
        start_date, end_date = rng
        start_dt = datetime(start_date.year, start_date.month, start_date.day, 8, 0, 0)
        end_dt = datetime(end_date.year, end_date.month, end_date.day, 18, 0, 0)
        return (
            start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        )

    start_date = _parse_start_date(text)
    duration = _parse_duration_days(text)

    start_dt = datetime(start_date.year, start_date.month, start_date.day, 8, 0, 0)
    if duration == 0.5:
        end_dt = datetime(start_date.year, start_date.month, start_date.day, 12, 0, 0)
    else:
        # 请假 n 天，含起始当天，截止到第 n 天的 18:00
        end_date = start_date + timedelta(days=max(int(duration), 1) - 1)
        end_dt = datetime(end_date.year, end_date.month, end_date.day, 18, 0, 0)

    return (
        start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        end_dt.strftime("%Y-%m-%d %H:%M:%S"),
    )
