#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""resume-master v2 · YAML → 可编辑 DOCX →（可选）Microsoft Word PDF。

DOCX 是 Word 路线的唯一排版源；HTML／浏览器不参与该路线的 PDF 导出。
不安装字体、不修改注册表、不修改 Word 全局选项。
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess

import yaml
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Mm, Pt, RGBColor
from docx.text.run import Run

HERE = Path(__file__).resolve().parent


def _rgb(value, default="16181D"):
    value = str(value or default).lstrip("#")
    return RGBColor.from_string(value if len(value) == 6 else default)


def _style(data):
    raw = dict(data.get("style") or {})
    raw.update(data.get("word") or {})
    return {
        "east": raw.get("font_east_asia") or "Microsoft YaHei",
        "latin": raw.get("font_latin") or "Arial",
        "accent": raw.get("accent") or "#2F5BEA",
        "body": float(raw.get("body_size") or 9.5),
        "lead": float(raw.get("lead") or 1.42),
        "name": float(raw.get("name_size") or 22),
        "role": float(raw.get("role_size") or 10.5),
        "section": float(raw.get("section_size") or 10.5),
        "entry": float(raw.get("entry_size") or 10),
        "meta": float(raw.get("meta_size") or 8),
        "margins": raw.get("margins") or {},
    }


def _soft_breaks(text):
    """给长拉丁 token 一个不可见断行机会；目标 URL 与 YAML 原文不变。"""
    return str(text or "").replace("/\u200b", "/").replace("/", "/\u200b")


def _font(run, cfg, size=None, bold=None, color=None, italic=None):
    size = float(size or cfg["body"])
    run.text = _soft_breaks(run.text)
    run.font.name = cfg["latin"]
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    run.font.color.rgb = _rgb(color or "2A2F38")
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.rFonts
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    for attr, value in (("ascii", cfg["latin"]), ("hAnsi", cfg["latin"]), ("eastAsia", cfg["east"]), ("cs", cfg["latin"])):
        fonts.set(qn(f"w:{attr}"), value)
    fonts.set(qn("w:hint"), "eastAsia")
    return run


def _para(container, cfg, size=None, before=0, after=0, lead=None, keep_next=False, keep=True):
    p = container.add_paragraph()
    fmt = p.paragraph_format
    size = float(size or cfg["body"])
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    fmt.line_spacing = Pt(size * float(lead or cfg["lead"]))
    fmt.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    fmt.keep_with_next = keep_next
    fmt.keep_together = keep
    fmt.widow_control = True
    return p


def _reuse_or_para(container, cfg, **kwargs):
    paragraphs = getattr(container, "paragraphs", [])
    if paragraphs and not paragraphs[0].text and len(paragraphs[0].runs) == 0:
        p = paragraphs[0]
        fmt = p.paragraph_format
        size = float(kwargs.get("size") or cfg["body"])
        fmt.space_before = Pt(kwargs.get("before", 0))
        fmt.space_after = Pt(kwargs.get("after", 0))
        fmt.line_spacing = Pt(size * float(kwargs.get("lead") or cfg["lead"]))
        fmt.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        fmt.keep_with_next = kwargs.get("keep_next", False)
        fmt.keep_together = kwargs.get("keep", True)
        fmt.widow_control = True
        return p
    return _para(container, cfg, **kwargs)


def _markdown(p, text, cfg, size=None, color=None, force_bold=False):
    parts = re.split(r"(\*\*.*?\*\*)", str(text or ""))
    for part in parts:
        if not part:
            continue
        bold = force_bold or (part.startswith("**") and part.endswith("**"))
        value = part[2:-2] if part.startswith("**") and part.endswith("**") else part
        _font(p.add_run(value), cfg, size=size, bold=bold, color=color)
    return p


def _hyperlink(p, text, url, cfg, size=None, color=None):
    rel_id = p.part.relate_to(str(url), RT.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), rel_id)
    new_run = OxmlElement("w:r")
    hyperlink.append(new_run)
    p._p.append(hyperlink)
    run = Run(new_run, p)
    run.text = str(text)
    _font(run, cfg, size=size, color=color or cfg["accent"])
    run.underline = False
    return run


