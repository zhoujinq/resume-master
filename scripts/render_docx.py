#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""唯一生产路线：证据 YAML → 可编辑 DOCX → Microsoft Word PDF。"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
from pathlib import Path

import fitz
import yaml
from docx import Document
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Mm
from PIL import Image

SERIF = "思源宋体"
SANS = "思源黑体"
ACCENT = "2F5BEA"
INK = "141519"
BODY = "2B3038"
MUTED = "5A6069"
DATE_GRAY = "857F74"
RULE = "1A1D22"
HAIR = "9C9D9F"
BLACK = "000000"
BODY_PT = 9.5
PHOTO_CX = 792480
PHOTO_CY = 1108710
PHOTO_X = 6160770
PHOTO_Y = 534670
INLINE = re.compile(r"(\[\[.*?\]\]|\*\*.*?\*\*)")
PAGE_CONTENT_TWIPS = 9978


def _module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def child(parent, tag):
    found = parent.find(qn(tag))
    if found is None:
        found = OxmlElement(tag)
        parent.append(found)
    return found


def validate_style_contract(data):
    if data.get("style"):
        raise ValueError("v3 不接受 style／字体／颜色／字号覆盖；请修改内容，不修改唯一视觉标准")
    for key in ("route", "renderer", "theme"):
        if key in data:
            raise ValueError(f"v3 不接受渲染路线字段 {key}")


def set_run(run, size, family=SANS, bold=False, color=BODY, underline=False, spacing=None):
    rpr = run._r.get_or_add_rPr()
    fonts = child(rpr, "w:rFonts")
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(f"w:{attr}"), family)
    fonts.set(qn("w:hint"), "eastAsia")
    child(rpr, "w:sz").set(qn("w:val"), str(int(round(size * 2))))
    child(rpr, "w:szCs").set(qn("w:val"), str(int(round(size * 2))))
    child(rpr, "w:color").set(qn("w:val"), color)
    if bold:
        child(rpr, "w:b").set(qn("w:val"), "1")
        child(rpr, "w:bCs").set(qn("w:val"), "1")
    if underline:
        child(rpr, "w:u").set(qn("w:val"), "single")
    if spacing is not None:
        child(rpr, "w:spacing").set(qn("w:val"), str(int(round(spacing * 20))))
    lang = child(rpr, "w:lang")
    lang.set(qn("w:val"), "zh-CN")
    lang.set(qn("w:eastAsia"), "zh-CN")
    child(rpr, "w:noProof")
    return run


def fmt(paragraph, before=0, after=0, line=13.8, keep_next=False, align="both",
        left=0, right=0, hanging=None, tabs=None, num=None):
    ppr = paragraph._p.get_or_add_pPr()
    if num is not None:
        numpr = child(ppr, "w:numPr")
        child(numpr, "w:ilvl").set(qn("w:val"), "0")
        child(numpr, "w:numId").set(qn("w:val"), str(num))
    spacing = child(ppr, "w:spacing")
    spacing.set(qn("w:before"), str(int(round(before * 20))))
    spacing.set(qn("w:after"), str(int(round(after * 20))))
    spacing.set(qn("w:line"), str(int(round(line * 20))))
    spacing.set(qn("w:lineRule"), "exact")
    child(ppr, "w:jc").set(qn("w:val"), align)
    ind = child(ppr, "w:ind")
    ind.set(qn("w:left"), str(int(left)))
    ind.set(qn("w:right"), str(int(right)))
    ind.set(qn("w:firstLine"), "0")
    if hanging is not None:
        ind.set(qn("w:hanging"), str(int(hanging)))
    child(ppr, "w:autoSpaceDE").set(qn("w:val"), "0")
    child(ppr, "w:autoSpaceDN").set(qn("w:val"), "0")
    child(ppr, "w:snapToGrid").set(qn("w:val"), "0")
    if keep_next:
        child(ppr, "w:keepNext")
    if tabs:
        tabs_el = child(ppr, "w:tabs")
        for value, position in tabs:
            tab = OxmlElement("w:tab")
            tab.set(qn("w:val"), value)
            tab.set(qn("w:pos"), str(int(position)))
            tabs_el.append(tab)
    return paragraph


def border(paragraph, size, color, space, right_indent=None):
    ppr = paragraph._p.get_or_add_pPr()
    if right_indent is not None:
        child(ppr, "w:ind").set(qn("w:right"), str(right_indent))
    pbdr = child(ppr, "w:pBdr")
    bottom = child(pbdr, "w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:space"), str(space))
    bottom.set(qn("w:color"), color)


