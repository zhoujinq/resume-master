#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容质量审计：定位结构套话并对账润色前后事实，不输出伪精确分数。"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import yaml


STRUCTURAL_RULES = [
    {
        "code": "CHAT_RESIDUE",
        "status": "FAIL",
        "category": "core",
        "patterns": [r"希望这份简历", r"希望本简历", r"感谢您的阅读", r"期待与您进一步沟通", r"如果您需要", r"我可以提供", r"欢迎联系我", r"以上是我的"],
        "action": "移除对话或求职信残留，只保留招聘方需要核对的经历事实。",
    },
    {
        "code": "DOCUMENT_NARRATION",
        "status": "FAIL",
        "category": "core",
        "patterns": [r"本简历", r"这份简历", r"以下内容", r"本段主要", r"上述经历"],
        "action": "删除对文档自身的介绍，直接陈述候选人的动作、对象与结果。",
    },
    {
        "code": "UNCONFIRMED_FACT",
        "status": "FAIL",
        "category": "core",
        "patterns": [r"大概", r"据说", r"可能参与", r"应该是", r"应该有", r"据悉", r"据了解"],
        "action": "回到事实台账核实；无法确认的表述不得进入终稿，不用润色掩盖不确定性。",
    },
    {
        "code": "STAGED_CONTRAST",
        "status": "WARN",
        "category": "advisory",
        "patterns": [r"不是[^。；\n]{0,40}而是", r"并非[^。；\n]{0,40}而是", r"不仅[^。；\n]{0,40}更", r"与其[^。；\n]{0,40}不如"],
        "action": "直接写事实；只有负半句用于澄清真实误解或归属时，才经人工判断保留对比。",
    },
    {
        "code": "STAGED_OPENER",
        "status": "WARN",
        "category": "advisory",
        "patterns": [r"值得一提", r"总的来说", r"综上所述", r"归根结底", r"本质上", r"关键在于", r"最重要的是"],
        "action": "删除铺垫或重复总结，让具体事实直接承担重点。",
    },
    {
        "code": "INFLATED_SIGNIFICANCE",
        "status": "WARN",
        "category": "advisory",
        "patterns": [r"行业标杆", r"行业领先", r"里程碑", r"颠覆", r"重大突破", r"深远影响", r"核心竞争力", r"卓越", r"顶尖", r"一流", r"极大提升", r"巨大提升", r"广受好评", r"一致认可"],
        "action": "保留可核验结果，删除没有额外证据的重要性、宣传语和宏大判断。",
    },
    {
        "code": "UNATTRIBUTED_AUTHORITY",
        "status": "WARN",
        "category": "advisory",
        "patterns": [r"专家认可", r"业内知名", r"客户一致好评", r"客户一致认可", r"广受赞誉", r"权威背书"],
        "action": "写明真实来源、对象与评价口径；没有证据时不借无名权威增强主张。",
    },
]

ABSTRACT_TERMS = {
    "专业性", "逻辑性", "执行力", "影响力", "竞争力", "创新", "赋能", "协同",
    "体系化", "系统化", "精细化", "数字化", "智能化", "高质量", "高效率", "价值感",
}
QUALIFIERS = ("可能", "较为", "比较", "基本上", "一定程度上", "某种程度上", "相对来说", "大体上")


def plain(text):
    return re.sub(r"\[\[(.*?)\]\]|\*\*(.*?)\*\*", lambda m: m.group(1) or m.group(2), str(text or ""))