def _bottom_border(p, color="1F2328", size=6, space=3):
    ppr = p._p.get_or_add_pPr()
    borders = ppr.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        ppr.append(borders)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:space"), str(space))
    bottom.set(qn("w:color"), color)
    borders.append(bottom)


def _cell_margins(cell, top=0, start=0, bottom=0, end=0):
    tcpr = cell._tc.get_or_add_tcPr()
    margins = tcpr.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar")
        tcpr.append(margins)
    for name, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = margins.find(qn(f"w:{name}"))
        if node is None:
            node = OxmlElement(f"w:{name}")
            margins.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def _table_no_borders(table):
    tblpr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        node = OxmlElement(f"w:{edge}")
        node.set(qn("w:val"), "nil")
        borders.append(node)
    tblpr.append(borders)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblpr.append(layout)


def _field(p, instruction, cfg):
    run = p.add_run()
    _font(run, cfg, size=7, color="7A818C")
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for el in (begin, instr, separate, text, end):
        run._r.append(el)


def _header(doc, data, cfg):
    meta = data.get("meta") or {}
    photo = meta.get("photo")
    has_photo = bool(photo and Path(photo).is_file() and float(meta.get("photo_w") or 25) > 0)
    if has_photo:
        table = doc.add_table(rows=1, cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.LEFT
        table.autofit = False
        _table_no_borders(table)
        section = doc.sections[0]
        total = section.page_width - section.left_margin - section.right_margin
        photo_width = Mm(float(meta.get("photo_w") or 25))
        table.columns[0].width = total - photo_width - Mm(4)
        table.columns[1].width = photo_width + Mm(4)
        left, right = table.rows[0].cells
        left.width = table.columns[0].width
        right.width = table.columns[1].width
        for cell in (left, right):
            _cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
        photo_p = right.paragraphs[0]
        photo_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        photo_p.paragraph_format.space_after = Pt(0)
        photo_p.paragraph_format.line_spacing = 1.0
        photo_p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        # 只给宽度，高度由 Word 按原图比例计算，避免拉伸。
        photo_p.add_run().add_picture(str(photo), width=photo_width)
    else:
        left = doc

    p = _reuse_or_para(left, cfg, size=cfg["name"], after=2, lead=1.0, keep_next=True)
    _font(p.add_run(str(meta.get("name") or "")), cfg, size=cfg["name"], bold=True, color="14161A")
    if meta.get("role"):
        p = _para(left, cfg, size=cfg["role"], after=4, lead=1.1, keep_next=True)
        _font(p.add_run(str(meta["role"])), cfg, size=cfg["role"], color=cfg["accent"])

    contacts = meta.get("contact") or []
    if contacts:
        p = _para(left, cfg, size=cfg["meta"], after=1, lead=1.35, keep_next=True)
        for index, item in enumerate(contacts):
            if index:
                _font(p.add_run("  ·  "), cfg, size=cfg["meta"], color="9AA1AB")
            if isinstance(item, dict):
                text = item.get("t") or ""
                if item.get("br"):
                    p.add_run().add_break()
                if item.get("u"):
                    _hyperlink(p, text, item["u"], cfg, size=cfg["meta"], color="5C636E")
                else:
                    _font(p.add_run(str(text)), cfg, size=cfg["meta"], color="5C636E")
            else:
                _font(p.add_run(str(item)), cfg, size=cfg["meta"], color="5C636E")

    links = meta.get("links") or []
    if links:
        p = _para(left, cfg, size=cfg["meta"], after=2, lead=1.35, keep_next=True)
        for index, link in enumerate(links):
            if index:
                _font(p.add_run("  ·  "), cfg, size=cfg["meta"], color="9AA1AB")
            if link.get("label"):
                _font(p.add_run(str(link["label"]) + " "), cfg, size=cfg["meta"], color="5C636E")
            _hyperlink(p, link.get("short") or link.get("url") or "", link.get("url") or "", cfg, size=cfg["meta"])

    stats = meta.get("stats") or []
    if stats:
        p = _para(left, cfg, size=cfg["meta"], before=2, after=2, lead=1.3, keep_next=True)
        for index, stat in enumerate(stats):
            if index:
                _font(p.add_run("   ·   "), cfg, size=cfg["meta"], color="C9CDD3")
            _font(p.add_run(str(stat.get("n") or "")), cfg, size=cfg["body"] + 0.5, bold=True, color="16181D")
            _font(p.add_run(" " + str(stat.get("l") or "")), cfg, size=cfg["meta"], color="5C636E")

    if meta.get("lede"):
        p = _para(doc if has_photo else left, cfg, size=cfg["body"], before=3, after=2, lead=1.5)
        _markdown(p, meta["lede"], cfg, size=cfg["body"], color="3A4048")


def _entry(doc, item, cfg, available_pt):
    p = _para(doc, cfg, size=cfg["entry"], before=2, after=1, lead=1.25, keep_next=True)
    p.paragraph_format.tab_stops.add_tab_stop(Pt(available_pt), WD_TAB_ALIGNMENT.RIGHT)
    logo = item.get("logo")
    if logo and Path(logo).is_file():
        # 条目不在固定高度表格中，避免行内 Logo 撑坏整行或被裁切。
        p.add_run().add_picture(str(logo), height=Mm(3.5))
        p.add_run(" ")
    _font(p.add_run(str(item.get("org") or "")), cfg, size=cfg["entry"], bold=True, color="16181D")
    if item.get("role"):
        _font(p.add_run("  ·  " + str(item["role"])), cfg, size=cfg["body"], color="5C636E")
    if item.get("date"):
        _font(p.add_run("\t" + str(item["date"])), cfg, size=cfg["meta"], color="7A818C")
    link_value = item.get("link") or item.get("url")
    if link_value:
        link_p = p
        if item.get("date"):
            # 日期与链接同时存在时，链接另起一行，不能因栏位冲突丢内容。
            link_p = _para(doc, cfg, size=cfg["meta"], after=1, lead=1.1, keep_next=True)
            link_p.paragraph_format.tab_stops.add_tab_stop(Pt(available_pt), WD_TAB_ALIGNMENT.RIGHT)
        link = link_value
        if isinstance(link, dict):
            text, url = link.get("text") or link.get("url") or "", link.get("url") or ""
        else:
            text = url = str(link)
        _font(link_p.add_run("\t"), cfg, size=cfg["meta"])
        if url:
            _hyperlink(link_p, text, url, cfg, size=cfg["meta"])
        else:
            _font(link_p.add_run(text), cfg, size=cfg["meta"], color="9AA1AB")
    for bullet in item.get("bullets") or []:
        _bullet(doc, bullet, cfg)


def _bullet(doc, text, cfg):
    p = _para(doc, cfg, size=cfg["body"], after=0.7, lead=cfg["lead"], keep=True)
    p.paragraph_format.left_indent = Mm(4)
    p.paragraph_format.first_line_indent = Mm(-4)
    _font(p.add_run("• "), cfg, size=cfg["body"], color=cfg["accent"])
    _markdown(p, text, cfg, size=cfg["body"], color="2A2F38")
    return p


def build_docx(data, out_path):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cfg = _style(data)
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)
    margins = {"left": 17, "right": 17, "top": 14, "bottom": 12}
    margins.update(cfg["margins"])
    section.left_margin, section.right_margin = Mm(float(margins["left"])), Mm(float(margins["right"]))
    section.top_margin, section.bottom_margin = Mm(float(margins["top"])), Mm(float(margins["bottom"]))
    section.header_distance, section.footer_distance = Mm(5), Mm(5)

    normal = doc.styles["Normal"]
    normal.font.name = cfg["latin"]
    normal.font.size = Pt(cfg["body"])
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), cfg["east"])
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.line_spacing = Pt(cfg["body"] * cfg["lead"])

    doc.core_properties.title = str((data.get("meta") or {}).get("name") or "resume")
    doc.core_properties.subject = "resume-master v2 · single-source DOCX"
    _header(doc, data, cfg)
    available_pt = (section.page_width - section.left_margin - section.right_margin) / 12700
    for sec in data.get("sections") or []:
        p = _para(doc, cfg, size=cfg["section"], before=6, after=3, lead=1.2, keep_next=True)
        if sec.get("page_break_before"):
            p.paragraph_format.page_break_before = True
        _font(p.add_run(str(sec.get("title") or "")), cfg, size=cfg["section"], bold=True, color="16181D")
        if sec.get("note"):
            _font(p.add_run("  " + str(sec["note"])), cfg, size=cfg["meta"], color="9AA1AB")
        _bottom_border(p)
        if sec.get("body"):
            p = _para(doc, cfg, size=cfg["body"], after=1, keep_next=True)
            _markdown(p, sec["body"], cfg, size=cfg["body"])
        for item in sec.get("items") or []:
            _entry(doc, item, cfg, available_pt)
        for bullet in sec.get("bullets") or []:
            _bullet(doc, bullet, cfg)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _field(footer, "PAGE", cfg)
    _font(footer.add_run(" / "), cfg, size=7, color="7A818C")
    _field(footer, "NUMPAGES", cfg)

    settings = doc.settings._element
    update = settings.find(qn("w:updateFields"))
    if update is None:
        update = OxmlElement("w:updateFields")
        settings.append(update)
    update.set(qn("w:val"), "true")
    overflow = settings.find(qn("w:overflowPunct"))
    if overflow is None:
        overflow = OxmlElement("w:overflowPunct")
        settings.append(overflow)
    overflow.set(qn("w:val"), "false")

    temp = out_path.with_name(out_path.stem + ".tmp.docx")
    doc.save(temp)
    os.replace(temp, out_path)
    return out_path


