-- =====================================================================
-- 粤教服务 · 多智能体系统 数据库结构
-- 共 12 张表：sys_user + 学生侧4张 + 员工侧3张 + 客服侧3张 + conversation_log
-- 严格对齐《sql设计草稿.txt》，补充 conversation_log（对话记录表）
-- =====================================================================

-- 统一用户表
CREATE TABLE IF NOT EXISTS sys_user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,               -- 用户名/登录账号
    password_hash TEXT NOT NULL,          -- 加密后的密码
    real_name TEXT NOT NULL,              -- 真实姓名
    user_type TEXT NOT NULL,              -- 用户大类（STUDENT 学生 / EMPLOYEE 员工 / PARENT 家长）
    employee_role TEXT,                   -- 员工角色（仅当 user_type='EMPLOYEE' 时有效：普通员工/领导/管理员）
    department TEXT,                      -- 所属部门/院系
    homeroom_teacher_id INTEGER,          -- 班主任ID（仅学生有效，指向 sys_user 里的员工）
    class_id INTEGER,                     -- 所在班级（仅学生有效，指向 school_class）
    parent_of_student_id INTEGER,         -- 家长对应的学生ID（仅 user_type='PARENT' 时有效）
    contact_info TEXT,                    -- 联系方式（手机号/邮箱）
    status TEXT DEFAULT '正常',            -- 账号状态（正常/停用/已删除）
    created_by INTEGER,                   -- 开户人ID（顾问开的学员，只有他能看到）
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 班级表（班级 ↔ 班主任 一一对应）
-- 学员的 sys_user.class_id 指向这里；sys_user.homeroom_teacher_id 始终等于
-- 该班的 teacher_id，请假审批 / 成绩录入 / 越权判断仍然只看 homeroom_teacher_id。
CREATE TABLE IF NOT EXISTS school_class (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                   -- 班级名称（如 粤教1班）
    grade TEXT,                           -- 届别 / 年级（如 2025 级）
    kind TEXT DEFAULT '常规班',            -- 常规班（正式学员）/ 试听班（活动项目老师带的意向学员）
    teacher_id INTEGER,                   -- 班主任ID（一个班只有一位）
    note TEXT,
    created_by INTEGER,                   -- 建班人（顾问）
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_school_class_name ON school_class(name);
CREATE INDEX IF NOT EXISTS idx_school_class_teacher ON school_class(teacher_id);

-- =====================================================================
-- 留学生智能管家 Agent 相关表
-- =====================================================================

-- 学生行政服务表（请假、考务等申请）
CREATE TABLE IF NOT EXISTS student_admin_service (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,          -- 学生ID
    service_type TEXT NOT NULL,           -- 服务类型（请假/考务查询）
    start_time DATETIME,                  -- 开始时间（请假用）
    end_time DATETIME,                    -- 结束时间（请假用）
    reason TEXT,                          -- 申请事由
    status TEXT DEFAULT '待审批',          -- 审批状态（待审批/已通过/已驳回）
    approver_id INTEGER,                  -- 审批人/班主任ID
    approve_time DATETIME,                -- 审批完成时间（为空表示还没批）
    approve_comment TEXT,                 -- 审批意见
    related_academic_id INTEGER,          -- 关联教务数据ID（DDL/考试ID）
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 心理健康画像表
CREATE TABLE IF NOT EXISTS student_psych_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL UNIQUE,   -- 学生ID（唯一）
    latest_emotion_tag TEXT,              -- 最新情绪标签（焦虑/平稳等）
    emotion_score INTEGER,                -- 情绪分值（0-100）
    last_interaction_time DATETIME,       -- 最近一次交互时间
    emotion_history TEXT,                 -- 历史情绪波动（JSON字符串）
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 心理预警表
CREATE TABLE IF NOT EXISTS student_psych_alert (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    trigger_reason TEXT NOT NULL,         -- 触发原因（AI提取的关键词/原句）
    risk_level TEXT NOT NULL,             -- 风险等级（高/中/低）
    status TEXT DEFAULT '未处理',          -- 处理状态（未处理/跟进中/已处理）
    teacher_id INTEGER,                   -- 负责跟进的老师ID
    handler_id INTEGER,                   -- 实际处理人（班主任）
    handle_note TEXT,                     -- 处理记录（沟通过什么、家长是否知情）
    handle_time DATETIME,
    journal_id INTEGER,                   -- 来源心理周记ID（周记高分触发的预警才有），用于回写学生端
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 学生心理周记：比「情绪评估」多记录睡眠、压力源、持续时长等，
-- 提交后沉淀进心理画像；分值 >= 70 时额外触发预警通知班主任。
CREATE TABLE IF NOT EXISTS student_psych_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    mood_tag TEXT DEFAULT '平静',             -- 情绪标签（平静/低落/焦虑/烦躁/疲惫/其他）
    mood_score INTEGER DEFAULT 50,           -- 自评分值（0-100，越高越难受）
    sleep TEXT DEFAULT '一般',               -- 睡眠（良好/一般/较差）
    stress_source TEXT DEFAULT '其他',        -- 压力来源（学业/人际/家庭/就业/经济/其他）
    duration TEXT DEFAULT '今天',             -- 持续多久（今天/几天/一两周/一个月以上）
    content TEXT NOT NULL,                   -- 想说的话
    status TEXT DEFAULT '待跟进',             -- 待跟进/跟进中/已跟进
    handler_id INTEGER,                      -- 跟进老师（本班班主任）
    handle_note TEXT,                        -- 老师回复（学生可见）
    handle_time DATETIME,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 学生反馈工单表
-- 学生在「我的反馈」里提交，本班班主任在「反馈处理」里回复并结案，
-- 回复内容（solution）学生能看到，处理过程进操作日志。
CREATE TABLE IF NOT EXISTS student_feedback_ticket (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    category TEXT DEFAULT '其他',          -- 反馈类型（课程教学/老师沟通/住宿生活/报修设施/教务流程/其他）
    content TEXT NOT NULL,                -- 反馈内容摘要
    detail TEXT,                          -- 详细反馈内容
    status TEXT DEFAULT '待处理',          -- 处理进度（待处理/处理中/已解决）
    solution TEXT,                        -- 老师回复 / 最终解决方案（学生可见）
    handler_id INTEGER,                   -- 处理老师（本班班主任）
    handle_time DATETIME,                 -- 最后处理时间
    is_notified INTEGER DEFAULT 0,        -- 是否已通知学生（0否 1是）
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================================
-- 企业员工智能业务助手 Agent 相关表
-- =====================================================================

-- 意向客户表（销售线索与跟进）
CREATE TABLE IF NOT EXISTS crm_lead (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,          -- 客户姓名
    contact_info TEXT,                    -- 联系方式
    background_info TEXT,                 -- 客户背景与档案
    follow_up_history TEXT,               -- 历史跟进记录（JSON/长文本）
    status TEXT DEFAULT '新增意向',        -- 流转状态（新增意向/跟进中/已签约/已流失）
    class_id INTEGER,                     -- 归入的班（活动试听班：有联系方式且未流失的意向学员）
    owner_employee_id INTEGER NOT NULL,   -- 负责员工ID
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 员工日报表
CREATE TABLE IF NOT EXISTS employee_daily_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    report_date DATE NOT NULL,            -- 日报所属日期
    content TEXT NOT NULL,                -- 结构化后的日报文本
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 学生成绩表
CREATE TABLE IF NOT EXISTS student_score (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_name TEXT NOT NULL,            -- 课程名称
    score REAL NOT NULL,                  -- 成绩（REAL支持小数）
    semester TEXT,                        -- 学期
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================================
-- 客服与活动 Agent 相关表
-- =====================================================================

-- 课程与项目表
CREATE TABLE IF NOT EXISTS course_project (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,           -- 项目/课程名称
    category TEXT,                        -- 类别（语言培训/背景提升/硕博连读等）
    description TEXT,                     -- 项目详情介绍
    target_audience TEXT                  -- 适合人群/学历要求
);

-- 活动与讲座表
CREATE TABLE IF NOT EXISTS event_lecture (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name TEXT NOT NULL,             -- 活动/讲座名称
    event_type TEXT,                      -- 类型（线上/线下）
    start_time DATETIME NOT NULL,         -- 开始时间
    location TEXT,                        -- 地点或线上链接
    max_participants INTEGER,             -- 最大报名人数
    current_participants INTEGER DEFAULT 0 -- 当前报名人数
);

-- 活动报名表
CREATE TABLE IF NOT EXISTS event_registration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,            -- 关联活动ID
    customer_id INTEGER NOT NULL,         -- 报名客户ID
    status TEXT DEFAULT '已报名',          -- 报名状态
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES event_lecture(id)
);

-- =====================================================================
-- 补充：对话记录表（心理画像的情绪数据来源）
-- =====================================================================
CREATE TABLE IF NOT EXISTS conversation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    agent_type TEXT NOT NULL,             -- 哪个Agent产生的对话
    user_input TEXT NOT NULL,             -- 用户输入
    ai_output TEXT,                       -- AI回复
    emotion_tag TEXT,                     -- 本次对话情绪标签（供心理画像累积）
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================================
-- 操作日志（工作日报）：所有关键动作留痕
-- 个人只看自己的，管理员在后台看全量但不可改
-- =====================================================================
CREATE TABLE IF NOT EXISTS op_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id INTEGER,
    actor_name TEXT,
    actor_role TEXT,
    action TEXT NOT NULL,
    action_label TEXT,
    target_type TEXT,
    target_id INTEGER,
    summary TEXT NOT NULL,
    detail TEXT,
    result TEXT DEFAULT '成功',
    create_time DATETIME
);

CREATE INDEX IF NOT EXISTS idx_op_log_actor ON op_log(actor_id, create_time DESC);
CREATE INDEX IF NOT EXISTS idx_op_log_time ON op_log(create_time DESC);

-- =====================================================================
-- 活动（顾问设计：讲什么、谁来讲、什么时候、多少名额）
-- 说明：event_lecture / event_registration 是给 Dify 工具用的旧表，
--       这里另建一套带讲师、名额、报名人信息的表，互不影响。
-- =====================================================================
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,                  -- 活动名称
    category TEXT,                        -- 类型（线下分享会 / 线上说明会 / 开放日）
    description TEXT,                     -- 活动内容简介
    speaker TEXT,                         -- 主讲老师
    start_time DATETIME NOT NULL,         -- 开始时间
    end_time DATETIME,                    -- 结束时间
    location TEXT,                        -- 地点 / 线上会议号
    capacity INTEGER NOT NULL DEFAULT 30, -- 名额
    status TEXT DEFAULT '开放报名',        -- 开放报名 / 已结束 / 已取消
    created_by INTEGER,                   -- 设计这场活动的顾问
    create_time DATETIME
);

CREATE TABLE IF NOT EXISTS activity_signup (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,
    name TEXT NOT NULL,                   -- 报名人姓名
    phone TEXT NOT NULL,                  -- 手机号（11 位，唯一）
    lead_id INTEGER,                      -- 同时写入的客户线索
    remark TEXT,                          -- 报名时说的话 / 意向
    status TEXT DEFAULT '已报名',
    create_time DATETIME,
    FOREIGN KEY (activity_id) REFERENCES activity(id)
);

CREATE INDEX IF NOT EXISTS idx_activity_signup ON activity_signup(activity_id, create_time DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_activity_signup_phone ON activity_signup(activity_id, phone);