def inline(paragraph, text, size=BODY_PT, family=SANS, color=BODY):
    for part in INLINE.split(str(text or "")):
        if not part:
            continue
        if part.startswith("[[") and part.endswith("]]"):
            set_run(paragraph.add_run(part[2:-2]), size, family, bold=True, color=ACCENT)
        elif part.startswith("**") and part.endswith("**"):
            set_run(paragraph.add_run(part[2:-2]), size, family, bold=True, color=INK)
        else:
            set_run(paragraph.add_run(part), size, family, color=color)


def hyperlink(paragraph, text, url, size, color=BLACK):
    rid = paragraph.part.relate_to(str(url), RT.HYPERLINK, is_external=True)
    node = OxmlElement("w:hyperlink")
    node.set(qn("r:id"), rid)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    fonts = OxmlElement("w:rFonts")
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(f"w:{attr}"), SANS)
    rpr.append(fonts)
    for tag, value in (("w:b", "1"), ("w:bCs", "1"), ("w:color", color), ("w:u", "single"),
                       ("w:sz", str(int(round(size * 2)))), ("w:szCs", str(int(round(size * 2))))):
        element = OxmlElement(tag)
        element.set(qn("w:val"), value)
        rpr.append(element)
    run.append(rpr)
    text_node = OxmlElement("w:t")
    text_node.set(qn("xml:space"), "preserve")
    text_node.text = str(text)
    run.append(text_node)
    node.append(run)
    paragraph._p.append(node)


def configure_section(section, top, bottom):
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.left_margin = Mm(17)
    section.right_margin = Mm(17)
    section.top_margin = Mm(top)
    section.bottom_margin = Mm(bottom)
    section.header_distance = Mm(5)
    section.footer_distance = Mm(5)
    section._sectPr.remove_all("w:headerReference")
    section._sectPr.remove_all("w:footerReference")


def new_page(doc):
    section = doc.add_section(WD_SECTION.NEW_PAGE)
    configure_section(section, 18, 18)
    fmt(doc.paragraphs[-1], line=1, align="left")
    return section


def resolve(base, value):
    if not value:
        return None
    path = Path(str(value)).expanduser()
    return path if path.is_absolute() else base / path


def float_picture(run, relative_h, pos_h, relative_v, pos_v):
    drawing = run._r.find(qn("w:drawing"))
    inline_node = drawing.find(qn("wp:inline")) if drawing is not None else None
    if inline_node is None:
        raise ValueError("标准图片结构缺失")
    children = list(inline_node)
    anchor = parse_xml(
        f'<wp:anchor {nsdecls("wp")} distT="0" distB="0" distL="0" distR="0" '
        'simplePos="0" relativeHeight="251659264" behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1"/>'
    )
    simple = OxmlElement("wp:simplePos")
    simple.set("x", "0")
    simple.set("y", "0")
    anchor.append(simple)
    for tag, relative, offset in (("wp:positionH", relative_h, pos_h), ("wp:positionV", relative_v, pos_v)):
        position = OxmlElement(tag)
        position.set("relativeFrom", relative)
        value = OxmlElement("wp:posOffset")
        value.text = str(offset)
        position.append(value)
        anchor.append(position)
    for tag in ("wp:extent", "wp:effectExtent"):
        node = inline_node.find(qn(tag))
        if node is None:
            node = OxmlElement(tag)
            for attr in ("l", "t", "r", "b"):
                node.set(attr, "0")
        anchor.append(node)
    anchor.append(OxmlElement("wp:wrapNone"))
    for child_node in children:
        if child_node.tag not in {qn("wp:extent"), qn("wp:effectExtent")}:
            anchor.append(child_node)
    drawing.remove(inline_node)
    drawing.append(anchor)


def add_photo(paragraph, path):
    run = paragraph.add_run()
    run.add_picture(str(path), width=PHOTO_CX, height=PHOTO_CY)
    float_picture(run, "page", PHOTO_X, "page", PHOTO_Y)


def add_logo(paragraph, path, width_mm):
    width_mm = float(width_mm or 5.6)
    with Image.open(path) as image:
        cx = int(round(width_mm * 36000))
        cy = int(round(width_mm * image.height / image.width * 36000))
    run = paragraph.add_run()
    run.add_picture(str(path), width=cx, height=cy)
    float_picture(run, "margin", 0, "paragraph", 0)
    return int(round((width_mm + 2.2) * 56.6929))


