#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""证据台账校验：只证明可追溯与归属一致，不替代用户确认真实性。"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import yaml

STATUSES = {"confirmed", "authorized", "provisional"}
OWNERSHIPS = {"personal", "team", "assisted", "demo"}
NUMBER = re.compile(r"\d+(?:[.:/]\d+)*%?")
INDEPENDENT = re.compile(r"独立|主导")
DEMO_WORD = re.compile(r"演示|示例|虚构")


def norm(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or "")))


def iter_bullets(data):
    for si, section in enumerate(data.get("sections") or []):
        for bi, bullet in enumerate(section.get("bullets") or []):
            yield f"sections[{si}].bullets[{bi}]", bullet
        for ii, item in enumerate(section.get("items") or []):
            for bi, bullet in enumerate(item.get("bullets") or []):
                yield f"sections[{si}].items[{ii}].bullets[{bi}]", bullet


def validate_resume(data):
    errors = []
    facts = data.get("facts")
    if not isinstance(facts, list) or not facts:
        return ["facts: 至少一条事实台账"]
    fact_map = {}
    for index, fact in enumerate(facts):
        path = f"facts[{index}]"
        if not isinstance(fact, dict):
            errors.append(f"{path}: 必须是对象")
            continue
        fact_id = str(fact.get("id") or "").strip()
        if not fact_id:
            errors.append(f"{path}.id: 不能为空")
            continue
        if fact_id in fact_map:
            errors.append(f"{path}.id: 重复 {fact_id}")
        fact_map[fact_id] = fact
        if not str(fact.get("statement") or "").strip():
            errors.append(f"{path}.statement: 不能为空")
        status = fact.get("status")
        if status not in STATUSES:
            errors.append(f"{path}.status: 非法状态 {status!r}")
        if fact.get("ownership") not in OWNERSHIPS:
            errors.append(f"{path}.ownership: 非法归属 {fact.get('ownership')!r}")
        if not str(fact.get("source") or "").strip():
            errors.append(f"{path}.source: 必须记录来源")
        if not str(fact.get("note") or "").strip():
            errors.append(f"{path}.note: 必须记录可答辩说明或待核对点")

    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("sections: 至少一个含正文的章节")
    else:
        for index, section in enumerate(sections):
            path = f"sections[{index}]"
            if not isinstance(section, dict):
                errors.append(f"{path}: 必须是对象")
                continue
            if not str(section.get("title") or "").strip():
                errors.append(f"{path}.title: 不能为空")
            visible = bool(
                str(section.get("body") or "").strip()
                or (section.get("bullets") or [])
                or (section.get("items") or [])
            )
            if not visible:
                errors.append(f"{path}: 空章节不得进入终稿；请省略该章节")

    links = (data.get("meta") or {}).get("links")
    if links is None:
        links = []
    if not isinstance(links, list):
        errors.append("meta.links: 必须是列表；没有链接时省略此字段")
    else:
        for index, link in enumerate(links):
            url = (link.get("url") or link.get("u")) if isinstance(link, dict) else None
            if not str(url or "").strip():
                errors.append(f"meta.links[{index}].url: 已配置链接必须有真实 URL；没有链接时省略整个 links 字段")

    for path, bullet in iter_bullets(data):
        if not isinstance(bullet, dict) or not str(bullet.get("text") or "").strip():
            errors.append(f"{path}: 必须使用包含 text 与 facts 的对象")
            continue
        refs = bullet.get("facts")
        if not isinstance(refs, list) or not refs:
            errors.append(f"{path}.facts: 每条成果必须引用事实 ID")
            continue
        unknown = [ref for ref in refs if ref not in fact_map]
        for ref in unknown:
            errors.append(f"{path}.facts: 未知事实 {ref}")
        linked = [fact_map[ref] for ref in refs if ref in fact_map]
        for fact in linked:
            if fact.get("status") == "provisional":
                errors.append(f"{path}: provisional 事实 {fact.get('id')} 不得进入终稿")
        if not linked:
            continue
        text = str(bullet["text"])
        statements = norm(" ".join(str(fact.get("statement") or "") for fact in linked))
        for number in NUMBER.findall(unicodedata.normalize("NFKC", text)):
            if norm(number) not in statements:
                errors.append(f"{path}: 数字 {number} 未在引用事实中出现")
        owners = {fact.get("ownership") for fact in linked}
        if INDEPENDENT.search(text) and "personal" not in owners and owners & {"assisted", "team"}:
            errors.append(f"{path}: ownership 为 {sorted(owners)} 的事实不得写成独立／主导")
        if owners == {"demo"} and not DEMO_WORD.search(text):
            errors.append(f"{path}: demo 事实必须保留演示／示例／虚构口径")

    jd = data.get("jd") or {}
    requirements = jd.get("requirements") or []
    for index, requirement in enumerate(requirements):
        path = f"jd.requirements[{index}]"
        refs = requirement.get("evidence") or []
        gap = requirement.get("gap") is True
        if not refs and not gap:
            errors.append(f"{path}: 无证据时必须明确 gap: true")
        for ref in refs:
            if ref not in fact_map:
                errors.append(f"{path}: 未知事实 {ref}")
        if gap and refs:
            errors.append(f"{path}: gap 与 evidence 不能同时成立")
    return errors


def main():
    parser = argparse.ArgumentParser(description="校验简历证据台账与 JD 映射")
    parser.add_argument("yaml", type=Path)
    parser.add_argument("--json", type=Path, help="可选：写入结构化校验结果")
    args = parser.parse_args()
    data = yaml.safe_load(args.yaml.read_text(encoding="utf-8")) or {}
    errors = validate_resume(data)
    result = {"source": str(args.yaml), "status": "PASS" if not errors else "FAIL", "errors": errors}
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
        return 1
    print(f"PASS {args.yaml}：{len(data.get('facts') or [])} 条事实可追溯")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
