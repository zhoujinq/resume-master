#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resume-master · 交付门禁
检查一份渲染出来的简历 PDF（配合 YAML）是否达到可投递标准。

用法:
    python qa.py resume.pdf [resume.yaml] [--pages 2] [--strict]

退出码 0 = 通过，1 = 有阻断项（❌）。
"""
import argparse
import os
import re
import sys

import fitz  # PyMuPDF
import yaml

A4_W, A4_H = 595.28, 841.89
MARGIN_L, MARGIN_R = 48.2, 547.4      # 17mm 版心（与 assets/resume.css 的 @page 一致）
BOTTOM_SAFE = 806.0     # 12mm 下边距

BANNED_CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "banned-words.json")


def load_banned():
    import json
    try:
        with open(BANNED_CFG, encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("words", []), cfg.get("patterns", []), int(cfg.get("threshold", 6))
    except Exception:
        return [], [], 6
PLACEHOLDER = re.compile(r"(XXX|xxx|待填|待补|TODO|\[.{0,6}\]|＿)")

results = []


def add(level, item, detail=""):
    results.append((level, item, detail))


def check_overflow(doc):
    bad = []
    for pno, page in enumerate(doc, 1):
        for b in page.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    x0, _, x1, y1 = s["bbox"]
                    if s["text"].strip() and (x0 < MARGIN_L - 1.5 or x1 > MARGIN_R + 1.5):
                        bad.append((pno, round(x0, 1), round(x1, 1), s["text"][:24]))
                    if y1 > BOTTOM_SAFE and not re.match(r"^\d+\s*/\s*\d+$", s["text"].strip()):
                        bad.append((pno, "bottom", round(y1, 1), s["text"][:24]))
    if bad:
        for x in bad[:6]:
            add("❌", "文本越界", f"p{x[0]} x{x[1]}→{x[2]} {x[3]!r}")
    else:
        add("✅", "文本越界", "全部在版心内")


def check_pages(doc, expect):
    n = doc.page_count
    if expect and n != expect:
        add("❌", "页数", f"实际 {n} 页，预期 {expect} 页")
    else:
        add("✅", "页数", f"{n} 页")


def check_fill(doc):
    """最后一页内容占比：留白超过 60% 说明没排满。"""
    last = doc[doc.page_count - 1]
    ys = [b[3] for b in last.get_text("blocks") if b[3] < BOTTOM_SAFE - 8]
    bottom = max(ys) if ys else 0
    ratio = (bottom - 40) / (BOTTOM_SAFE - 40)
    if doc.page_count > 1 and ratio < 0.40:
        add("⚠️", "末页留白", f"只用了 {ratio:.0%}，建议补内容或压成一页")
    else:
        add("✅", "末页留白", f"占用 {ratio:.0%}")


def check_text(doc, allowed_words=()):
    text = "\n".join(p.get_text() for p in doc)
    words, patterns, threshold = load_banned()
    allowed_words = set(allowed_words)
    counter = {}
    for w in words:
        if w in allowed_words:
            continue
        n = text.count(w)
        if n:
            counter[w] = n
    for pat in patterns:
        for m in re.findall(pat, text):
            matched = str(m)
            if any(word in matched for word in allowed_words):
                continue
            counter[matched] = counter.get(matched, 0) + 1
    total = sum(counter.values())
    suffix = f"；已豁免用户确认词：{'、'.join(sorted(allowed_words))}" if allowed_words else ""
    if total >= threshold:
        add("❌", "禁忌词", f"命中 {total} 次（阈值 {threshold}）：" + "、".join(f"{k}×{v}" for k, v in counter.items()) + suffix)
    elif total:
        add("⚠️", "禁忌词", f"命中 {total} 次：" + "、".join(f"{k}×{v}" for k, v in counter.items()) + suffix)
    else:
        add("✅", "禁忌词", "未命中" + suffix)

    todo = text.count("【待补】")
    if todo:
        add("⚠️", "待补占位", f"还剩 {todo} 处【待补】，投递前必须填")
    else:
        add("✅", "待补占位", "无")

    ph = PLACEHOLDER.findall(text)
    if ph:
        add("❌", "占位符残留", "、".join(sorted(set(ph))[:6]))
    else:
        add("✅", "占位符", "无残留")


def check_yaml(path, doc):
    if not path or not os.path.exists(path):
        return
    data = yaml.safe_load(open(path, encoding="utf-8")) or {}
    meta = data.get("meta") or {}
    if not meta.get("contact"):
        add("❌", "联系方式", "meta.contact 为空")
    else:
        add("✅", "联系方式", f"{len(meta['contact'])} 项")
    inline_links = [x for x in (meta.get("contact") or []) if isinstance(x, dict) and x.get("u")]
    if not meta.get("links") and not inline_links:
        add("⚠️", "外部链接", "未配置作品集 / GitHub")
    else:
        add("✅", "外部链接", f"{len(meta.get('links') or []) + len(inline_links)} 条")

    dates = []
    for sec in data.get("sections") or []:
        for it in sec.get("items") or []:
            if it.get("date"):
                dates.append(it["date"])
    ok = [d for d in dates if re.match(r"^\d{4}\.\d{2}\s*[–-]\s*(\d{4}\.\d{2}|至今)$", d.strip())]
    if dates and len(ok) != len(dates):
        bad = [d for d in dates if d not in ok]
        add("⚠️", "日期格式", "不统一：" + "、".join(bad[:4]))
    elif dates:
        add("✅", "日期格式", f"{len(dates)} 条全部统一为 YYYY.MM – YYYY.MM")

    # 每条 bullet 是否有"判断"信号（不是硬门禁，只提示）
    weak = 0
    total = 0
    for sec in data.get("sections") or []:
        for it in sec.get("items") or []:
            for b in it.get("bullets") or []:
                total += 1
                if not re.search(r"\d", b) and not re.search(r"(所以|因此|判断|决定|改为)", b):
                    weak += 1
    if total:
        pct = weak / total
        if pct > 0.5:
            add("⚠️", "内容密度", f"{weak}/{total} 条既无数字也无判断，建议重写")
        else:
            add("✅", "内容密度", f"{total - weak}/{total} 条带数字或判断")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("yaml_path", nargs="?", default=None)
    ap.add_argument("--pages", type=int, default=None)
    ap.add_argument("--strict", action="store_true", help="⚠️ 也算失败")
    ap.add_argument("--allow-word", action="append", default=[], help="豁免用户已确认的具体表述；可重复传入")
    args = ap.parse_args()

    doc = fitz.open(args.pdf)
    check_overflow(doc)
    check_pages(doc, args.pages)
    check_fill(doc)
    check_text(doc, allowed_words=args.allow_word)
    check_yaml(args.yaml_path, doc)

    print(f"resume-master QA · {os.path.basename(args.pdf)}")
    print("-" * 46)
    for level, item, detail in results:
        print(f"{level}  {item:<8} {detail}")
    fails = [r for r in results if r[0] == "❌"]
    warns = [r for r in results if r[0] == "⚠️"]
    print("-" * 46)
    print(f"结论：{len(fails)} 阻断 / {len(warns)} 提醒")
    sys.exit(1 if fails or (args.strict and warns) else 0)


if __name__ == "__main__":
    main()