def add_header(doc, meta, base):
    name = fmt(doc.add_paragraph(), after=6, line=40, keep_next=True, align="left")
    set_run(name.add_run(str(meta.get("name") or "")), 34, SERIF, bold=True, color=INK, spacing=2.7)
    photo = resolve(base, meta.get("photo"))
    if photo:
        if not photo.is_file():
            raise FileNotFoundError(f"照片不存在：{photo}")
        add_photo(name, photo)

    role = fmt(doc.add_paragraph(), after=2, line=14, keep_next=True, align="left")
    border(role, 7, RULE, 6, 2778 if photo else 0)
    set_run(role.add_run(str(meta.get("role") or "")), 10.5, SANS, bold=True, color=ACCENT)

    contact = fmt(doc.add_paragraph(), before=8, after=2, line=12, keep_next=True, align="left")
    for index, value in enumerate(meta.get("contact") or []):
        if index:
            set_run(contact.add_run(" · "), 8, SANS, color=MUTED)
        if isinstance(value, dict):
            hyperlink(contact, value.get("t") or value.get("url"), value.get("u") or value.get("url"), 8, color=MUTED)
        else:
            set_run(contact.add_run(str(value)), 8, SANS, color=MUTED)

    links = fmt(doc.add_paragraph(), line=12, keep_next=True, align="left")
    for index, item in enumerate(meta.get("links") or []):
        if index:
            set_run(links.add_run("  ·  "), 8, SANS, color=MUTED)
        icon = resolve(base, item.get("icon"))
        if icon:
            run = links.add_run()
            run.add_picture(str(icon), width=Mm(3.5), height=Mm(3.5))
            set_run(run, 8, SANS, bold=True, color=INK)
            set_run(links.add_run(" "), 8, SANS, bold=True, color=INK)
        label = str(item.get("label") or "").strip()
        url = str(item.get("url") or item.get("u") or "")
        text = (label + " " if label else "") + str(item.get("short") or url)
        hyperlink(links, text, url, 8)


def add_section_heading(doc, section, page_index):
    heading = fmt(doc.add_paragraph(), before=14.87 if page_index == 1 else 7.84,
                  after=7.87 if page_index == 1 else 4.9, line=16.5, keep_next=True,
                  align="left", tabs=[("right", PAGE_CONTENT_TWIPS)] if section.get("note") else None)
    set_run(heading.add_run(str(section.get("title") or "")), 13, SERIF, bold=True, color=INK, spacing=1.0)
    if section.get("note"):
        heading.add_run()._r.append(OxmlElement("w:tab"))
        set_run(heading.add_run(str(section["note"])), 8, SANS, color=MUTED)
    border(heading, 4, HAIR, 3)


def add_body(doc, text):
    paragraph = fmt(doc.add_paragraph(), line=13.8, keep_next=True)
    inline(paragraph, text)


def add_item(doc, item, base, project=False, page_index=1, first=False):
    if project and page_index > 1:
        before = 3.16 if first else 3.57
    elif page_index == 1:
        before = 7.87 if first else 10.24
    else:
        before = 4.7 if first else 5.27
    line = fmt(doc.add_paragraph(), before=before, after=0 if project or page_index > 1 else 0.5,
               line=13.8, keep_next=True, align="left", tabs=[("right", PAGE_CONTENT_TWIPS)])
    logo = resolve(base, item.get("logo"))
    if logo:
        indent = add_logo(line, logo, item.get("logo_width") or 5.6)
        child(line._p.get_or_add_pPr(), "w:ind").set(qn("w:left"), str(indent))
    set_run(line.add_run(str(item.get("org") or item.get("name") or "")), 8.5 if project else 10, SANS, bold=True, color=INK)
    if item.get("role"):
        set_run(line.add_run(" — "), 8.5, SANS, color=MUTED)
        set_run(line.add_run(str(item["role"])), 8.5, SANS, color=MUTED)
    line.add_run()._r.append(OxmlElement("w:tab"))
    if item.get("url"):
        hyperlink(line, str(item["url"]), str(item["url"]), 8.5)
        if item.get("date"):
            set_run(line.add_run("  "), 8, SERIF, color=DATE_GRAY)
    if item.get("date"):
        set_run(line.add_run(str(item["date"])), 8, SERIF, color=DATE_GRAY)


def add_bullet(doc, bullet, page_index=1, first=False, project=False):
    text = bullet["text"] if isinstance(bullet, dict) else str(bullet)
    if first and project and page_index > 1:
        before = 3.29
    elif first and page_index > 1:
        before = 1.65
    else:
        before = 3.2
    paragraph = fmt(doc.add_paragraph(), before=before, line=13.8, left=238, hanging=238, num=90)
    inline(paragraph, text)


