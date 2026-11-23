"""演示种子数据（全量重建，跑一次就得到固定的初始状态）。

用法：
    python seed.py            # 清空演示表后重新写入
    python seed.py --keep     # 只在表为空时补数据，不清空

说明：只用于演示与验收，数据库结构与 schema.sql 完全一致。
所有记录都用显式 id，方便活动和线索被其它表稳定引用。
"""

import hashlib
import sqlite3
import sys
from datetime import date, timedelta

from config import DB_PATH

DEMO_TABLES = [
    "activity_signup",
    "activity",
    "event_registration",
    "student_feedback_ticket",
    "student_psych_journal",
    "student_psych_alert",
    "student_psych_profile",
    "student_admin_service",
    "student_score",
    "employee_daily_report",
    "crm_lead",
    "event_lecture",
    "course_project",
    "conversation_log",
    "school_class",
    "sys_user",
]


def _hash(pwd: str) -> str:
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()


def _d(offset_days: int) -> str:
    return (date.today() + timedelta(days=offset_days)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# 用户：1 名管理员 + 3 名班主任 + 9 名学员 + 3 名顾问 + 2 名家长
#
# 同身份多账号是为了验证「不越权」：
#   李老师(3)  → 张三(1)、许明(2)、林晓(16)        · 新加坡 / 香港方向
#   赵老师(9)  → 刘一鸣(6)、周雨桐(7)、吴天成(8)   · 德国 / 中德方向
#   孙老师(10) → 陈嘉怡(5)、何雨(12)、高远(17)     · 专升本 / 港澳方向
#   顾问：陈顾问(13)、吴顾问(18)、何顾问(19) 各带自己的线索
# 学生记录里的 homeroom_teacher_id 决定「请假找谁批、成绩谁能录」，
# 这是全系统隔离的唯一依据，改这里就等于改权限。
# 密码统一 123456。
# ---------------------------------------------------------------------------
USERS = [
    # id, username, real_name, user_type, employee_role, department, contact, homeroom, parent_of
    (1, "stu001", "张三", "STUDENT", None, "国际学院 2025 级 · 新加坡方向", "13800000001", 3, None),
    (2, "stu002", "许明", "STUDENT", None, "国际学院 2024 级 · 新加坡方向", "13800000002", 3, None),
    (3, "emp001", "李老师", "EMPLOYEE", "普通员工", "留学事业部 · 咨询一组（新加坡方向）", "13900000001", None, None),
    (4, "admin", "王主任", "EMPLOYEE", "管理员", "教学管理部 · 主任", "13900000002", None, None),
    (5, "stu003", "陈嘉怡", "STUDENT", None, "国际学院 2025 级 · 专升本", "13700000003", 10, None),
    (6, "stu004", "刘一鸣", "STUDENT", None, "国际学院 2025 级 · 德国方向", "13600000004", 9, None),
    (7, "stu005", "周雨桐", "STUDENT", None, "国际学院 2024 级 · 中德共建", "13500000005", 9, None),
    (8, "stu006", "吴天成", "STUDENT", None, "国际学院 2023 级 · 本硕连读", "13500000006", 9, None),
    (9, "emp003", "赵老师", "EMPLOYEE", "普通员工", "留学事业部 · 咨询二组（德国方向）", "13900000003", None, None),
    (10, "emp004", "孙老师", "EMPLOYEE", "普通员工", "教学管理部 · 教务（专升本方向）", "13900000004", None, None),
    (12, "stu007", "何雨", "STUDENT", None, "国际学院 2025 级 · 港澳方向", "13500000007", 10, None),
    (13, "emp006", "陈顾问", "EMPLOYEE", "普通员工", "留学事业部 · 咨询三组", "13900000006", None, None),
    (14, "parent001", "陈女士", "PARENT", None, "家长 · 张三母亲", "13800000011", None, 1),
    (15, "parent002", "林先生", "PARENT", None, "家长 · 许明父亲", "13800000012", None, 2),
    (16, "stu008", "林晓", "STUDENT", None, "国际学院 2025 级 · 香港方向", "13500000008", 3, None),
    (17, "stu009", "高远", "STUDENT", None, "国际学院 2025 级 · 澳洲方向", "13500000009", 10, None),
    (18, "emp007", "吴顾问", "EMPLOYEE", "普通员工", "留学事业部 · 咨询四组", "13900000007", None, None),
    (19, "emp008", "何顾问", "EMPLOYEE", "普通员工", "留学事业部 · 咨询五组", "13900000008", None, None),
    # 活动项目老师：不讲某一方向的课，负责试听课 / 项目介绍，把有联系方式的意向学员拢在试听班
    (20, "emp009", "张老师", "EMPLOYEE", "活动项目老师", "市场活动部 · 试听与项目介绍", "13900000009", None, None),
]

# ---------------------------------------------------------------------------
# 班级：一个班 ↔ 一位班主任，学员挂在班上（sys_user.class_id）
# 学员的 homeroom_teacher_id 与班的 teacher_id 保持一致，
# 请假审批 / 成绩录入 / 越权判断仍然只看 homeroom_teacher_id。
# ---------------------------------------------------------------------------
CLASSES = [
    # id, name, grade, teacher_id, note, kind
    (1, "粤教1班", "2025 级", 3, "新加坡 / 香港方向", "常规班"),
    (2, "粤教2班", "2025 级", 9, "德国 / 中德方向", "常规班"),
    (3, "粤教3班", "2025 级", 10, "专升本 / 港澳方向", "常规班"),
    # 试听班：成员不是正式学员，而是有联系方式、未流失的意向学员（见下方 crm_lead 挂班）
    (4, "粤教试听班", "活动班", 20, "活动项目老师带班：试听课 / 项目介绍", "试听班"),
]

# ---------------------------------------------------------------------------
# 项目：与 profile_match_engine 的 8 条规则一一对应
# ---------------------------------------------------------------------------
PROJECTS = [
    ("2+2 国际本科直通班", "国际本科", "国内 2 年 + 海外 2 年，初中毕业即可起步，最终取得海外本科学位。", "初中/高中毕业生，14-22 岁"),
    ("0.5/1+2 新加坡定向培养本科班", "新加坡定向", "国内 0.5~1 年语言与专业衔接 + 新加坡 2 年本科，周期短、学历可认证。", "高中/中职/专科毕业生，17-25 岁"),
    ("2+2+1 国际本硕连读", "本硕连读", "本科 + 硕士一贯制培养，适合目标明确的升学学员。", "高中/中职/专科毕业生，17-28 岁"),
    ("一年制专升本", "专升本", "专科升本科，一年制快速取得本科学历。", "专科毕业生，18-40 岁"),
    ("一年制本升硕", "本升硕", "本科升硕士，一年制，适合快速提升学历。", "本科毕业生，20-45 岁"),
    ("6+6 酒店运营大专就业班", "新加坡就业", "新加坡一带一路工学交替：6 个月理论 + 6 个月带薪实习（实习薪资 6000-8000 元/月），一年取得大专文凭，100% 推荐就业。", "职高/中专/中职/技校，满 17 岁，无语言要求"),
    ("9+6 航空运营大专就业班", "新加坡就业", "新加坡大专文凭课程：9 个月理论 + 6 个月带薪实习，就业薪资 15000 元/月以上。", "职高/中专/中职/技校，满 17 岁，无语言要求"),
    ("德国双元制职业教育", "德国双元制", "企业 + 学校双元培养，需德语基础与动手能力，毕业可直接就业。", "18-35 岁，有德语基础"),
]

# ---------------------------------------------------------------------------
# 活动：6 场（含 1 场已满、1 场已结束）
# ---------------------------------------------------------------------------
EVENTS = [
    # id, name, type, offset_days, hour, location, max, current
    (1, "新加坡留学分享会", "线下", 3, 19, "广州天河校区 A302", 30, 18),
    (2, "德国双元制项目说明会", "线上", 5, 20, "腾讯会议 825-113-007", 20, 20),
    (3, "香港升学规划沙龙", "线下", 9, 14, "深圳福田校区 B101", 25, 11),
    (4, "新加坡公立大学申请解析", "线上", 12, 19, "腾讯会议 640-882-119", 100, 47),
    (5, "中德共建项目家长见面会", "线下", 16, 10, "广州天河校区报告厅", 40, 22),
    (6, "马来西亚留学专场（往期）", "线下", -7, 15, "广州天河校区 A201", 30, 30),
]

# ---------------------------------------------------------------------------
# 顾问设计的活动：讲什么、谁来讲、什么时候、多少名额
# 第二场刻意报满（20/20），用于演示「该活动已满，推荐去别的活动」
# ---------------------------------------------------------------------------
ACTIVITIES = [
    # title, category, description, speaker, offset_days, hour, location, capacity, created_by
    ("新加坡留学分享会", "线下分享会",
     "2026 秋季新加坡方向：院校选择、专业匹配、住宿与费用一次讲清，现场可一对一问。",
     "李老师", 3, 19, "广州天河校区 A302", 30, 13),
    # 说明会 / 试听课讲的是「项目本身」，由活动项目老师张老师讲；方向深度分享仍由该方向班主任讲
    ("德国双元制项目说明会", "线上说明会",
     "双元制怎么读、企业带薪怎么算、德语要到什么水平；适合中职 / 高中毕业想尽快就业的家庭。",
     "张老师", 5, 20, "腾讯会议 825-113-007", 20, 18),
    ("香港升学规划沙龙", "线下沙龙",
     "港校本科 / 副学士路径对比，DSE 与高考成绩如何换算，家长最关心的身份与就业问题。",
     "孙老师", 9, 14, "深圳福田校区 B101", 25, 19),
    ("德语试听课（双元制方向 · 小班）", "试听课",
     "45 分钟真实课堂：德语发音 + 双元制企业面试模拟，家长可在后排旁听，课后一对一给方案。",
     "张老师", 2, 19, "广州天河校区 A302", 12, 18),
]

_FULL_NAMES = [
    "王丽", "李强", "张敏", "刘洋", "陈静", "杨帆", "黄磊", "周婷", "吴昊", "徐倩",
    "孙浩", "马晓", "朱琳", "胡军", "郭婷", "何伟", "高雅", "罗静", "梁宇", "宋佳",
]

SIGNUPS = (
    [
        # activity_id, name, phone, remark
        (1, "陈女士", "13800000011", "想了解新加坡本科，孩子高三"),
        (1, "林先生", "13800000012", "已加微信，想带材料过来"),
        (1, "黄伟", "13400000008", "汽修厂工作，考虑出国就业"),
        (3, "梁诗敏", "13400000009", "一年制升硕，关注学历认证"),
    ]
    + [(2, n, f"139{10000000 + i}", "线上说明会报名") for i, n in enumerate(_FULL_NAMES)]
)

# ---------------------------------------------------------------------------
# 成绩：5 名学生，跨两个学期
# ---------------------------------------------------------------------------
SCORES = [
    # student_id, course, score, semester
    (16, "学术英语", 84.0, "2025-2026 第一学期"),
    (16, "香港升学导论", 79.0, "2025-2026 第一学期"),
    (17, "学术英语", 71.5, "2025-2026 第一学期"),
    (17, "澳洲文化概况", 66.0, "2025-2026 第一学期"),
    (1, "学术英语", 88.0, "2025-2026 第一学期"),
    (1, "高等数学", 76.5, "2025-2026 第一学期"),
    (1, "程序设计基础", 92.0, "2025-2026 第一学期"),
    (1, "跨文化沟通", 84.0, "2025-2026 第一学期"),
    (1, "学术写作", 79.5, "2025-2026 第二学期"),
    (1, "雅思听力", 6.5, "2025-2026 第二学期"),
    (1, "雅思口语", 6.0, "2025-2026 第二学期"),
    (2, "学术英语", 81.0, "2024-2025 第二学期"),
    (2, "微观经济学", 74.0, "2024-2025 第二学期"),
    (2, "统计学基础", 68.5, "2024-2025 第二学期"),
    (2, "商务沟通", 86.0, "2024-2025 第二学期"),
    (2, "商务统计", 55.0, "2024-2025 第二学期"),
    (5, "英语听说", 91.0, "2025-2026 第一学期"),
    (5, "管理学原理", 83.5, "2025-2026 第一学期"),
    (5, "计算机应用", 88.0, "2025-2026 第一学期"),
    (6, "德语基础 A1", 72.0, "2025-2026 第一学期"),
    (6, "机械制图", 85.0, "2025-2026 第一学期"),
    (6, "电工基础", 78.5, "2025-2026 第一学期"),
    (7, "德语基础 A2", 80.0, "2025-2026 第一学期"),
    (7, "自动化概论", 76.0, "2025-2026 第一学期"),
    (7, "数学", 69.0, "2025-2026 第一学期"),
    (8, "雅思综合", 6.5, "2024-2025 第二学期"),
    (8, "国际商务", 82.0, "2024-2025 第二学期"),
    (8, "研究方法", 87.5, "2024-2025 第二学期"),
]

# ---------------------------------------------------------------------------
# 客户线索：10 条，四种状态都有
# ---------------------------------------------------------------------------
LEADS = [
    # name, contact, background, history, status, owner
    ("许明轩", "13800000002", "19 岁，高中刚毕业，家长陪同咨询，意向新加坡本科",
     "2026-11-10 电话沟通，已加微信；2026-11-14 到访校区", "跟进中", 13),
    ("陈嘉怡", "13700000003", "22 岁，大专毕业，想快速拿本科学历",
     "2026-11-12 线上咨询专升本项目", "新增意向", 13),
    ("刘一鸣", "13600000004", "17 岁，中职机电专业，德语零基础，家庭希望尽快就业",
     "2026-11-08 展会留资", "新增意向", 13),
    ("黄伟", "13400000008", "20 岁，高中毕业两年，在汽修厂工作，想出国就业",
     "2026-11-02 抖音私信；11-05 电话沟通德国双元制", "跟进中", 18),
    ("梁诗敏", "13400000009", "24 岁，本科毕业，想一年制升硕，家长关注学历认证",
     "2026-11-01 官网表单留资；11-06 到访，意向新加坡", "跟进中", 18),
    ("郑浩然", "13400000010", "18 岁，高三在读，成绩中等，考虑 2+2 国际本科",
     "2026-10-28 学校宣讲会留资；11-03 家长电话咨询", "跟进中", 18),
    ("苏婉", "13400000011", "21 岁，专科在读大三，计划专升本后出国",
     "2026-10-20 线上咨询；11-10 已签约一年制专升本", "已签约", 19),
    ("冯子豪", "13400000012", "19 岁，中职毕业，家长希望先工作再考虑",
     "2026-10-15 展会留资；11-02 回访明确暂缓", "已流失", 19),
    ("罗嘉", "13400000013", "17 岁，高二，家长咨询香港升学",
     "2026-11-15 到访深圳校区，意向香港", "新增意向", 19),
    ("唐晓", "13400000014", "23 岁，大专毕业，预算有限，关注马来西亚项目",
     "2026-11-16 电话沟通，待发送项目资料", "新增意向", 19),
]

# ---------------------------------------------------------------------------
# 请假：7 条，覆盖待审批 / 已通过 / 已驳回 与不同日期
# ---------------------------------------------------------------------------
LEAVES = [
    # student_id, start_offset, end_offset, reason, status, approver, comment
    (16, 3, 3, "香港院校面试，需请假一天", "待审批", 3, None),
    (17, 5, 6, "办理澳洲签证材料", "待审批", 10, None),
    (1, -12, -12, "参加雅思考试", "已通过", 3, "考试加油，回来把准考证复印件交给教务。"),
    (1, -5, -4, "发烧就医，附医院证明", "已通过", 3, ""),
    (2, -20, -18, "家中有事需回老家", "已通过", 3, "已备案，返校后到教务销假。"),
    (2, 7, 7, "学校体检", "待审批", 3, None),
    (5, -8, -8, "专科毕业手续办理", "已驳回", 10, "当天有专升本衔接课，建议改到周末或线上办理。"),
    (5, 2, 3, "参加专升本目标院校面试", "待审批", 10, None),
    (6, 2, 2, "德语等级考试报名现场确认", "待审批", 9, None),
    (7, 4, 5, "随家长参加中德项目面签", "待审批", 9, None),
    (8, -30, -28, "家长陪同回国办理材料", "已通过", 9, ""),
    (12, 6, 6, "港澳方向院校面试", "待审批", 10, None),
]

# ---------------------------------------------------------------------------
# 学生反馈：5 条，待处理 / 处理中 / 已解决都有，且分属三位班主任
# ---------------------------------------------------------------------------
TICKETS = [
    # student_id, category, content, detail, status, solution, notified
    (1, "报修设施", "宿舍空调不制冷，报修三天无人处理", "A302 宿舍空调 11 月 14 日起不制冷，已报修两次", "处理中", None, 1),
    (2, "课程教学", "课程安排与宣传不符", "报名时承诺每周 20 课时，实际只有 12 课时", "待处理", None, 0),
    (6, "住宿生活", "住宿押金退还延迟", "9 月退宿，押金承诺 30 天内退还，至今未到账", "待处理", None, 0),
    (5, "教务流程", "教材重复收费", "同一本教材在两个学期各收了一次费用", "已解决", "已退还重复收取的 180 元教材费", 1),
    (16, "老师沟通", "希望口语课多安排一对一练习", "现在一周只有一次一对一，想加两次，费用怎么算？", "已解决",
     "已和教务确认：每周加一次一对一，按 200 元/次结算，本月起执行", 1),
]

# ---------------------------------------------------------------------------
# 学生心理周记：4 条，待跟进 / 跟进中 / 已跟进都有
# 分值都低于 70，不会额外触发预警（预警演示数据见 ALERTS）
# ---------------------------------------------------------------------------
JOURNALS = [
    # student_id, tag, score, sleep, source, duration, content, status, handler_id, reply, days_ago
    (1, "平静", 45, "一般", "学业", "今天",
     "这周开始有点静不下心，晚上睡得还行，先把作业赶完再说。", "待跟进", None, None, 1),
    (16, "平静", 32, "良好", "人际", "今天",
     "和朋友聊开了，心情比前两天好，想继续按计划准备口语考试。", "已跟进", 3,
     "挺好的，保持这个节奏；口语加练的事按之前说的执行。", 2),
    (6, "疲惫", 65, "一般", "学业", "几天",
     "连着几天觉得累，德语单词记不住，担心跟不上同班同学。", "待跟进", None, None, 1),
    (5, "低落", 58, "较差", "家庭", "一两周",
     "家里最近事情多，晚上经常想心事，白天上课注意力不太集中。", "跟进中", 10,
     "已经和她聊过一次，约好下周三再细聊，先观察睡眠。", 4),
]

# ---------------------------------------------------------------------------
# 日报：6 条
# ---------------------------------------------------------------------------
REPORTS = [
    (3, -1, "上午电话跟进许明家长，确认 11 月底到访；下午整理新加坡项目资料，接待到访客户 2 组。"),
    (3, -2, "跟进郑浩然家长，对比 2+2 与新加坡定向两个方案；整理本周线索 12 条，其中有效 8 条。"),
    (9, -1, "接待梁诗敏到访，确认本升硕方向；电话回访黄伟，德国双元制材料已发。"),
    (9, -3, "深圳校区香港沙龙邀约 15 人，确认到场 9 人；更新 CRM 中 6 条线索状态。"),
    (10, -1, "核对本学期成绩录入，缺 3 名学生学术写作成绩；处理请假审批 5 条。"),
    (4, -1, "审阅三组咨询数据，签约率 18.6%；安排下周德国项目说明会分工；核对全校待批请假。"),
]

# ---------------------------------------------------------------------------
# 活动报名：6 条
# ---------------------------------------------------------------------------
REGISTRATIONS = [
    # event_id, customer_id, status
    (1, 1, "已报名"),
    (1, 2, "已报名"),
    (2, 3, "已报名"),
    (3, 4, "已报名"),
    (5, 7, "已报名"),
    (6, 8, "已签到"),
]


def rebuild(verbose: bool = True) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    for table in DEMO_TABLES:
        cur.execute(f"DELETE FROM {table}")
    cur.execute("DELETE FROM sqlite_sequence WHERE name IN (%s)" % ",".join("?" * len(DEMO_TABLES)),
                DEMO_TABLES)

    cur.executemany(
        """INSERT INTO sys_user
           (id, username, password_hash, real_name, user_type, employee_role, department,
            contact_info, homeroom_teacher_id, parent_of_student_id, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '正常')""",
        [(i, u, _hash("123456"), n, t, r, d, c, h, p) for i, u, n, t, r, d, c, h, p in USERS],
    )

    # 学员的「开户顾问」：顾问登录后只在自己开的学员里管理账户
    for consultant_id, student_ids in ((13, (1, 2, 16)), (18, (6, 7, 8)), (19, (5, 12, 17))):
        cur.execute(
            "UPDATE sys_user SET created_by = ? WHERE id IN (%s)"
            % ",".join("?" * len(student_ids)),
            (consultant_id, *student_ids),
        )

    # 班级：先建班，再把学员按班主任挂到对应的班上
    cur.executemany(
        "INSERT INTO school_class (id, name, grade, teacher_id, note, kind, create_time, update_time) "
        "VALUES (?, ?, ?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))",
        CLASSES,
    )
    cur.execute(
        "UPDATE sys_user SET class_id = ("
        "  SELECT id FROM school_class WHERE teacher_id = sys_user.homeroom_teacher_id"
        ") WHERE user_type = 'STUDENT'"
    )

    cur.executemany(
        "INSERT INTO course_project (id, project_name, category, description, target_audience) VALUES (?,?,?,?,?)",
        [(i, *p) for i, p in enumerate(PROJECTS, start=1)],
    )

    cur.executemany(
        """INSERT INTO event_lecture
           (id, event_name, event_type, start_time, location, max_participants, current_participants)
           VALUES (?,?,?,?,?,?,?)""",
        [(i, n, t, f"{_d(off)} {hour:02d}:00:00", loc, mx, cur_n)
         for i, n, t, off, hour, loc, mx, cur_n in EVENTS],
    )

    cur.executemany(
        "INSERT INTO student_score (student_id, course_name, score, semester) VALUES (?,?,?,?)",
        SCORES,
    )

    # 一条待处理的预警：用于演示「认领 / 解除」，否则预警表永远是空的
    cur.execute(
        "INSERT INTO student_psych_alert (student_id, risk_level, status, trigger_reason) "
        "VALUES (?, ?, ?, ?)",
        (2, "中", "未处理", "连续两周提到失眠、不想上课，同宿舍同学反映他最近很少参加活动"),
    )

    cur.executemany(
        """INSERT INTO crm_lead
           (customer_name, contact_info, background_info, follow_up_history, status, owner_employee_id)
           VALUES (?,?,?,?,?,?)""",
        LEADS,
    )

    # 试听班名单：有联系方式、且不是「已流失」的线索进班（已丢失的客户学生不纳入）
    cur.execute(
        "UPDATE crm_lead SET class_id = (SELECT id FROM school_class WHERE kind = '试听班' LIMIT 1) "
        "WHERE TRIM(COALESCE(contact_info,'')) <> '' AND COALESCE(status,'新增意向') <> '已流失'"
    )

    cur.executemany(
        """INSERT INTO student_admin_service
           (student_id, service_type, start_time, end_time, reason, status, approver_id,
            approve_time, approve_comment, create_time, update_time)
           VALUES (?, '请假', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                sid,
                f"{_d(s)} 08:00:00",
                f"{_d(e)} 18:00:00",
                reason,
                status,
                appr,
                # 已处理的单子补一个审批时间（开始前一天上午），待审批留空
                None if status == "待审批" else f"{_d(s - 1)} 09:30:00",
                comment,
                f"{_d(s - 2)} 20:15:00",
                f"{_d(s - 2)} 20:15:00" if status == "待审批" else f"{_d(s - 1)} 09:30:00",
            )
            for sid, s, e, reason, status, appr, comment in LEAVES
        ],
    )

    cur.executemany(
        """INSERT INTO student_feedback_ticket
           (student_id, category, content, detail, status, solution, is_notified)
           VALUES (?,?,?,?,?,?,?)""",
        TICKETS,
    )

    cur.executemany(
        """INSERT INTO student_psych_journal
           (student_id, mood_tag, mood_score, sleep, stress_source, duration, content,
            status, handler_id, handle_note, handle_time, create_time, update_time)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [
            (sid, tag, score, sleep, source, dur, content, status, handler, reply,
             None if not reply else f"{_d(off)} 10:00:00",
             f"{_d(off + 1)} 20:00:00", f"{_d(off)} 10:00:00")
            for sid, tag, score, sleep, source, dur, content, status, handler, reply, off in JOURNALS
        ],
    )

    cur.executemany(
        "INSERT INTO employee_daily_report (employee_id, report_date, content) VALUES (?,?,?)",
        [(eid, _d(off), content) for eid, off, content in REPORTS],
    )

    cur.executemany(
        "INSERT INTO event_registration (event_id, customer_id, status) VALUES (?,?,?)",
        REGISTRATIONS,
    )

    cur.executemany(
        """INSERT INTO activity
           (id, title, category, description, speaker, start_time, end_time, location,
            capacity, status, created_by, create_time)
           VALUES (?,?,?,?,?,?,?,?,?, '开放报名', ?, ?)""",
        [
            (i, title, cat, desc, spk, f"{_d(off)} {hour:02d}:00:00",
             f"{_d(off)} {hour + 2:02d}:00:00", loc, cap, owner, f"{_d(-2)} 10:00:00")
            for i, (title, cat, desc, spk, off, hour, loc, cap, owner)
            in enumerate(ACTIVITIES, start=1)
        ],
    )

    cur.executemany(
        """INSERT INTO activity_signup
           (activity_id, name, phone, remark, status, create_time)
           VALUES (?,?,?,?, '已报名', ?)""",
        [(aid, n, p, r, f"{_d(-1)} 15:30:00") for aid, n, p, r in SIGNUPS],
    )

    conn.commit()

    if verbose:
        print("演示数据已重建：")
        for table in ["sys_user", "course_project", "event_lecture", "student_score",
                      "crm_lead", "student_admin_service", "student_feedback_ticket",
                      "employee_daily_report", "event_registration",
         "activity", "activity_signup"]:
            n = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:26} {n}")

    conn.close()


def seed_if_empty() -> None:
    """只在库为空时补数据（保留现有记录）。"""
    conn = sqlite3.connect(DB_PATH)
    n = conn.execute("SELECT COUNT(*) FROM sys_user").fetchone()[0]
    conn.close()
    if n:
        print("库中已有用户数据，未改动。需要重置请直接运行 python seed.py")
        return
    rebuild()


if __name__ == "__main__":
    if "--keep" in sys.argv:
        seed_if_empty()
    else:
        rebuild()
