from copy import deepcopy


def valid_data():
    return {
        "meta": {
            "name": "林示例",
            "role": "海外产品运营",
            "contact": [
                "深圳",
                {"t": "example@example.com", "u": "mailto:example@example.com"},
            ],
            "links": [{"label": "作品", "url": "https://example.com/work"}],
            "photo": None,
        },
        "facts": [
            {
                "id": "F001",
                "statement": "独立拓展 12 家虚构客户，确认回款 30 万元。",
                "status": "confirmed",
                "ownership": "personal",
                "source": "用户确认的虚构样例事实",
                "note": "可说明客户口径与回款口径。",
            },
            {
                "id": "F002",
                "statement": "协助团队完成 2 次虚构复盘。",
                "status": "authorized",
                "ownership": "assisted",
                "source": "用户授权的虚构样例调整",
                "note": "只承担材料整理。",
            },
            {
                "id": "F003",
                "statement": "独立整理虚构项目工具与说明文档。",
                "status": "confirmed",
                "ownership": "personal",
                "source": "用户确认的虚构样例事实",
                "note": "可展示脱敏说明。",
            },
        ],
        "jd": {
            "requirements": [
                {"requirement": "客户拓展", "evidence": ["F001"]},
                {"requirement": "跨团队协作", "evidence": ["F002"]},
                {"requirement": "尚待补齐的外语成绩", "evidence": [], "gap": True},
            ]
        },
        "sections": [
            {
                "title": "工作经历",
                "note": None,
                "body": None,
                "items": [
                    {
                        "org": "示例科技有限公司",
                        "role": "产品运营",
                        "date": "2024.01–2025.01",
                        "bullets": [
                            {"text": "独立拓展 [[12 家]]虚构客户，确认回款 **30 万元**。", "facts": ["F001"]},
                            {"text": "协助团队完成 2 次虚构复盘，仅负责材料整理。", "facts": ["F002"]},
                        ],
                    }
                ],
            },
            {
                "title": "项目经历",
                "note": "所有内容均为虚构",
                "page_break_before": True,
                "variant": "project",
                "body": "先写用户意图，再写可核验证据。",
                "items": [
                    {
                        "org": "示例文档工具",
                        "date": "2025.02–2025.03",
                        "url": "https://example.com/demo",
                        "bullets": [
                            {"text": "独立整理虚构项目工具与说明文档。", "facts": ["F003"]}
                        ],
                    }
                ],
            },
        ],
    }


def mutated(mutator):
    data = valid_data()
    mutator(data)
    return data


def clone(data):
    return deepcopy(data)