def setup_document():
    doc = Document()
    configure_section(doc.sections[0], 14, 18)
    settings = doc.settings._element
    child(settings, "w:doNotAutoCompressPictures")
    compat = child(settings, "w:compat")
    mode = OxmlElement("w:compatSetting")
    mode.set(qn("w:name"), "compatibilityMode")
    mode.set(qn("w:uri"), "http://schemas.microsoft.com/office/word")
    mode.set(qn("w:val"), "15")
    compat.append(mode)
    theme = child(settings, "w:themeFontLang")
    theme.set(qn("w:val"), "zh-CN")
    theme.set(qn("w:eastAsia"), "zh-CN")
    styles = doc.styles.element
    defaults = child(child(child(styles, "w:docDefaults"), "w:rPrDefault"), "w:rPr")
    fonts = child(defaults, "w:rFonts")
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(f"w:{attr}"), SANS)
    child(defaults, "w:sz").set(qn("w:val"), "19")
    child(defaults, "w:szCs").set(qn("w:val"), "19")
    numbering = doc.part.numbering_part.element
    abstract = parse_xml(
        '<w:abstractNum %s w:abstractNumId="90"><w:multiLevelType w:val="singleLevel"/>'
        '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="▪"/><w:lvlJc w:val="left"/>'
        '<w:pPr><w:ind w:left="238" w:hanging="238"/></w:pPr>'
        f'<w:rPr><w:rFonts w:ascii="{SANS}" w:hAnsi="{SANS}" w:eastAsia="{SANS}" w:hint="eastAsia"/>'
        f'<w:color w:val="{ACCENT}"/><w:sz w:val="19"/><w:szCs w:val="19"/></w:rPr></w:lvl></w:abstractNum>' % nsdecls("w")
    )
    numbering.append(abstract)
    numbering.append(parse_xml('<w:num %s w:numId="90"><w:abstractNumId w:val="90"/></w:num>' % nsdecls("w")))
    return doc


def build_docx(data, out, base_dir=None):
    validate_style_contract(data)
    errors = _module("evidence").validate_resume(data)
    if errors:
        raise ValueError("证据校验失败：\n" + "\n".join(errors))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    base = Path(base_dir) if base_dir else Path.cwd()
    doc = setup_document()
    add_header(doc, data.get("meta") or {}, base)
    page_index = 1
    for section in data.get("sections") or []:
        if section.get("page_break_before"):
            new_page(doc)
            page_index += 1
        add_section_heading(doc, section, page_index)
        if section.get("body"):
            add_body(doc, section["body"])
        for bullet in section.get("bullets") or []:
            add_bullet(doc, bullet, page_index=page_index)
        project = section.get("variant") == "project"
        for item in section.get("items") or []:
            add_item(doc, item, base, project=project, page_index=page_index,
                     first=item is (section.get("items") or [None])[0])
            bullets = item.get("bullets") or []
            for index, bullet in enumerate(bullets):
                add_bullet(doc, bullet, page_index=page_index, first=index == 0, project=project)
    doc.save(out)
    return out


def word_powershell_env(environ=None, windows=None):
    env = dict(os.environ if environ is None else environ)
    windows = (os.name == "nt") if windows is None else windows
    if windows:
        system_root = env.get("SystemRoot", r"C:\Windows")
        program_files = env.get("ProgramFiles", r"C:\Program Files")
        env["PSModulePath"] = os.pathsep.join([
            str(Path(program_files) / "WindowsPowerShell" / "Modules"),
            str(Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "Modules"),
        ])
    return env


def export_pdf_with_word(docx, pdf, repeat_pdf=None, subset_fonts=True):
    script = Path(__file__).with_name("export_word.ps1")
    log_path = Path(pdf).with_suffix(".word-export.json")
    command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), str(docx), str(pdf)]
    if repeat_pdf:
        command.append(str(repeat_pdf))
    command.append(str(log_path))
    try:
        result = subprocess.run(command, cwd=str(Path(__file__).resolve().parents[1]), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, env=word_powershell_env())
    except FileNotFoundError as exc:
        raise SystemExit("无法启动 Word 导出进程：需要 Windows PowerShell 和本机 Microsoft Word；不会用其他渲染器冒充 PDF。") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Word 导出超时；请关闭占用文档的进程后重试，当前产物不得视为验收通过。") from exc
    if result.returncode != 0:
        raise RuntimeError(f"Word 导出失败：{result.stdout}\n{result.stderr}")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Word 导出证据不可解析：{result.stdout}") from exc
    if not report.get("exit_code") == 0:
        raise RuntimeError(f"Word 导出失败：{report}")
    if subset_fonts:
        for path in (Path(pdf), Path(repeat_pdf) if repeat_pdf else None):
            if path and path.exists():
                subset_pdf_fonts(path)
    return report