def subset_pdf_fonts(pdf_path):
    """只对 Word 已导出的 PDF 做无损字体子集化；不改文字、链接或页面。"""
    import fitz

    pdf_path = Path(pdf_path)
    temp = pdf_path.with_name(pdf_path.stem + ".subset.tmp.pdf")
    doc = fitz.open(pdf_path)
    try:
        doc.subset_fonts(verbose=False)
        doc.save(temp, garbage=4, deflate=True)
    finally:
        doc.close()
    os.replace(temp, pdf_path)
    return pdf_path


def export_pdf_with_word(docx_path, pdf_path, timeout=180):
    """用本机 Microsoft Word 导出；不借浏览器或系统打印驱动冒充。"""
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        raise RuntimeError("需要 Windows Microsoft Word 与 PowerShell；当前环境不能执行 Word 同源导出")
    script = HERE / "export_word.ps1"
    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [shell, "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File", str(script),
         "-Docx", str(Path(docx_path).resolve()), "-Pdf", str(pdf_path.resolve())],
        capture_output=True, text=True, encoding="utf-8", timeout=timeout,
    )
    if proc.returncode or not pdf_path.is_file() or pdf_path.stat().st_size < 1000:
        raise RuntimeError(f"Word 导出失败（{proc.returncode}）：{proc.stdout}\n{proc.stderr}")
    subset_pdf_fonts(pdf_path)
    return pdf_path


