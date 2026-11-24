#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""封板后派生：最终 YAML＋对应 PDF＋QA → 单文件可编辑 HTML。"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import importlib.util
import json
import mimetypes
import re
from pathlib import Path

import fitz
import yaml

VERSION = "3.3.0"
INLINE = re.compile(r"(\[\[.*?\]\]|\*\*.*?\*\*)")
DEFAULTS = {
    "name": {"font": "serif", "size": 34, "line": 40, "before": 0, "after": 6},
    "role": {"font": "sans", "size": 10.5, "line": 14, "before": 0, "after": 2},
    "contact": {"font": "sans", "size": 8, "line": 12, "before": 8, "after": 2},
    "links": {"font": "sans", "size": 8, "line": 12, "before": 0, "after": 0},
    "section": {"font": "serif", "size": 13, "line": 16.5, "before": 7.8, "after": 4.9},
    "note": {"font": "sans", "size": 8.5, "line": 12, "before": 0, "after": 2},
    "entry": {"font": "sans", "size": 9.5, "line": 14, "before": 7.8, "after": 2},
    "bullet": {"font": "sans", "size": 9.5, "line": 13.8, "before": 0, "after": 2},
    "body": {"font": "sans", "size": 9.5, "line": 13.8, "before": 0, "after": 2},
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def qa_module():
    path = Path(__file__).with_name("qa.py")
    spec = importlib.util.spec_from_file_location("resume_editor_qa", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inline_html(value) -> str:
    """只转换封板正文的 [[强调]] 与 **粗体**，其余内容全部转义。"""
    parts = []
    for token in INLINE.split(str(value or "")):
        if not token:
            continue
        if token.startswith("[[") and token.endswith("]]"):
            parts.append('<span class="accent">' + inline_html(token[2:-2]) + "</span>")
        elif token.startswith("**") and token.endswith("**"):
            parts.append("<strong>" + inline_html(token[2:-2]) + "</strong>")
        else:
            parts.append(html.escape(token, quote=False))
    return "".join(parts)


def plain_html(value) -> str:
    return html.escape(str(value or ""), quote=False)


def link_html(label, url) -> str:
    text = plain_html(label or url)
    target = html.escape(str(url or ""), quote=True)
    if not re.match(r"^(https?://|mailto:|tel:)", target, re.I):
        return text
    return f'<a href="{target}">{text}</a>'


def photo_state(meta, source_dir: Path):
    value = meta.get("photo")
    if not value:
        return None
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = source_dir / path
    if not path.is_file():
        raise FileNotFoundError(f"封板照片不存在：{path}")
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    if mime not in {"image/png", "image/jpeg"}:
        raise ValueError("编辑器照片仅支持 PNG／JPEG")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "dataUri": f"data:{mime};base64,{encoded}",
        "widthMm": 22.005,
        "heightMm": 30.7975,
        "xMm": 171.185,
        "yMm": 14.852,
    }


def state_from_data(data, source_dir: Path, pdf_path: Path):
    source_dir = Path(source_dir)
    pdf_path = Path(pdf_path)
    meta = data.get("meta") or {}
    pages = [[]]
    counter = 0

    def add(kind, value="", *, style=None, fields=None):
        nonlocal counter
        counter += 1
        block = {
            "id": f"b{counter:03d}-{kind}",
            "kind": kind,
            "html": inline_html(value) if kind not in {"name", "role", "contact", "links"} else str(value or ""),
            "style": dict(DEFAULTS.get(kind, DEFAULTS["body"]), **(style or {})),
        }
        if fields:
            block["fields"] = fields
        if block["html"] or fields:
            pages[-1].append(block)
        return block

    add("name", plain_html(meta.get("name")))
    add("role", plain_html(meta.get("role")))
    contacts = []
    for value in meta.get("contact") or []:
        if isinstance(value, dict):
            contacts.append(link_html(value.get("t") or value.get("u") or value.get("url"), value.get("u") or value.get("url")))
        elif str(value).strip():
            contacts.append(plain_html(value))
    if contacts:
        add("contact", '<span style="color:#5A6069">' + " · ".join(contacts) + "</span>")
    links = []
    for item in meta.get("links") or []:
        url = item.get("url") or item.get("u")
        label = str(item.get("label") or "").strip()
        short = str(item.get("short") or url or "").strip()
        text = (label + " " if label else "") + short
        if text and url:
            links.append(link_html(text, url))
    if links:
        add("links", "  ·  ".join(links))

    for section in data.get("sections") or []:
        if section.get("page_break_before"):
            if pages[-1]:
                pages.append([])
        section_style = {"before": 14.9, "after": 7.9} if len(pages) == 1 and not any(b["kind"] == "section" for b in pages[-1]) else {}
        section_block = add("section", section.get("title"), style=section_style)
        if section.get("note"):
            section_block["fields"] = {"note": inline_html(section.get("note"))}
        add("body", section.get("body"))
        for bullet in section.get("bullets") or []:
            add("bullet", bullet.get("text") if isinstance(bullet, dict) else bullet)
        for item in section.get("items") or []:
            fields = {
                "org": inline_html(item.get("org") or item.get("name")),
                "role": inline_html(item.get("role")),
                "date": inline_html(item.get("date")),
            }
            if item.get("url"):
                fields["url"] = str(item["url"])
            add("entry", fields=fields)
            for bullet in item.get("bullets") or []:
                add("bullet", bullet.get("text") if isinstance(bullet, dict) else bullet)
    pages = [page for page in pages if page]
    return {
        "schema": "resume-editor-state/v1",
        "revision": str((data.get("delivery") or {}).get("version") or "v3.3.0") + "-微调.1",
        "accent": "#2F5BEA",
        "base": {"yamlSha256": "", "pdfSha256": sha256(pdf_path)},
        "photo": photo_state(meta, source_dir),
        "pages": pages,
    }


def validate_freeze(data, pdf_path: Path, qa_path: Path):
    if not pdf_path.is_file():
        raise RuntimeError(f"封板 PDF 不存在：{pdf_path}")
    if not qa_path.is_file():
        raise RuntimeError(f"封板 QA 不存在：{qa_path}")
    report = json.loads(qa_path.read_text(encoding="utf-8"))
    blocking = [check for check in report.get("checks") or [] if check.get("category") in {"core", "strict"} and check.get("status") in {"FAIL", "NOT_RUN"}]
    if blocking:
        names = "；".join(f"{check.get('name')}={check.get('status')}" for check in blocking[:8])
        raise RuntimeError(f"封板 QA 仍有阻断：{names}")
    qa = qa_module()
    try:
        with fitz.open(pdf_path) as pdf:
            text = "\n".join(page.get_text("text", sort=False) for page in pdf)
    except Exception as exc:
        raise RuntimeError(f"PDF 内容覆盖检查无法读取：{exc}") from exc
    missing = qa.coverage(qa.content_atoms(data), text)
    if missing:
        raise RuntimeError(f"PDF 内容覆盖不足，可能不是此 YAML 的封板稿：{missing[:8]}")
    if not text.strip():
        raise RuntimeError("PDF 内容覆盖检查失败：文本层为空")


def build_editor(yaml_path, pdf_path, qa_path, output_path, docx_path=None):
    yaml_path = Path(yaml_path)
    pdf_path = Path(pdf_path)
    qa_path = Path(qa_path)
    output_path = Path(output_path)
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    validate_freeze(data, pdf_path, qa_path)
    state = state_from_data(data, yaml_path.parent, pdf_path)
    state["base"]["yamlSha256"] = sha256(yaml_path)
    docx_path = Path(docx_path) if docx_path else pdf_path.with_suffix(".docx")
    if docx_path.is_file():
        from docx import Document
        document = Document(docx_path)
        docx_text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        qa = qa_module()
        missing = qa.coverage(qa.content_atoms(data), docx_text)
        if missing:
            raise RuntimeError(f"封板 DOCX 与 YAML 内容不一致：{missing[:8]}")
        block_count = sum(len(page) for page in state["pages"])
        if len(document.paragraphs) != block_count:
            raise RuntimeError(f"封板 DOCX 段落数 {len(document.paragraphs)} 与编辑器区块数 {block_count} 不一致，不能原位导出")
        state["base"]["docxSha256"] = sha256(docx_path)
        state["base"]["docxBase64"] = base64.b64encode(docx_path.read_bytes()).decode("ascii")
    else:
        state["base"]["docxSha256"] = ""
        state["base"]["docxBase64"] = ""
    root = Path(__file__).resolve().parents[1]
    template = (root / "assets/editor-template.html").read_text(encoding="utf-8")
    runtime = (root / "assets/editor-runtime.js").read_text(encoding="utf-8")
    jszip = (root / "assets/vendor/jszip.min.js").read_text(encoding="utf-8")
    license_text = (root / "licenses/jszip-LICENSE").read_text(encoding="utf-8")
    jszip_with_license = "/*\n" + license_text.replace("*/", "* /") + "\n*/\n" + jszip
    state_json = json.dumps(state, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    result = template.replace("/*__RESUME_DATA__*/", state_json)
    result = result.replace("/*__JSZIP__*/", jszip_with_license.replace("</script", "<\\/script"))
    result = result.replace("/*__EDITOR_RUNTIME__*/", runtime.replace("</script", "<\\/script"))
    if "/*__" in result:
        raise RuntimeError("编辑器模板仍有未替换占位符")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result, encoding="utf-8")
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("yaml", help="与封板 PDF 对应的最终结构化 YAML")
    parser.add_argument("--pdf", required=True, help="已验收的封板 PDF")
    parser.add_argument("--docx", help="对应的封板 DOCX；默认取 PDF 同名文件，用于原位导出最新修改")
    parser.add_argument("--qa", required=True, help="封板 QA JSON；core／strict 不得 FAIL 或 NOT_RUN")
    parser.add_argument("--output", required=True, help="输出的单文件 HTML")
    args = parser.parse_args()
    state = build_editor(args.yaml, args.pdf, args.qa, args.output, args.docx)
    print(json.dumps({
        "version": VERSION,
        "output": str(Path(args.output).resolve()),
        "pages": len(state["pages"]),
        "blocks": sum(len(page) for page in state["pages"]),
        "photo": bool(state["photo"]),
        "docxTemplate": bool(state["base"].get("docxBase64")),
        "pdfSha256": state["base"]["pdfSha256"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