def _embedded_font_stream(document, font_xref):
    descriptor = document.xref_get_key(font_xref, "FontDescriptor")
    if descriptor[0] != "xref":
        descendants = document.xref_get_key(font_xref, "DescendantFonts")
        if descendants[0] != "xref":
            return None, None
        descendant_xref = int(descendants[1].split()[0])
        match = re.search(r"(\d+)\s+0\s+R", document.xref_object(descendant_xref))
        if not match:
            return None, None
        descriptor = document.xref_get_key(int(match.group(1)), "FontDescriptor")
    if descriptor[0] != "xref":
        return None, None
    descriptor_xref = int(descriptor[1].split()[0])
    for key in ("FontFile2", "FontFile3", "FontFile"):
        stream = document.xref_get_key(descriptor_xref, key)
        if stream[0] == "xref":
            return int(stream[1].split()[0]), key
    return None, None


def _subset_large_font_streams(document):
    from fontTools import subset
    from fontTools.ttLib import TTFont
    from io import BytesIO

    used_glyphs = {}
    for page in document:
        for span in page.get_texttrace():
            used_glyphs.setdefault(span["font"], set()).update(char[1] for char in span["chars"])
    font_xrefs = {font[0] for page in document for font in page.get_fonts(full=True)}
    for font_xref in sorted(font_xrefs):
        stream_xref, _ = _embedded_font_stream(document, font_xref)
        if not stream_xref:
            continue
        original = document.xref_stream(stream_xref)
        if len(original) < 1_000_000:
            continue
        base_font = document.xref_get_key(font_xref, "BaseFont")[1].split("+")[-1].lstrip("/")
        glyphs = used_glyphs.get(base_font) or set()
        if not glyphs:
            continue
        try:
            options = subset.Options()
            options.retain_gids = True
            options.notdef_glyph = True
            options.notdef_outline = True
            font = TTFont(BytesIO(original), recalcBBoxes=False, recalcTimestamp=False)
            subsetter = subset.Subsetter(options=options)
            subsetter.populate(gids=glyphs)
            subsetter.subset(font)
            output = BytesIO()
            font.save(output)
            replacement = output.getvalue()
            if 0 < len(replacement) < len(original):
                document.update_stream(stream_xref, replacement, compress=True)
        except Exception as exc:
            print(f"WARN 字体 {font_xref} 保留原嵌入数据：{exc}")


def _pdf_fingerprint(document):
    pages = []
    for page in document:
        import hashlib
        pixmap = page.get_pixmap(dpi=72, alpha=False)
        links = sorted((link.get("uri") or "", tuple(round(v, 3) for v in link["from"])) for link in page.get_links() if link.get("uri"))
        pages.append((page.get_text("text", sort=False), links, hashlib.sha256(pixmap.samples).hexdigest()))
    return pages


def subset_pdf_fonts(path):
    path = Path(path)
    temp = path.with_name(path.stem + ".subset.tmp.pdf")
    with fitz.open(path) as document:
        before = _pdf_fingerprint(document)
        document.subset_fonts()
        _subset_large_font_streams(document)
        document.save(temp, garbage=4, clean=True, deflate=True)
    with fitz.open(temp) as document:
        after = _pdf_fingerprint(document)
    if before != after:
        differences = []
        for index, (old, new) in enumerate(zip(before, after), start=1):
            if old[0] != new[0]:
                differences.append(f"第{index}页文本")
            if old[1] != new[1]:
                differences.append(f"第{index}页链接")
            if old[2] != new[2]:
                differences.append(f"第{index}页像素")
        temp.unlink(missing_ok=True)
        raise RuntimeError(f"字体子集化改变 {'、'.join(differences)}，已保留原文件：{path}")
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("yaml", type=Path)
    parser.add_argument("-o", "--output", required=True, type=Path)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--repeat-pdf", type=Path)
    parser.add_argument("--no-subset-fonts", action="store_true", help="诊断用：保留 Word 原始嵌入字体")
    args = parser.parse_args()
    data = yaml.safe_load(args.yaml.read_text(encoding="utf-8")) or {}
    build_docx(data, args.output, args.yaml.resolve().parent)
    print(f"OK  {args.output}")
    if args.pdf or args.repeat_pdf:
        if not args.pdf or not args.repeat_pdf:
            parser.error("--pdf 与 --repeat-pdf 必须同时提供")
        export_pdf_with_word(args.output, args.pdf, args.repeat_pdf, subset_fonts=not args.no_subset_fonts)
        print(f"OK  {args.pdf}\nOK  {args.repeat_pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