def _resolve_assets(data, base):
    def fix(value):
        if not value:
            return value
        return str(Path(value) if Path(value).is_absolute() else (base / value).resolve())
    meta = data.setdefault("meta", {})
    meta["photo"] = fix(meta.get("photo"))
    for sec in data.get("sections") or []:
        for item in sec.get("items") or []:
            item["logo"] = fix(item.get("logo"))
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("yaml_path")
    ap.add_argument("-o", "--out")
    ap.add_argument("--pdf", help="由 Microsoft Word 从同一 DOCX 导出 PDF")
    ap.add_argument("--repeat-pdf", help="同参数第二次导出，供 QA 做逐页像素比较")
    args = ap.parse_args()
    source = Path(args.yaml_path).resolve()
    with source.open(encoding="utf-8") as f:
        data = _resolve_assets(yaml.safe_load(f) or {}, source.parent)
    out = Path(args.out) if args.out else source.with_suffix(".docx")
    build_docx(data, out)
    print(f"OK DOCX  {out.resolve()}")
    if args.repeat_pdf and not args.pdf:
        ap.error("--repeat-pdf 需要同时提供 --pdf")
    if args.pdf:
        export_pdf_with_word(out, args.pdf)
        print(f"OK PDF   {Path(args.pdf).resolve()}（Microsoft Word）")
    if args.repeat_pdf:
        export_pdf_with_word(out, args.repeat_pdf)
        print(f"OK REPEAT {Path(args.repeat_pdf).resolve()}（Microsoft Word）")


if __name__ == "__main__":
    main()
