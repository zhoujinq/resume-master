#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真实 DOCX／Word PDF 验收。未执行不等于通过，建议 WARN 不伪装成核心通过。"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

import fitz
import yaml
from lxml import etree
from PIL import Image, ImageChops

ALLOWED_SIZES = {8.0, 8.5, 9.5, 10.0, 10.5, 13.0, 34.0}
ALLOWED_COLORS = {0x000000, 0x2F5BEA, 0x141519, 0x2B3038, 0x5A6069, 0x857F74}
PLACEHOLDERS = ("【待补】", "【待确认】", "TODO", "TBD", "待定", "xxx")
LINK_LABELS = {"github": ["GitHub", "GitHub个人主页", "Github"], "gmail": ["Gmail", "Gmail邮箱"]}


def _evidence_module():
    path = Path(__file__).with_name("evidence.py")
    spec = importlib.util.spec_from_file_location("resume_evidence_qa", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _content_module():
    path = Path(__file__).with_name("content_audit.py")
    spec = importlib.util.spec_from_file_location("resume_content_audit_qa", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plain_md(text):
    return re.sub(r"\[\[(.*?)\]\]|\*\*(.*?)\*\*", lambda m: m.group(1) or m.group(2), str(text or ""))


def normalize_text(text):
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = re.sub(r"[•·・■□▪]", "", text)
    text = re.sub(r"[\s\u200b]+", "", text)
    return text


def content_atoms(data):
    atoms = []

    def add(value):
        if value is None:
            return
        if isinstance(value, dict):
            add(value.get("t") or value.get("text") or value.get("label"))
            add(value.get("u") or value.get("url"))
            return
        value = plain_md(value).strip()
        if value:
            atoms.append(value)

    meta = data.get("meta") or {}
    for key in ("name", "role"):
        add(meta.get(key))
    for value in meta.get("contact") or []:
        add(value.get("t") if isinstance(value, dict) else value)
    for item in meta.get("links") or []:
        add(item.get("label"))
        add(item.get("url") or item.get("u"))
    for section in data.get("sections") or []:
        for key in ("title", "note", "body"):
            add(section.get(key))
        for bullet in section.get("bullets") or []:
            add(bullet.get("text") if isinstance(bullet, dict) else bullet)
        for item in section.get("items") or []:
            for key in ("org", "name", "role", "date", "url"):
                add(item.get(key))
            link = item.get("link") or {}
            add(link.get("text"))
            for bullet in item.get("bullets") or []:
                add(bullet.get("text") if isinstance(bullet, dict) else bullet)
    return atoms


def docx_text(path):
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in root.xpath(".//w:body//w:p", namespaces=ns):
        parts = []
        for node in paragraph.iter():
            if node.tag == "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t":
                parts.append(node.text or "")
            elif node.tag == "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tab":
                parts.append("\t")
        paragraphs.append("".join(parts))
    return "\n".join(paragraphs)


def font_allowed(name):
    normalized = str(name or "").replace(" ", "").lower()
    return normalized.startswith("sourcehansanssc") or normalized.startswith("sourcehanserifsc")


def font_size_status(sizes):
    values = [float(size) for size in sizes]
    ok = values and all(any(abs(size - allowed) <= 0.08 for allowed in ALLOWED_SIZES) for size in values)
    return "PASS" if ok else "FAIL"


def file_size_status(size):
    return "PASS" if int(size) <= 2_000_000 else "WARN"


def blank_page_status(ratios):
    return "WARN" if ratios and float(ratios[-1]) < 50 else "PASS"


def image_quality_status(dimensions):
    if not dimensions:
        return {"status": "NOT_RUN", "detail": "未提供照片实际像素"}
    width, height = max(dimensions, key=lambda pair: pair[0] * pair[1])
    status = "PASS" if width >= 400 and height >= 560 else "WARN"
    return {"status": status, "detail": f"照片实际像素 {width}×{height}；建议至少 400×560"}


def coverage(atoms, actual):
    normalized = normalize_text(actual)
    return [atom for atom in atoms if normalize_text(atom) not in normalized]


def _link_map(pdf):
    result = {}
    for page in pdf:
        for link in page.get_links():
            uri = link.get("uri") or ""
            if uri:
                result.setdefault(uri, []).append(link)
    return result


def link_check(expected, found, label):
    expected_set = set(expected)
    found_set = set(found)
    return {
        "status": "PASS" if expected_set == found_set else "FAIL",
        "detail": f"{label} {len(found_set)}/{len(expected_set)}；缺失={sorted(expected_set-found_set)}；额外={sorted(found_set-expected_set)}",
        "missing": sorted(expected_set - found_set),
        "extra": sorted(found_set - expected_set),
    }


def raw_overflow(page):
    issues = []
    width, height = page.rect.width, page.rect.height
    for block in page.get_text("rawdict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                for char in span.get("chars", []):
                    if not char.get("c", "").strip():
                        continue
                    x0, y0, x1, y1 = char["bbox"]
                    if x0 < -0.5 or y0 < -0.5 or x1 > width + 0.5 or y1 > height + 0.5 or y1 > 790.5:
                        issues.append({"char": char["c"], "bbox": [x0, y0, x1, y1], "page": page.number + 1})
    return issues


def text_metrics(pdf):
    sizes, fonts, colors = set(), set(), set()
    for page in pdf:
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if not span.get("text", "").strip():
                        continue
                    sizes.add(round(float(span["size"]), 2))
                    fonts.add(span.get("font", ""))
                    colors.add(int(span.get("color", 0)))
    return sizes, fonts, colors


def bullet_line_metrics(pdf):
    wrap_gaps, start_gaps = [], []
    bullet_pattern = re.compile(r"^\s*[▪•·■□]\s*")
    for page in pdf:
        lines = []
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                text = "".join(span.get("text", "") for span in spans)
                if text.strip():
                    size = max((float(span.get("size", 0)) for span in spans), default=0)
                    lines.append((line["bbox"], text, size))
        lines.sort(key=lambda entry: (entry[0][1], entry[0][0]))
        bullet_starts = sorted(entry[0][1] for entry in lines if bullet_pattern.match(entry[1]))
        for first, second in zip(bullet_starts, bullet_starts[1:]):
            gap = second - first
            if 10 < gap < 25:
                start_gaps.append(round(gap, 2))
        for index, entry in enumerate(lines):
            if not bullet_pattern.match(entry[1]):
                continue
            bullet_x = entry[0][0]
            current = entry
            continued = False
            for candidate in lines[index + 1:]:
                gap = candidate[0][1] - current[0][1]
                if gap <= 0.5:
                    continue
                if gap > 20 or bullet_pattern.match(candidate[1]):
                    break
                if abs(candidate[2] - current[2]) > 0.3:
                    break
                indent_ok = candidate[0][0] > bullet_x + 4 if not continued else abs(candidate[0][0] - current[0][0]) < 4
                if not indent_ok:
                    break
                if 10 < gap < 20:
                    wrap_gaps.append(round(gap, 2))
                current = candidate
                continued = True
    return wrap_gaps, start_gaps


def photo_layout_status(pdf, has_photo):
    if not has_photo:
        return {"status": "NOT_APPLICABLE", "detail": "无照片"}
    candidates = []
    for page in pdf:
        for image in page.get_images(full=True):
            for rect in page.get_image_rects(image[0]):
                candidates.append((rect.width * rect.height, page.number + 1, rect))
    if not candidates:
        return {"status": "FAIL", "detail": "YAML 指定照片，但 PDF 未找到图像"}
    _, page_number, rect = max(candidates, key=lambda item: item[0])
    expected = (485.1, 42.1, 62.4, 87.3)
    actual = (rect.x0, rect.y0, rect.width, rect.height)
    ok = all(abs(a - e) <= 3.0 for a, e in zip(actual, expected))
    return {"status": "PASS" if ok else "FAIL", "detail": f"page={page_number} x={rect.x0:.1f} y={rect.y0:.1f} w={rect.width:.1f} h={rect.height:.1f}"}


def compare_pdf_pixels(first, second, third=None, dpi=144):
    """比较 first/second；third 可作为必须被检出的变异样本，防止假比较。"""
    if len(first) != len(second):
        return {"status": "FAIL", "detail": "页数不同", "difference_pixels": []}
    differences = []
    for page_a, page_b in zip(first, second):
        a = page_a.get_pixmap(dpi=dpi, alpha=False)
        b = page_b.get_pixmap(dpi=dpi, alpha=False)
        if (a.width, a.height, a.n) != (b.width, b.height, b.n):
            differences.append(-1)
            continue
        if a.samples == b.samples:
            differences.append(0)
            continue
        mode = {1: "L", 3: "RGB", 4: "RGBA"}.get(a.n)
        if mode is None:
            return {"status": "FAIL", "detail": f"不支持的像素通道数 {a.n}", "difference_pixels": []}
        image_a = Image.frombytes(mode, (a.width, a.height), a.samples)
        image_b = Image.frombytes(mode, (b.width, b.height), b.samples)
        difference = ImageChops.difference(image_a, image_b)
        bands = difference.split()
        mask = bands[0]
        for band in bands[1:]:
            mask = ImageChops.lighter(mask, band)
        differences.append(a.width * a.height - mask.histogram()[0])
    status = "PASS" if all(value == 0 for value in differences) else "FAIL"
    detail = f"{dpi} DPI 逐页差分 {differences}"
    if third is not None:
        if len(third) != len(second):
            return {"status": "FAIL", "detail": "变异样本页数不同", "difference_pixels": differences}
        sentinel = []
        for page_a, page_b in zip(second, third):
            a = page_a.get_pixmap(dpi=dpi, alpha=False)
            b = page_b.get_pixmap(dpi=dpi, alpha=False)
            sentinel.append(0 if a.samples == b.samples else 1)
        if not any(sentinel):
            status = "FAIL"
            detail += "；变异样本未被检出"
        else:
            detail += "；变异样本已检出"
    return {"status": status, "detail": detail, "difference_pixels": differences}


def export_evidence_status(path, pdf, docx):
    if not path:
        return {"status": "NOT_RUN", "detail": "未提供 Word COM 导出日志"}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        checks = [
            data.get("exporter") == "Microsoft.Office.Interop.Word",
            int(data.get("exit_code", -1)) == 0,
            Path(data.get("input", "")).resolve() == Path(docx).resolve(),
            Path(data.get("output", "")).resolve() == Path(pdf).resolve(),
            Path(data.get("sha256", "")) and len(data.get("sha256", "")) == 64,
        ]
        return {"status": "PASS" if all(checks) else "FAIL", "detail": json.dumps(data, ensure_ascii=False)}
    except Exception as exc:
        return {"status": "FAIL", "detail": f"导出日志无效：{exc}"}


def edit_undo_status(path):
    if not path:
        return {"status": "NOT_RUN", "detail": "未执行真实 Word 编辑—撤销"}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        checks = [
            data.get("exporter") == "Microsoft.Office.Interop.Word",
            data.get("before_sha256") == data.get("after_sha256"),
            int(data.get("replacement_count", 0)) >= 1,
            int(data.get("undo_count", 0)) >= 1,
            data.get("saved") is False,
            data.get("temp_copy") is True,
        ]
        return {"status": "PASS" if all(checks) else "FAIL", "detail": json.dumps(data, ensure_ascii=False)}
    except Exception as exc:
        return {"status": "FAIL", "detail": f"编辑—撤销证据无效：{exc}"}


def summarize(checks):
    if any(check["status"] == "FAIL" for check in checks):
        return "FAIL"
    if any(check["category"] in {"core", "strict"} and check["status"] == "NOT_RUN" for check in checks):
        return "INCOMPLETE"
    if any(check["status"] == "WARN" for check in checks):
        return "WARN"
    return "PASS"


def report_markdown(source, checks):
    lines = [f"# QA：{source}", "", f"**{summarize(checks)}**", "", "| 层级 | 检查 | 状态 | 证据 |", "|---|---|---|---|"]
    for check in checks:
        detail = str(check.get("detail", "")).replace("|", "\\|").replace("\n", "<br>")
        lines.append(f"| {check['category']} | {check['name']} | {check['status']} | {detail} |")
    lines.extend(["", "`NOT_RUN` 未执行；`NOT_APPLICABLE` 不适用；建议 WARN 不等于核心 FAIL。报告不声称自动证明事实真实。"])
    return "\n".join(lines) + "\n"


def run(args):
    data = yaml.safe_load(args.yaml.read_text(encoding="utf-8")) or {}
    atoms = content_atoms(data)
    checks = []

    def add(name, category, status, detail):
        checks.append({"name": name, "category": category, "status": status, "detail": detail})

    errors = _evidence_module().validate_resume(data)
    add("证据台账与 JD 映射", "core", "PASS" if not errors else "FAIL", "；".join(errors) or f"{len(data.get('facts') or [])} 条事实可追溯")
    for content_check in _content_module().audit_content(data):
        add(f"内容审计 {content_check['code']}", content_check.get("category", "advisory"), content_check["status"], content_check["detail"])
    if args.docx and Path(args.docx).exists():
        word_text = docx_text(args.docx)
        missing = coverage(atoms, word_text)
        add("源文覆盖 DOCX", "core", "FAIL" if missing else "PASS", f"缺失 {len(missing)} 段：{missing[:8]}")
    else:
        word_text = ""
        add("源文覆盖 DOCX", "core", "NOT_RUN", "DOCX 未提供或不存在")

    pdf = None
    if args.pdf and Path(args.pdf).exists():
        pdf = fitz.open(args.pdf)
        all_text = "\n".join(page.get_text("text", sort=False) for page in pdf)
        add("PDF 导出", "core", "PASS", f"{len(pdf)} 页，{Path(args.pdf).stat().st_size} bytes")
        expected_pages = args.pages or (data.get("delivery") or {}).get("pages")
        add("页数", "core", "PASS" if expected_pages and len(pdf) == expected_pages else ("NOT_RUN" if not expected_pages else "FAIL"), f"实际 {len(pdf)}，目标 {expected_pages or '未指定'}")
        missing = coverage(atoms, all_text)
        add("源文覆盖 PDF", "core", "FAIL" if missing else "PASS", f"缺失 {len(missing)} 段：{missing[:8]}")
        add("文本层非空", "core", "FAIL" if any(not page.get_text().strip() for page in pdf) else "PASS", "逐页检查")
        if word_text:
            same = normalize_text(word_text) == normalize_text(all_text)
            add("DOCX/PDF 全文一致", "core", "PASS" if same else "FAIL", "仅统一换行与项目符号；数字与字母不删除")
        else:
            add("DOCX/PDF 全文一致", "core", "NOT_RUN", "缺少 DOCX 文本")
        placeholders = [word for word in PLACEHOLDERS if word.lower() in all_text.lower()]
        add("占位符", "core", "FAIL" if placeholders else "PASS", str(placeholders))
        overflow = [(page.number + 1, issue) for page in pdf for issue in raw_overflow(page)]
        add("逐字符越界与页底", "core", "FAIL" if overflow else "PASS", f"{len(overflow)} 处；{overflow[:5]}")
        sizes, fonts, colors = text_metrics(pdf)
        add("实际 PDF 字体", "core", "PASS" if fonts and all(font_allowed(font) for font in fonts) else "FAIL", str(sorted(fonts)))
        add("固定字号", "core", font_size_status(sizes), str(sorted(sizes)))
        bad_colors = sorted(colors - ALLOWED_COLORS)
        add("正文与强调色", "core", "FAIL" if bad_colors else "PASS", f"实际={[hex(c) for c in sorted(colors)]}；越界={[hex(c) for c in bad_colors]}")
        urls = [str(item.get("url") or item.get("u")) for item in (data.get("meta") or {}).get("links") or []]
        urls += [str(item["url"]) for section in data.get("sections") or [] for item in section.get("items") or [] if item.get("url")]
        expected_links = set(urls) | {str(v.get("u") or v.get("url")) for v in (data.get("meta") or {}).get("contact") or [] if isinstance(v, dict)}
        found = _link_map(pdf)
        result = link_check(expected_links, found, "URL")
        add("PDF 真实链接", "core", result["status"], result["detail"])
        if word_text:
            with zipfile.ZipFile(args.docx) as archive:
                rels = archive.read("word/_rels/document.xml.rels").decode("utf-8")
            found_docx = set(re.findall(r'Target="(https?://[^"]+|mailto:[^"]+)"', rels))
            result = link_check(expected_links, found_docx, "DOCX URL")
            add("DOCX 真实链接", "core", result["status"], result["detail"])
            missing_pdf = set(found_docx) - set(found)
            add("链接双端同步", "core", "FAIL" if missing_pdf else "PASS", f"PDF 缺失 {sorted(missing_pdf)}")
        else:
            add("DOCX 真实链接", "core", "NOT_RUN", "缺少 DOCX")
            add("链接双端同步", "core", "NOT_RUN", "缺少 DOCX")
        if "gmail" in found:
            lower_text = all_text.lower()
            label_ok = any(label.lower() in lower_text for label in LINK_LABELS["gmail"])
            add("Gmail 标签语义", "core", "PASS" if label_ok else "FAIL", "不能只出现 Gmail 字样而没有邮箱标签")
        photo = photo_layout_status(pdf, bool((data.get("meta") or {}).get("photo")))
        add("照片坐标与尺寸", "core", photo["status"], photo["detail"])
        dimensions = set()
        for page in pdf:
            for image in page.get_images(full=True):
                dimensions.add((int(image[2]), int(image[3])))
        quality = image_quality_status(dimensions)
        add("照片建议像素", "advisory", quality["status"], quality["detail"])
        wrap, starts = bullet_line_metrics(pdf)
        if wrap:
            ok = all(12.8 <= gap <= 14.8 for gap in wrap)
            add("项目符号行距", "core", "PASS" if ok else "FAIL", f"折行间距={wrap}pt")
        else:
            add("项目符号行距", "core", "NOT_APPLICABLE", "没有折行项目符号")
        if starts:
            ok = all(13.6 <= gap <= 14.2 or 16.5 <= gap <= 17.5 for gap in starts)
            add("项目符号起始间距", "strict", "PASS" if ok else "FAIL", f"起始间距={starts}pt")
        else:
            add("项目符号起始间距", "strict", "NOT_APPLICABLE", "没有可比较的相邻项目符号")
        evidence = [Path(path) for path in args.visual_evidence]
        visual_ok = len(evidence) == len(pdf) and all(path.is_file() and path.stat().st_size > 10_000 for path in evidence)
        add("逐页视觉复核证据", "core", "PASS" if visual_ok else ("FAIL" if evidence else "NOT_RUN"), f"收到 {len(evidence)}/{len(pdf)} 页；每页须为真实目标产物图像")
        exported = export_evidence_status(args.word_export_log, args.pdf, args.docx or "")
        add("Word COM 导出证据", "core", exported["status"], exported["detail"])
        edited = edit_undo_status(args.edit_undo_evidence)
        add("真实 Word 编辑—撤销", "strict", edited["status"], edited["detail"])
        if args.repeat_pdf and Path(args.repeat_pdf).exists():
            with fitz.open(args.repeat_pdf) as repeat:
                result = compare_pdf_pixels(pdf, repeat)
            add("重复导出逐页像素", "strict", result["status"], result["detail"])
        else:
            add("重复导出逐页像素", "strict", "NOT_RUN", "未提供第二次 Word 导出")
        occupancy = []
        for page in pdf:
            blocks = [b for b in page.get_text("blocks") if str(b[4]).strip()]
            max_y = max((b[3] for b in blocks), default=0)
            occupancy.append(round(100 * max_y / page.rect.height, 1))
        add("末页留白", "advisory", blank_page_status(occupancy), f"逐页文字纵坐标占比={occupancy}；仅提醒")
        add("PDF 体积", "advisory", file_size_status(Path(args.pdf).stat().st_size), f"{Path(args.pdf).stat().st_size/1024/1024:.2f} MB；建议不超过 2 MB")
        pdf.close()
    else:
        for name in ("PDF 导出", "页数", "源文覆盖 PDF", "DOCX/PDF 全文一致", "PDF 真实链接", "链接双端同步", "逐页视觉复核证据", "Word COM 导出证据"):
            add(name, "core", "NOT_RUN", "无 Word 或未提供 PDF；不得用其他渲染器冒充")
        for name in ("重复导出逐页像素", "真实 Word 编辑—撤销"):
            add(name, "strict", "NOT_RUN", "未执行")
    if args.report_json:
        Path(args.report_json).write_text(json.dumps({"source": str(args.yaml), "overall": summarize(checks), "checks": checks}, ensure_ascii=False, indent=2), encoding="utf-8")
    report = report_markdown(args.report_json or args.yaml, checks)
    if args.report_md:
        Path(args.report_md).write_text(report, encoding="utf-8")
    else:
        print(report)
    if any(check["status"] == "FAIL" for check in checks):
        return 1
    if any(check["category"] == "core" and check["status"] == "NOT_RUN" for check in checks):
        return 2
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("yaml", type=Path)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--docx", type=Path)
    parser.add_argument("--repeat-pdf", type=Path)
    parser.add_argument("--pages", type=int)
    parser.add_argument("--visual-evidence", action="append", default=[])
    parser.add_argument("--word-export-log", type=Path)
    parser.add_argument("--edit-undo-evidence", type=Path)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--report-md", type=Path)
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
