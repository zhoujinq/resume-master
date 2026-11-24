#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容质量审计：不输出伪精确分数，只给可定位、可处理的问题。"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

import yaml


def plain(text):
    return re.sub(r"\[\[(.*?)\]\]|\*\*(.*?)\*\*", lambda m: m.group(1) or m.group(2), str(text or ""))


def normalized(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", plain(text)))


def bullets(data):
    for si, section in enumerate(data.get("sections") or []):
        entries = list(section.get("bullets") or [])
        for item in section.get("items") or []:
            entries.extend(item.get("bullets") or [])
        for bi, bullet in enumerate(entries):
            if isinstance(bullet, dict):
                yield f"sections[{si}].bullets[{bi}]", str(bullet.get("text") or "")


def audit_content(data):
    checks = []

    def add(code, status, detail, category="advisory"):
        checks.append({"code": code, "status": status, "detail": detail, "category": category})

    seen = {}
    emphasis_count = 0
    banned_path = Path(__file__).resolve().parents[1] / "assets" / "banned-words.json"
    banned = json.loads(banned_path.read_text(encoding="utf-8")) if banned_path.exists() else {"words": [], "patterns": []}
    for path, text in bullets(data):
        key = normalized(text)
        if key in seen:
            add("DUPLICATE", "FAIL", f"{path} 与 {seen[key]} 重复", "core")
        seen[key] = path
        visible = plain(text)
        if len(visible) > 120:
            add("LONG_BULLET", "WARN", f"{path} 共 {len(visible)} 字符，建议拆分或删减")
        hits = [word for word in banned.get("words", []) if word.lower() in visible.lower()]
        hits += [pattern for pattern in banned.get("patterns", []) if re.search(pattern, visible)]
        if hits:
            add("VAGUE", "WARN", f"{path} 含空泛表述：{hits}")
        emphasis_count += len(re.findall(r"\[\[.*?\]\]|\*\*.*?\*\*", text))
    if emphasis_count > 6:
        add("EMPHASIS", "WARN", f"全文共有 {emphasis_count} 处强调，建议不超过 6 处")
    for requirement in (data.get("jd") or {}).get("requirements") or []:
        if requirement.get("gap") is True:
            add("JD_GAP", "WARN", f"真实缺口：{requirement.get('requirement')}")
    if not checks:
        add("CONTENT_AUDIT", "PASS", "未发现重复、空泛、超长、过度强调或未披露 JD 缺口")
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("yaml", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    data = yaml.safe_load(args.yaml.read_text(encoding="utf-8")) or {}
    checks = audit_content(data)
    result = {"source": str(args.yaml), "overall": "FAIL" if any(c["status"] == "FAIL" for c in checks) else ("WARN" if any(c["status"] == "WARN" for c in checks) else "PASS"), "checks": checks}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(text, encoding="utf-8")
    print(text)
    return 1 if result["overall"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
