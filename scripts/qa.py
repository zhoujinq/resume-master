#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""resume-master v2 · 可审计交付门禁。

核心检查证明文件可交付；严格检查证明额外验收已闭合；建议项不冒充硬失败。
未执行的检查写 NOT_RUN，绝不计入 PASS。
"""
import argparse
import datetime as _dt
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

import fitz  # PyMuPDF
import yaml

A4_W, A4_H = 595.28, 841.89
MARGIN_L, MARGIN_R = 48.2, 547.4
BOTTOM_SAFE = 806.0
BANNED_CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "banned-words.json")
PLACEHOLDER = re.compile(r"(XXX|xxx|待填|待补|TODO|\[.{0,6}\]|＿)")
STATUSES = {"PASS", "WARN", "FAIL", "NOT_RUN", "NOT_APPLICABLE"}
KINDS = {"core", "strict", "advisory"}

# 旧测试与外部调用仍读取这个三元素列表。
results = []
checks = []


def record(item, status, kind="core", detail="", evidence=None):
    if status not in STATUSES:
        raise ValueError(f"未知状态: {status}")
    if kind not in KINDS:
        raise ValueError(f"未知检查类型: {kind}")
    entry = {"item": item, "status": status, "kind": kind, "detail": str(detail)}
    if evidence:
        entry["evidence"] = [str(x) for x in evidence]
    checks.append(entry)
    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "NOT_RUN": "⏭", "NOT_APPLICABLE": "—"}[status]
    results.append((icon, item, str(detail)))
    return entry


def add(level, item, detail="", kind="core"):
    status = {"✅": "PASS", "⚠️": "WARN", "❌": "FAIL", "⏭": "NOT_RUN", "—": "NOT_APPLICABLE"}.get(level, level)
    return record(item, status, kind, detail)


def _scope_status(entries):
    if any(x["status"] == "FAIL" for x in entries):
        return "FAIL"
    if any(x["status"] == "NOT_RUN" for x in entries):
        return "INCOMPLETE"
    if any(x["status"] == "WARN" for x in entries):
        return "WARN"
    return "PASS"


def build_summary():
    scoped = {kind: _scope_status([x for x in checks if x["kind"] == kind]) for kind in sorted(KINDS)}
    if any(x["status"] == "FAIL" for x in checks):
        overall = "FAIL"
    elif scoped["core"] == "INCOMPLETE" or scoped["strict"] == "INCOMPLETE":
        overall = "INCOMPLETE"
    elif "WARN" in scoped.values():
        overall = "WARN"
    else:
        overall = "PASS"
    return {"overall": overall, **scoped}


def normalize_text(text):
    """统一排版噪声，不删除数字、文字或有效标点。"""
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = text.replace("\u00ad", "").replace("\u200b", "").replace("\ufeff", "")
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    # Word/PDF 可能把间隔号或项目符号回映射为相近 Unicode；文字与数字不参与豁免。
    text = text.replace("・", "·").replace("•", "·")
    return "".join(ch for ch in text if not ch.isspace())


def plain_md(text):
    return re.sub(r"\*\*(.+?)\*\*", r"\1", str(text or ""))


def expected_text_atoms(data):
    """提取 YAML 中应真实出现在页面上的文字；URL 由链接检查单独验证。"""
    atoms = []

    def put(value):
        value = plain_md(value).strip()
        if value:
            atoms.append(value)

    meta = data.get("meta") or {}
    for key in ("name", "role", "lede"):
        put(meta.get(key))
    for item in meta.get("contact") or []:
        put(item.get("t") if isinstance(item, dict) else item)
    for link in meta.get("links") or []:
        put(link.get("label"))
        put(link.get("short") or link.get("url"))
    for stat in meta.get("stats") or []:
        put(stat.get("n"))
        put(stat.get("l"))
    for sec in data.get("sections") or []:
        put(sec.get("title"))
        put(sec.get("note"))
        put(sec.get("body"))
        for bullet in sec.get("bullets") or []:
            put(bullet)
        for item in sec.get("items") or []:
            for key in ("org", "role", "date"):
                put(item.get(key))
            link = item.get("link") or item.get("url")
            if isinstance(link, dict):
                put(link.get("text") or link.get("url"))
            elif link:
                put(link)
            for bullet in item.get("bullets") or []:
                put(bullet)
    return atoms


def pdf_text(doc):
    return "\n".join(page.get_text() for page in doc)


def check_source_coverage(doc, data):
    atoms = expected_text_atoms(data)
    haystack = normalize_text(pdf_text(doc))
    missing = [atom for atom in atoms if normalize_text(atom) not in haystack]
    if missing:
        record("源文覆盖", "FAIL", "core", f"缺少 {len(missing)} 段：" + "｜".join(missing[:5]))
    else:
        record("源文覆盖", "PASS", "core", f"{len(atoms)} 段源文均出现在 PDF")


def extract_docx_text(path):
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    lines = []
    for para in root.findall(".//w:body//w:p", ns):
        parts = []
        for el in para.iter():
            tag = el.tag.rsplit("}", 1)[-1]
            if tag == "t":
                parts.append(el.text or "")
            elif tag == "tab":
                parts.append("\t")
            elif tag in ("br", "cr"):
                parts.append("\n")
        lines.append("".join(parts))
    return "\n".join(lines)


def _pdf_parity_text(doc):
    lines = []
    for page in doc:
        for line in page.get_text("text", sort=True).splitlines():
            if re.fullmatch(r"\s*\d+\s*/\s*\d+\s*", line):
                continue
            lines.append(line)
    return "\n".join(lines)


def check_docx_pdf_text(doc, docx_path):
    if not docx_path:
        record("DOCX/PDF文本一致性", "NOT_APPLICABLE", "core", "未提供 DOCX；仅检查 PDF")
        return
    expected = normalize_text(extract_docx_text(docx_path))
    actual = normalize_text(_pdf_parity_text(doc))
    if expected == actual:
        record("DOCX/PDF文本一致性", "PASS", "core", f"归一化后逐字一致，{len(expected)} 字符")
        return
    ratio = difflib.SequenceMatcher(None, expected, actual).ratio()
    pos = next((i for i, (a, b) in enumerate(zip(expected, actual)) if a != b), min(len(expected), len(actual)))
    record("DOCX/PDF文本一致性", "FAIL", "core",
           f"相似度 {ratio:.4%}；首个差异 #{pos}：DOCX={expected[pos:pos+40]!r} PDF={actual[pos:pos+40]!r}")


def expected_links(data):
    links = []
    meta = data.get("meta") or {}
    for item in meta.get("contact") or []:
        if isinstance(item, dict) and item.get("u"):
            links.append(str(item["u"]))
    for link in meta.get("links") or []:
        if link.get("url"):
            links.append(str(link["url"]))
    for sec in data.get("sections") or []:
        for item in sec.get("items") or []:
            link = item.get("link") or item.get("url")
            if isinstance(link, dict) and link.get("url"):
                links.append(str(link["url"]))
            elif isinstance(link, str):
                links.append(link)
    return sorted(set(links))


def docx_links(path):
    found = set()
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if not name.startswith("word/") or not name.endswith(".rels"):
                continue
            root = ET.fromstring(zf.read(name))
            for rel in root:
                if rel.attrib.get("TargetMode") == "External" and rel.attrib.get("Type", "").endswith("/hyperlink"):
                    found.add(rel.attrib.get("Target", ""))
    return found


def pdf_links(doc):
    return {str(link["uri"]) for page in doc for link in page.get_links() if link.get("uri")}


def check_links(doc, data, docx_path=None):
    expected = set(expected_links(data))
    if not expected:
        record("可点击链接", "NOT_APPLICABLE", "core", "源文件未配置外部 URL")
        return
    actual_pdf = pdf_links(doc)
    missing_pdf = sorted(expected - actual_pdf)
    details = [f"PDF {len(actual_pdf & expected)}/{len(expected)} 个预期 URL 可点击"]
    failed = bool(missing_pdf)
    if missing_pdf:
        details.append("PDF 缺少：" + "、".join(missing_pdf))
    if docx_path:
        actual_docx = docx_links(docx_path)
        missing_docx = sorted(expected - actual_docx)
        details.append(f"DOCX {len(actual_docx & expected)}/{len(expected)} 个预期 URL 为真实关系")
        if missing_docx:
            failed = True
            details.append("DOCX 缺少：" + "、".join(missing_docx))
    record("可点击链接", "FAIL" if failed else "PASS", "core", "；".join(details))


def check_fonts(doc, allowed=()):
    fonts = set()
    chars = 0
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("text", "").strip():
                        chars += len(span["text"].strip())
                        fonts.add(span.get("font") or "未命名字体")
    if chars:
        record("PDF文本层", "PASS", "core", f"{chars} 个非空白字符；实际字体：" + "、".join(sorted(fonts)))
    else:
        record("PDF文本层", "FAIL", "core", "没有可提取文字，不能把视觉清晰当作矢量文本")

    def key(name):
        name = re.sub(r"^[A-Z]{6}\+", "", str(name))
        return re.sub(r"[^a-z0-9]", "", name.lower())

    if not allowed:
        record("字体白名单", "NOT_RUN", "strict", "未提供 --font-allow；只报告实际字体，不宣称严格字体通过")
        return
    allowed_keys = [key(x) for x in allowed if key(x)]
    bad = sorted(f for f in fonts if not any(a in key(f) for a in allowed_keys))
    if bad:
        record("字体白名单", "FAIL", "strict", "白名单外字体：" + "、".join(bad))
    else:
        record("字体白名单", "PASS", "strict", "全部实际字体命中：" + "、".join(allowed))


def compare_pdf_pixels(pdf_a, pdf_b, dpi=144):
    a, b = fitz.open(pdf_a), fitz.open(pdf_b)
    try:
        result = {"equal": True, "pages": a.page_count, "diff_pixels": 0, "dpi": dpi}
        if a.page_count != b.page_count:
            return {"equal": False, "pages": a.page_count, "other_pages": b.page_count, "diff_pixels": -1, "dpi": dpi}
        for pno in range(a.page_count):
            pa = a[pno].get_pixmap(dpi=dpi, alpha=False)
            pb = b[pno].get_pixmap(dpi=dpi, alpha=False)
            if pa.width != pb.width or pa.height != pb.height or pa.n != pb.n:
                result["equal"] = False
                result["diff_pixels"] = -1
                return result
            ba, bb = pa.samples, pb.samples
            if ba != bb:
                result["equal"] = False
                step = pa.n
                result["diff_pixels"] += sum(
                    1 for i in range(0, len(ba), step) if ba[i:i+step] != bb[i:i+step]
                )
        return result
    finally:
        a.close()
        b.close()


def check_repeat_export(repeat_pdf, current_pdf, dpi=144):
    if not repeat_pdf:
        record("重导出像素差", "NOT_RUN", "strict", "未提供 --repeat-pdf，不能宣称确定性复现")
        return
    result = compare_pdf_pixels(current_pdf, repeat_pdf, dpi=dpi)
    if result["equal"] and result["diff_pixels"] == 0:
        record("重导出像素差", "PASS", "strict", f"{result['pages']} 页在 {dpi} DPI 下逐页像素差为 0")
    else:
        record("重导出像素差", "FAIL", "strict", json.dumps(result, ensure_ascii=False))


def check_photo(doc, expected=False, min_width=400, min_height=560):
    images = []
    for pno, page in enumerate(doc, 1):
        for image in page.get_images(full=True):
            xref, width, height = image[0], image[2], image[3]
            images.append((width * height, pno, xref, width, height))
    if not images:
        if expected:
            record("PDF照片", "FAIL", "core", "源文件配置照片，但 PDF 没有栅格图像")
        else:
            record("PDF照片", "NOT_APPLICABLE", "core", "未配置照片且 PDF 无栅格图像")
        record("照片像素建议", "NOT_APPLICABLE", "advisory", "无照片可检查")
        return
    record("PDF照片", "PASS", "core", f"发现 {len(images)} 个图像实例")
    _, pno, xref, width, height = max(images)
    detail = f"最大图像 p{pno} xref {xref}：{width}×{height}px；建议至少 {min_width}×{min_height}px"
    status = "PASS" if width >= min_width and height >= min_height else "WARN"
    record("照片像素建议", status, "advisory", detail + "；按最大图像估计，含 Logo 时需人工确认")


def check_visual_review(paths):
    if not paths:
        record("视觉复核", "NOT_RUN", "core", "未提供 --visual-evidence；脚本通过不等于逐页看过")
        return
    missing = [p for p in paths if not Path(p).is_file()]
    if missing:
        record("视觉复核", "FAIL", "core", "证据文件不存在：" + "、".join(missing))
    else:
        record("视觉复核", "PASS", "core", "Agent 已逐页复核并登记证据", paths)


def check_edit_undo(evidence):
    if not evidence:
        record("Word编辑撤销", "NOT_RUN", "strict", "未提供实际编辑—撤销证据")
    elif not Path(evidence).is_file():
        record("Word编辑撤销", "FAIL", "strict", f"证据不存在：{evidence}")
    else:
        record("Word编辑撤销", "PASS", "strict", "已在 Word 中改一字、撤销并复核版式", [evidence])


def load_banned():
    try:
        with open(BANNED_CFG, encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("words", []), cfg.get("patterns", []), int(cfg.get("threshold", 6))
    except Exception:
        return [], [], 6


def _is_hanging_punctuation(span):
    """只允许 Word 的一个中文标点悬挂在版心外；字母、数字和整行超宽仍失败。"""
    text = span.get("text", "").rstrip()
    x0, _, x1, _ = span["bbox"]
    overflow = x1 - MARGIN_R
    return bool(
        text and text[-1] in "，。；：？！、）》】」’”"
        and x0 <= MARGIN_R + 1.5
        and 0 < overflow <= float(span.get("size") or 0) + 1.5
    )


def _visible_span(raw_span):
    """从字符级 bbox 排除首尾空格和零宽排版符，避免把尾随空格误判成文字越界。"""
    text = "".join(c.get("c", "") for c in raw_span.get("chars", []))
    chars = [c for c in raw_span.get("chars", []) if c.get("c", "").strip() and c.get("c") not in "\u200b\ufeff\u00ad"]
    if not chars:
        return None
    boxes = [c["bbox"] for c in chars]
    return {
        "text": text,
        "size": raw_span.get("size"),
        "bbox": [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)],
    }


def check_overflow(doc):
    bad = []
    hanging = 0
    for pno, page in enumerate(doc, 1):
        for block in page.get_text("rawdict")["blocks"]:
            for line in block.get("lines", []):
                for raw_span in line["spans"]:
                    span = _visible_span(raw_span)
                    if span is None:
                        continue
                    x0, _, x1, y1 = span["bbox"]
                    if x0 < MARGIN_L - 1.5 or x1 > MARGIN_R + 1.5:
                        if x1 > MARGIN_R + 1.5 and _is_hanging_punctuation(span):
                            hanging += 1
                        else:
                            bad.append((pno, round(x0, 1), round(x1, 1), span["text"][:24]))
                    if y1 > BOTTOM_SAFE and not re.match(r"^\d+\s*/\s*\d+$", span["text"].strip()):
                        bad.append((pno, "bottom", round(y1, 1), span["text"][:24]))
    if bad:
        for item in bad[:6]:
            add("❌", "文本越界", f"p{item[0]} x{item[1]}→{item[2]} {item[3]!r}")
    else:
        suffix = f"；{hanging} 处 Word 中文悬挂标点已单列" if hanging else ""
        add("✅", "文本越界", "文字与数字均在版心内" + suffix)


def file_size_status(size):
    return ("WARN" if size > 10 * 1024 * 1024 else "PASS", f"{size / 1024 / 1024:.2f} MB；超过 10 MB 时提醒检查完整字体或图片嵌入")


def check_file_size(path):
    size = Path(path).stat().st_size
    status, detail = file_size_status(size)
    record("PDF体积", status, "advisory", detail)


def check_pages(doc, expect):
    count = doc.page_count
    if expect and count != expect:
        add("❌", "页数", f"实际 {count} 页，预期 {expect} 页")
    else:
        add("✅", "页数", f"{count} 页")


def check_fill(doc):
    last = doc[doc.page_count - 1]
    ys = [b[3] for b in last.get_text("blocks") if b[3] < BOTTOM_SAFE - 8]
    bottom = max(ys) if ys else 0
    ratio = (bottom - 40) / (BOTTOM_SAFE - 40)
    if doc.page_count > 1 and ratio < 0.40:
        add("⚠️", "末页留白", f"只用了 {ratio:.0%}，建议补内容或压成一页")
    else:
        add("✅", "末页留白", f"占用 {ratio:.0%}")


def check_text(doc, allowed_words=()):
    text = pdf_text(doc)
    words, patterns, threshold = load_banned()
    allowed_words = set(allowed_words)
    counter = {}
    for word in words:
        if word not in allowed_words and text.count(word):
            counter[word] = text.count(word)
    for pattern in patterns:
        for match in re.findall(pattern, text):
            matched = str(match)
            if any(word in matched for word in allowed_words):
                continue
            counter[matched] = counter.get(matched, 0) + 1
    total = sum(counter.values())
    suffix = f"；已豁免用户确认词：{'、'.join(sorted(allowed_words))}" if allowed_words else ""
    detail = "、".join(f"{k}×{v}" for k, v in counter.items()) + suffix
    if total >= threshold:
        add("❌", "禁忌词", f"命中 {total} 次（阈值 {threshold}）：{detail}")
    elif total:
        add("⚠️", "禁忌词", f"命中 {total} 次：{detail}")
    else:
        add("✅", "禁忌词", "未命中" + suffix)

    todo = text.count("【待补】")
    if todo:
        add("❌", "待补占位", f"还剩 {todo} 处【待补】，投递前必须填")
    else:
        add("✅", "待补占位", "无")
    placeholders = PLACEHOLDER.findall(text)
    if placeholders:
        add("❌", "占位符残留", "、".join(sorted(set(placeholders))[:6]))
    else:
        add("✅", "占位符", "无残留")


def check_yaml(path, doc):
    if not path or not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    meta = data.get("meta") or {}
    if not meta.get("contact"):
        add("❌", "联系方式", "meta.contact 为空")
    else:
        add("✅", "联系方式", f"{len(meta['contact'])} 项")
    dates = [item["date"] for sec in data.get("sections") or [] for item in sec.get("items") or [] if item.get("date")]
    ok = [d for d in dates if re.match(r"^\d{4}\.\d{2}\s*[–-]\s*(\d{4}\.\d{2}|至今)$", d.strip())]
    if dates and len(ok) != len(dates):
        add("⚠️", "日期格式", "不统一：" + "、".join(d for d in dates if d not in ok)[:200])
    elif dates:
        add("✅", "日期格式", f"{len(dates)} 条全部统一为 YYYY.MM – YYYY.MM")
    weak = total = 0
    for sec in data.get("sections") or []:
        for item in sec.get("items") or []:
            for bullet in item.get("bullets") or []:
                total += 1
                if not re.search(r"\d", bullet) and not re.search(r"(所以|因此|判断|决定|改为)", bullet):
                    weak += 1
    if total:
        if weak / total > 0.5:
            add("⚠️", "内容密度", f"{weak}/{total} 条既无数字也无判断，建议重写")
        else:
            add("✅", "内容密度", f"{total - weak}/{total} 条带数字或判断")


def _file_info(path):
    if not path:
        return None
    p = Path(path)
    return {"path": str(p.resolve()), "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}


def write_reports(json_path, md_path, artifacts):
    payload = {
        "schema": "resume-master.qa.v2",
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "summary": build_summary(),
        "artifacts": {name: _file_info(path) for name, path in artifacts.items() if path},
        "checks": checks,
    }
    if json_path:
        Path(json_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if md_path:
        summary = payload["summary"]
        lines = [
            "# resume-master v2 验收报告", "",
            f"- 总体：**{summary['overall']}**",
            f"- 核心：**{summary['core']}**；严格：**{summary['strict']}**；建议：**{summary['advisory']}**",
            "- 未做项保持 NOT_RUN；建议未达不冒充核心失败，也不计入全部通过。", "",
            "| 类型 | 状态 | 检查 | 证据与说明 |", "|---|---|---|---|",
        ]
        for check in checks:
            detail = check["detail"].replace("|", "\\|").replace("\n", " ")
            if check.get("evidence"):
                detail += "；" + "、".join(check["evidence"])
            lines.append(f"| {check['kind']} | {check['status']} | {check['item']} | {detail} |")
        lines.extend(["", "## 文件指纹", ""])
        for name, info in payload["artifacts"].items():
            lines.append(f"- {name}：`{info['sha256']}`，{info['bytes']} 字节")
        Path(md_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("yaml_path", nargs="?", default=None)
    ap.add_argument("--docx", help="同一内容源生成的 DOCX；提供后执行全文与链接关系检查")
    ap.add_argument("--repeat-pdf", help="同参数第二次 Word 导出的 PDF，用于逐页像素比较")
    ap.add_argument("--pages", type=int, default=None)
    ap.add_argument("--strict", action="store_true", help="WARN 也返回失败退出码")
    ap.add_argument("--allow-word", action="append", default=[], help="豁免用户已确认的具体表述；可重复传入")
    ap.add_argument("--font-allow", action="append", default=[], help="严格字体白名单关键词；可重复传入")
    ap.add_argument("--visual-evidence", action="append", default=[], help="Agent 已逐页查看的渲染证据；可重复传入")
    ap.add_argument("--edit-undo-evidence", help="Word 实际编辑—撤销证据文件")
    ap.add_argument("--report-json")
    ap.add_argument("--report-md")
    args = ap.parse_args()

    results.clear()
    checks.clear()
    data = None
    if args.yaml_path:
        with open(args.yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    doc = fitz.open(args.pdf)
    try:
        check_overflow(doc)
        check_file_size(args.pdf)
        check_pages(doc, args.pages)
        check_fill(doc)
        check_text(doc, allowed_words=args.allow_word)
        check_yaml(args.yaml_path, doc)
        if data is not None:
            check_source_coverage(doc, data)
            check_links(doc, data, args.docx)
        check_docx_pdf_text(doc, args.docx)
        check_fonts(doc, args.font_allow)
        check_photo(doc, expected=bool((data or {}).get("meta", {}).get("photo")))
        check_repeat_export(args.repeat_pdf, args.pdf)
        check_visual_review(args.visual_evidence)
        check_edit_undo(args.edit_undo_evidence)
    finally:
        doc.close()

    payload = write_reports(args.report_json, args.report_md,
                            {"pdf": args.pdf, "docx": args.docx, "source": args.yaml_path, "repeat_pdf": args.repeat_pdf})
    print(f"resume-master QA v2 · {os.path.basename(args.pdf)}")
    print("-" * 72)
    for check in checks:
        print(f"{check['status']:<15} {check['kind']:<8} {check['item']}: {check['detail']}")
    print("-" * 72)
    print("结论：" + json.dumps(payload["summary"], ensure_ascii=False))
    fails = [x for x in checks if x["status"] == "FAIL"]
    warns = [x for x in checks if x["status"] == "WARN"]
    core_incomplete = any(x["kind"] == "core" and x["status"] == "NOT_RUN" for x in checks)
    if fails or (args.strict and warns):
        return 1
    return 2 if core_incomplete else 0


if __name__ == "__main__":
    sys.exit(main())
