"""静态原型使用的虚构数据。后续可替换为数据库或真实解析结果。"""

# 状态展示顺序。数量仍由机会列表计算，这里只决定界面上的排列。
STATUS_ORDER = ["待评估", "值得尝试", "准备中", "已申请", "已放弃"]

OPPORTUNITIES = [
    {
        "title": "字节跳动前端开发实习",
        "category": "实习就业",
        "organization": "字节跳动",
        "deadline": "2026-11-30",
        "requirements": "计算机相关专业在读，每周可到岗 4 天及以上。",
        "skills_required": "JavaScript、React、基础数据结构",
        "materials": "简历、作品集链接",
        "raw_content": "团队现招前端开发实习生，参与校园产品页面开发。截止日期为 2026 年 11 月 30 日。",
        "status": "准备中",
        "created_at": "2026-11-10",
    },
    {
        "title": "腾讯文档前端实习",
        "category": "实习就业",
        "organization": "腾讯",
        "deadline": "2026-12-05",
        "requirements": "本科及以上在读，能连续实习 3 个月。",
        "skills_required": "HTML、CSS、JavaScript、团队协作",
        "materials": "简历、课程成绩单",
        "raw_content": "腾讯文档团队招聘前端实习生，参与在线协作功能的界面开发。",
        "status": "准备中",
        "created_at": "2026-11-09",
    },
    {
        "title": "全国大学生数学建模竞赛",
        "category": "学科竞赛",
        "organization": "中国工业与应用数学学会",
        "deadline": "2027-09-15",
        "requirements": "全日制在校本科生，每队 3 人。",
        "skills_required": "数学建模、Python、论文写作",
        "materials": "报名表、指导教师确认",
        "raw_content": "竞赛面向全国高校本科生，要求在规定时间内完成建模论文。",
        "status": "待评估",
        "created_at": "2026-11-08",
    },
    {
        "title": "自动化所暑期科研实习",
        "category": "科研学术",
        "organization": "中国科学院自动化研究所",
        "deadline": "2027-04-20",
        "requirements": "相关专业本科三年级及以上，能到所实习 8 周。",
        "skills_required": "Python、机器学习基础、文献阅读",
        "materials": "简历、成绩单、个人陈述",
        "raw_content": "实验室开放暑期科研岗位，方向为机器学习应用，需提交个人陈述。",
        "status": "值得尝试",
        "created_at": "2026-11-06",
    },
    {
        "title": "国家奖学金评审",
        "category": "奖学金与资助",
        "organization": "所在学院学工办",
        "deadline": "2026-10-12",
        "requirements": "学习成绩位于专业前 10%，无违纪记录。",
        "skills_required": "材料整理、事迹总结",
        "materials": "申请表、成绩单、获奖证明",
        "raw_content": "学院启动本年度国家奖学金评审，请在截止日期前提交完整材料。",
        "status": "已申请",
        "created_at": "2026-09-20",
    },
    {
        "title": "商业案例分析大赛",
        "category": "学科竞赛",
        "organization": "某高校商学院",
        "deadline": "2026-10-01",
        "requirements": "需组队参加，并完成英文案例陈述。",
        "skills_required": "商业分析、英语演讲",
        "materials": "报名表、团队介绍",
        "raw_content": "大赛要求跨专业组队，并用英文进行案例陈述。当前与个人时间安排冲突。",
        "status": "已放弃",
        "created_at": "2026-09-15",
    },
]

USER_PROFILE = {
    "education": "本科",
    "major": "计算机科学与技术",
    "grade": "大三",
    "skills": [
        {"name": "Python", "level": "熟练"},
        {"name": "JavaScript", "level": "掌握"},
        {"name": "SQL", "level": "了解"},
        {"name": "机器学习", "level": "入门"},
    ],
    "projects": [
        {
            "name": "校园二手交易小程序",
            "detail": "负责商品列表、搜索和基础页面交互。",
        },
        {
            "name": "课程作业：电影评分预测",
            "detail": "使用 Python 完成数据清洗和简单模型对比。",
        },
    ],
    "interests": ["人工智能应用", "前端开发", "校园工具"],
    "goals": "暑假获得一份与 AI 应用相关的实习，并完成一个可以放进作品集的项目。",
    "constraints": "工作日晚上和周末有课，暂时不能长期离校。",
}

# 固定示例。本阶段不读取用户输入，也不调用模型。
MOCK_PARSE_RESULT = {
    "title": "中国大学生计算机设计大赛",
    "category": "学科竞赛",
    "organization": "中国大学生计算机设计大赛组织委员会",
    "deadline": "2026-05-31",
    "requirements": "普通高校在校本科生，以不超过 3 人的团队报名。",
    "skills_required": "软件开发、界面设计、项目演示",
    "materials": "作品说明、演示视频、报名表",
    "raw_content": "大赛面向普通高校在校本科生，鼓励提交软件应用与交互设计作品。作品提交截止时间为 2026 年 5 月 31 日。",
}
