"""Dify 三个应用的接入配置（服务 API）

本文件是前端 -> 后端 -> Dify 的唯一配置入口。
修改 Dify 应用或重新生成密钥后，只需改这里的 api_key。
"""

import os

# Dify 服务 API 地址（nginx 反代到 api 容器）
DIFY_API_BASE = os.environ.get("DIFY_API_BASE", "http://localhost/v1")
DIFY_TIMEOUT = float(os.environ.get("DIFY_TIMEOUT", "120"))

AGENTS = {
    "student": {
        "app_id": "638eb8a4-447e-4f28-b8a6-9c6b70a0f485",
        "api_key": "app-F106WVn0qNAmWhK1O0mKkio3",
        "name": "小粤同学",
        "icon": "🎓",
        "tagline": "留学生事务 · 请假 · 成绩 · 情绪 · 售后",
        "accent": "#0f766e",
        "name_var": "student_name",
        "users": [
            {"id": 1, "name": "张三", "label": "张三 · stu001 · 2025 级 · 新加坡"},
            {"id": 2, "name": "许明", "label": "许明 · stu002 · 2024 级 · 新加坡"},
            {"id": 5, "name": "陈嘉怡", "label": "陈嘉怡 · stu003 · 2025 级 · 专升本"},
            {"id": 6, "name": "刘一鸣", "label": "刘一鸣 · stu004 · 2025 级 · 德国"},
            {"id": 7, "name": "周雨桐", "label": "周雨桐 · stu005 · 2024 级 · 中德共建"},
            {"id": 8, "name": "吴天成", "label": "吴天成 · stu006 · 2023 级 · 本硕连读"},
            {"id": 12, "name": "何雨", "label": "何雨 · stu007 · 2025 级 · 港澳"},
            {"id": 16, "name": "林晓", "label": "林晓 · stu008 · 2025 级 · 香港"},
            {"id": 17, "name": "高远", "label": "高远 · stu009 · 2025 级 · 澳洲"},
        ],
        "welcome": "我是小粤同学，负责你的留学事务：请假、成绩、售后都能办，也可以聊聊最近的烦心事。",
        "prompts": [
            "我明天要请假一天，家里有事",
            "帮我查一下我的请假记录",
            "我上学期成绩怎么样",
            "最近压力好大，感觉有点撑不住",
            "课程内容和当初介绍的不一样，我想投诉",
            "新加坡本科的申请条件是什么",
        ],
    },
    "employee": {
        "app_id": "c4b69cae-f343-4260-9d38-383149c43d8f",
        "api_key": "app-aY0xcCsM8hVQWZShfVV9UHhj",
        "name": "小粤同学",
        "icon": "💼",
        "tagline": "员工业务 · CRM · 线索 · 日报 · 成绩",
        "accent": "#0f766e",
        "name_var": "employee_name",
        "users": [
            {"id": 3, "name": "李老师", "label": "李老师 · emp001 · 咨询一组（班主任）"},
            {"id": 9, "name": "赵老师", "label": "赵老师 · emp003 · 咨询二组（班主任）"},
            {"id": 10, "name": "孙老师", "label": "孙老师 · emp004 · 教务（班主任）"},
            {"id": 13, "name": "陈顾问", "label": "陈顾问 · emp006 · 咨询三组（顾问）"},
            {"id": 18, "name": "吴顾问", "label": "吴顾问 · emp007 · 咨询四组（顾问）"},
            {"id": 19, "name": "何顾问", "label": "何顾问 · emp008 · 咨询五组（顾问）"},
            {"id": 4, "name": "王主任", "label": "王主任 · admin · 教学管理部（管理员）"},
        ],
        "welcome": "我是小粤同学，负责员工业务：查客户跟进、录入线索、更新状态、写日报和录成绩。",
        "prompts": [
            "帮我查一下许同学的跟进记录",
            "新录入一个客户，叫陈晨，19岁，家长电话 13800138000，意向德国双元制",
            "把许明的状态改成已签约",
            "还有哪些学生请假待我审批",
            "帮我写今天的日报：跟进了5个客户，签约1个",
            "给张三录入Python课程成绩92分",
            "新员工入职要准备哪些材料",
        ],
    },
    "customer": {
        "app_id": "6d7af072-af9e-400c-b59d-6078455ba1f0",
        "api_key": "app-qjuGCcWnvgy7I2Al1NYvQH2e",
        "name": "小粤同学",
        "icon": "🤝",
        "tagline": "客服与活动 · 项目推荐 · 活动报名 · 政策",
        "accent": "#0f766e",
        "name_var": "customer_name",
        "users": [
            {"id": 14, "name": "陈女士", "label": "陈女士 · parent001 · 张三家长"},
            {"id": 15, "name": "林先生", "label": "林先生 · parent002 · 许明家长"},
        ],
        "welcome": "我是小粤同学，告诉我学员的年龄、学历和想法，我帮你匹配合适的项目，也能查活动、帮报名。",
        "prompts": [
            "我家孩子19岁、高中刚毕业、想快点拿本科学历",
            "德国双元制项目是什么，适合什么样的人",
            "最近有什么线下活动",
            "我要报名新加坡留学分享会",
            "你们的公司背景和师资怎么样",
        ],
    },
}