def normalized(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", plain(text)))


def bullets(data):
    for si, section in enumerate(data.get("sections") or []):
        for bi, bullet in enumerate(section.get("bullets") or []):
            if isinstance(bullet, dict):
                yield f"sections[{si}].bullets[{bi}]", str(bullet.get("text") or "")
        for ii, item in enumerate(section.get("items") or []):
            for bi, bullet in enumerate(item.get("bullets") or []):
                if isinstance(bullet, dict):
                    yield f"sections[{si}].items[{ii}].bullets[{bi}]", str(bullet.get("text") or "")


def mask_prose(value):
    """只豁免 sections 内 bullet.text；其他同名或新增字段仍受保护。"""
    from copy import deepcopy

    masked = deepcopy(value)
    for section in masked.get("sections") or []:
        candidates = list(section.get("bullets") or [])
        for item in section.get("items") or []:
            candidates.extend(item.get("bullets") or [])
        for bullet in candidates:
            if isinstance(bullet, dict) and "text" in bullet:
                bullet["text"] = "<prose>"
    return masked


def number_tokens(text):
    normalized_text = unicodedata.normalize("NFKC", plain(text))
    return Counter(re.findall(r"\d+(?:\.\d+)*(?:%)?", normalized_text))


def audit_content(data, baseline=None):
    checks = []

    def add(code, status, detail, category="advisory", action=None):
        check = {"code": code, "status": status, "detail": detail, "category": category}
        if action:
            check["action"] = action
        checks.append(check)

    seen = {}
    emphasis_count = 0
    bullet_count = 0
    decorative_labels = 0
    dash_count = 0
    banned_path = Path(__file__).resolve().parents[1] / "assets" / "banned-words.json"
    banned = json.loads(banned_path.read_text(encoding="utf-8")) if banned_path.exists() else {"words": [], "patterns": []}

    for path, text in bullets(data):
        bullet_count += 1
        key = normalized(text)
        if key in seen:
            add("DUPLICATE", "FAIL", f"{path} 与 {seen[key]} 重复", "core", "合并重复信息或删除没有新增证据的 bullet。")
        seen[key] = path
        visible = plain(text)
        if len(visible) > 120:
            add("LONG_BULLET", "WARN", f"{path} 共 {len(visible)} 字符，建议拆分或删减", action="优先保留岗位相关事实；需要改变事实结构时返回全文确认，不为缩短而删数字。")

        hits = [word for word in banned.get("words", []) if word.lower() in visible.lower()]
        hits += [pattern for pattern in banned.get("patterns", []) if re.search(pattern, visible)]
        if hits:
            add("VAGUE", "WARN", f"{path} 含空泛表述：{hits}", action="把抽象词替换为已有证据中的具体动作；没有证据时省略，不换另一组套话。")

        for rule in STRUCTURAL_RULES:
            matched = [pattern for pattern in rule["patterns"] if re.search(pattern, visible, flags=re.IGNORECASE)]
            if matched:
                add(rule["code"], rule["status"], f"{path} 命中结构模式：{matched}", rule["category"], rule["action"])

        abstract_hits = sorted(term for term in ABSTRACT_TERMS if term in visible)
        if len(abstract_hits) >= 3:
            add("ABSTRACT_TRIAD", "WARN", f"{path} 同时堆叠抽象名词：{abstract_hits}", action="按事实需要保留项目，不为节奏凑三个抽象词；用实际对象和动作替代。")

        qualifiers = [term for term in QUALIFIERS if term in visible]
        if len(qualifiers) >= 2:
            add("STACKED_QUALIFIERS", "WARN", f"{path} 堆叠限定词：{qualifiers}", action="只保留事实需要的真实不确定性；暂定事实仍需回到台账核实。")

        dash_count += len(re.findall(r"——|(?<!—)—(?!—)|\s--\s", visible))
        if re.match(r"^\s*(?:\*\*[^*]+\*\*|【[^】]+】)\s*[:：]", text):
            decorative_labels += 1
        emphasis_count += len(re.findall(r"\[\[.*?\]\]|\*\*.*?\*\*", text))

    if dash_count >= 3:
        add("DASH_OVERUSE", "WARN", f"全文出现 {dash_count} 处破折号连接", action="用逗号、句号或明确句法表达关系；日期范围中的连接号不在此检查内。")
    if bullet_count >= 3 and decorative_labels / bullet_count >= 0.75:
        add("DECORATIVE_LABELS", "WARN", f"{decorative_labels}/{bullet_count} 条 bullet 使用加粗或方括号标签", action="只有标签本身提供新信息时保留；不要给每条经历套同一种装饰格式。")
    if emphasis_count > 6:
        add("EMPHASIS", "WARN", f"全文共有 {emphasis_count} 处强调，建议不超过 6 处", action="只强调会改变岗位判断的关键词或成果，不按固定数量补强调。")

    for requirement in (data.get("jd") or {}).get("requirements") or []:
        if requirement.get("gap") is True:
            add("JD_GAP", "WARN", f"真实缺口：{requirement.get('requirement')}", action="如实保留缺口；只有 JD 明确要求时才提示，不虚构经历填补。")

    if baseline is not None:
        before_prose = dict(bullets(baseline))
        after_prose = dict(bullets(data))
        if mask_prose(baseline) != mask_prose(data):
            add("NON_PROSE_CHANGED", "FAIL", "纯润色只允许 bullet.text 变化；事实、归属、URL、结构或其他字段已改变", "core", "退出纯润色，恢复非正文字段并重新执行证据与全文确认。")
        else:
            number_changes = []
            for path in sorted(set(before_prose) | set(after_prose)):
                before_numbers = number_tokens(before_prose.get(path, ""))
                after_numbers = number_tokens(after_prose.get(path, ""))
                if before_numbers != after_numbers:
                    number_changes.append({"path": path, "before": dict(before_numbers), "after": dict(after_numbers)})
            if number_changes:
                add("NUMBER_CHANGED", "FAIL", f"纯润色前后数字词元不一致：{number_changes}", "core", "恢复原有数字；确需新增或修正数字时，先更新证据并重新确认。")
            else:
                add("MECHANICAL_FACTS", "PASS", "非正文字段与每条 bullet 的数字词元对账一致", "core", "这只证明机械字段未变，不能证明语义等价。")

        if before_prose != after_prose:
            add("SEMANTIC_REVIEW", "WARN", "正文已变化；名称、动作、范围、因果和限制条件仍需人工逐条对账", action="由执行者与用户核对原意，不把字段和数字对账写成自动证明事实未变。")

    if not checks:
        add("CONTENT_AUDIT", "PASS", "未发现重复、结构套话、空泛、超长、过度强调或未披露 JD 缺口")
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("yaml", type=Path)
    parser.add_argument("--baseline", type=Path, help="纯润色前的 YAML；只允许 bullet.text 与表达层变化")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    data = yaml.safe_load(args.yaml.read_text(encoding="utf-8")) or {}
    baseline = yaml.safe_load(args.baseline.read_text(encoding="utf-8")) if args.baseline else None
    checks = audit_content(data, baseline=baseline)
    result = {
        "source": str(args.yaml),
        "baseline": str(args.baseline) if args.baseline else None,
        "overall": "FAIL" if any(c["status"] == "FAIL" for c in checks) else ("WARN" if any(c["status"] == "WARN" for c in checks) else "PASS"),
        "checks": checks,
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(text, encoding="utf-8")
    print(text)
    return 1 if result["overall"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
