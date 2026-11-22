#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resume-master · 渲染引擎
YAML -> A4 PDF（精确排版，一个引擎 + 多套主题）

用法:
    python render.py resume.yaml -o out.pdf [--theme swiss|editorial|mono]

设计原则（详见 references/design-system.md）:
  1. 层级靠留白、字重、细线，不靠颜色
  2. 强调色一页最多出现 3 处
  3. 时间右对齐到页边
  4. 章节标题 = 小字号 + 字距 + 一条通到页边的细线
"""
import argparse
import html as _html
import os
import re
import sys

import yaml
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

FONT_DIR = "C:/Windows/Fonts/"
FONT_MAP = {
    "body": ("Deng", "Deng.ttf"),
    "body_b": ("DengB", "Dengb.ttf"),
    "hei": ("Hei", "simhei.ttf"),
    "song": ("Song", "simsun.ttc"),
    "mono": ("Mono", "consola.ttf"),
    "mono_b": ("MonoB", "consolab.ttf"),
}

PAGE_W, PAGE_H = A4
INK = "#16181D"
BODY_INK = "#2A2F38"

THEMES = {
    # 瑞士网格：全无衬线，强左对齐，细横线
    "swiss": dict(
        display="body_b", accent="#2F5BEA",
        name_size=25, name_track=1.2, role_size=10.0,
        sec_size=8.3, sec_track=1.4, sec_rule_color="#1F2328",
        bullet="square", body_size=8.9, lead=1.60,
        date_color="#7A818C", muted="#5C636E", faint="#9AA1AB",
        rule="#DFE1E6", entry_gap=4.4, sec_gap_top=8.6, sec_gap_bottom=3.0,
    ),
    # 编辑风：宋体大标题 + 报头式导语
    "editorial": dict(
        display="song", accent="#B4472B",
        name_size=29, name_track=3.0, role_size=9.6,
        sec_size=8.5, sec_track=2.0, sec_rule_color="#C9C4BA",
        bullet="dash", body_size=8.9, lead=1.64,
        date_color="#857F74", muted="#5A554C", faint="#9C968B",
        rule="#E2DDD4", entry_gap=4.8, sec_gap_top=9.2, sec_gap_bottom=3.2,
    ),
    # 技术文档：等宽标题 + 极细线，密度高
    "mono": dict(
        display="hei", accent="#0F766E",
        name_size=22, name_track=1.0, role_size=9.4,
        sec_size=7.9, sec_track=1.0, sec_rule_color="#111111",
        bullet="plus", body_size=8.7, lead=1.56,
        date_color="#6B7280", muted="#4B5563", faint="#9CA3AF",
        rule="#D6D6DA", entry_gap=4.0, sec_gap_top=7.6, sec_gap_bottom=2.6,
    ),
}

BULLET_GLYPH = {"square": "\u25aa", "dash": "\u2013", "plus": "+"}


def md(s):
    """**粗体** -> <b>，其余字符转义。"""
    s = _html.escape(str(s), quote=False)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)


def register_fonts():
    ok = {}
    for key, (name, fn) in FONT_MAP.items():
        path = os.path.join(FONT_DIR, fn)
        if not os.path.exists(path):
            continue
        try:
            if fn.lower().endswith(".ttc"):
                pdfmetrics.registerFont(TTFont(name, path, subfontIndex=0))
            else:
                pdfmetrics.registerFont(TTFont(name, path))
            ok[key] = name
        except Exception:
            pass
    if "body" not in ok:
        sys.exit("fonts: 找不到中文字体，请修改 FONT_MAP 指向本机字体")
    pdfmetrics.registerFontFamily(
        ok["body"], normal=ok["body"], bold=ok.get("body_b", ok["body"]),
        italic=ok["body"], boldItalic=ok.get("body_b", ok["body"]),
    )
    return ok


class Doc:
    def __init__(self, path, theme, margins):
        self.c = canvas.Canvas(path, pagesize=A4)
        self.t = theme
        self.ml = margins["left"] * mm
        self.mr = margins["right"] * mm
        self.mt = margins["top"] * mm
        self.mb = margins["bottom"] * mm
        self.w = PAGE_W - self.ml - self.mr
        self.x = self.ml
        self.y = PAGE_H - self.mt
        self.page = 1
        self.total_pages = 1

    # ---------- 基础 ----------
    def text(self, x, y, s, font, size, color=INK, track=0.0, anchor="l"):
        c = self.c
        if anchor == "r":
            x -= pdfmetrics.stringWidth(s, font, size) + track * max(0, len(s) - 1)
        to = c.beginText(x, y)
        to.setFont(font, size)
        to.setFillColor(HexColor(color) if isinstance(color, str) else color)
        to.setCharSpace(track)
        to.textOut(s)
        c.drawText(to)
        c._charSpace = 0          # Tc 会残留在图形状态里，必须复位

    def reset_tc(self):
        """显式把字符间距归零：Tc 属于文本状态，会残留给后续 Paragraph。"""
        to = self.c.beginText(0, -50)
        to.setCharSpace(0)
        to.textOut("")
        self.c.drawText(to)
        self.c._charSpace = 0

    def para(self, text, size, color, width, lead=1.6, font=None):
        style = ParagraphStyle(
            "p", fontName=font or self.t["body"], fontSize=size, leading=size * lead,
            textColor=HexColor(color) if isinstance(color, str) else color,
            wordWrap="CJK", spaceBefore=0, spaceAfter=0,
        )
        p = Paragraph(text, style)
        _, h = p.wrap(width, 10000)
        return p, h

    def draw_para(self, text, size, color, width, lead=1.6, indent=0.0):
        """在当前 y 上方绘制段落；y 更新为段落底部。"""
        p, h = self.para(text, size, color, width - indent - 10, lead=lead)
        self.ensure(h)
        self.reset_tc()
        p.drawOn(self.c, self.x + indent, self.y - h)
        self.y -= h
        return h

    def line(self, x1, y, x2, color="#DCDEE3", width=0.5):
        self.c.setStrokeColor(HexColor(color))
        self.c.setLineWidth(width)
        self.c.line(x1, y, x2, y)

    def ensure(self, h):
        if self.y - h < self.mb:
            self.new_page()

    def new_page(self):
        self._footer()
        self.c.showPage()
        self.page += 1
        self.y = PAGE_H - self.mt

    def _footer(self):
        if self.total_pages <= 1:
            return
        self.text(PAGE_W - self.mr, self.mb * 0.5, f"{self.page} / {self.total_pages}",
                  self.t["body"], 7, self.t["faint"], anchor="r")

    # ---------- 报头 ----------
    def header(self, meta):
        t = self.t
        photo = meta.get("photo")
        pw = float(meta.get("photo_w") or 0) * mm
        has_photo = bool(photo and pw and os.path.exists(photo))
        avail = self.w - (pw + 6 * mm if has_photo else 0)

        if has_photo:
            ph = pw * 1.4
            x0 = PAGE_W - self.mr - pw
            y0 = PAGE_H - self.mt - ph
            self.c.drawImage(photo, x0, y0, pw, ph, mask="auto")
            self.c.setStrokeColor(HexColor(t["rule"]))
            self.c.setLineWidth(0.4)
            self.c.rect(x0, y0, pw, ph, stroke=1, fill=0)

        base = self.y - t["name_size"] * 0.88
        self.text(self.x, base, meta["name"], t["display"], t["name_size"], INK,
                  track=t["name_track"])
        self.y = base - t["name_size"] * 0.34

        if meta.get("role"):
            self.text(self.x, self.y - t["role_size"] * 0.86, meta["role"], t["body"],
                      t["role_size"], t["accent"], track=0.15)
            self.y -= t["role_size"] + 5.0

        bits = list(meta.get("contact") or [])
        if bits:
            self.draw_para("   ·   ".join(bits), 7.7, t["muted"], avail, lead=1.5)
            self.y -= 1.8

        links = meta.get("links") or []
        if links:
            parts = []
            for l in links:
                label = l.get("label", "")
                short = l.get("short") or l.get("url", "")
                parts.append(f'{label}&nbsp;&nbsp;<a href="{l.get("url", "")}" color="{t["accent"]}">{short}</a>')
            self.draw_para("   ·   ".join(parts), 7.7, t["muted"], avail, lead=1.5)

        self.y -= 3.4

        lede = (meta.get("lede") or "").strip()
        if lede:
            p, h = self.para(md(lede), t["body_size"] + 0.5, t["muted"], avail - 4.5 * mm - 2,
                             lead=t["lead"] + 0.04)
            self.ensure(h + 6 * mm)
            self.c.setFillColor(HexColor(t["accent"]))
            self.c.rect(self.x, self.y - h, 1.5, h, stroke=0, fill=1)
            self.reset_tc()
            p.drawOn(self.c, self.x + 4.5 * mm, self.y - h)
            self.y -= h + 4.6 * mm

    # ---------- 章节 ----------
    def section_title(self, title, note=""):
        t = self.t
        self.ensure(26 * mm)
        self.y -= t["sec_gap_top"]
        size = t["sec_size"]
        self.text(self.x, self.y - size, title, t["body"], size, INK, track=t["sec_track"])
        tw = pdfmetrics.stringWidth(title, t["body"], size) + t["sec_track"] * max(0, len(title) - 1)
        note_w = pdfmetrics.stringWidth(note, t["body"], 7.2) + 3.0 * mm if note else 0
        self.line(self.x + tw + 4.0 * mm, self.y - size * 0.30, PAGE_W - self.mr - note_w,
                  t["sec_rule_color"], 0.6)
        if note:
            self.text(PAGE_W - self.mr, self.y - size, note, t["body"], 7.2, t["faint"], anchor="r")
        self.y -= size + t["sec_gap_bottom"] + 2.4

    # ---------- 条目 ----------
    def entry(self, item):
        t = self.t
        org = item.get("org", "")
        role = item.get("role", "")
        date = item.get("date", "")
        logo = item.get("logo")

        size = t["body_size"] + 0.9
        lh = size * 1.5
        self.ensure(lh + t["body_size"] * 2.4)

        base = self.y - size
        x = self.x
        if logo and os.path.exists(logo):
            w, h = 4.0 * mm, 4.0 * mm
            try:
                from PIL import Image as _PIL
                iw, ih = _PIL.open(logo).size
                h = 3.7 * mm
                w = h * iw / ih
                if w > 11 * mm:
                    w = 11 * mm
                    h = w * ih / iw
            except Exception:
                pass
            cy = base + size * 0.34
            self.c.drawImage(logo, x, cy - h / 2, w, h, mask="auto")
            x += w + 2.0 * mm

        self.text(x, base, org, t["bold"], size, INK)
        org_w = pdfmetrics.stringWidth(org, t["bold"], size)

        date_w = 0
        if date:
            ds = t["body_size"] - 1.5
            date_w = pdfmetrics.stringWidth(date, t["body"], ds)
            self.text(PAGE_W - self.mr, base, date, t["body"], ds, t["date_color"], anchor="r")

        self.y -= lh + 1.0
        if role:
            room = (PAGE_W - self.mr - date_w - 4 * mm) - (x + org_w + 2.6 * mm)
            if pdfmetrics.stringWidth(role, t["body"], t["body_size"] - 0.2) <= room:
                self.text(x + org_w + 2.6 * mm, base, role, t["body"], t["body_size"] - 0.2,
                          t["muted"])
            else:
                self.draw_para(role, t["body_size"] - 0.2, t["muted"], self.w, lead=1.45)
                self.y -= 1.0

        for b in item.get("bullets") or []:
            self.bullet(b)
        self.y -= t["entry_gap"]

    def bullet(self, text):
        t = self.t
        indent = 4.0 * mm
        size = t["body_size"]
        p, h = self.para(md(text), size, BODY_INK, self.w - indent - 10, lead=t["lead"])
        self.ensure(h + 0.5)
        # 用矢量图形画项目符号：等线/宋体没有 U+25AA 这类符号，字形方案会画不出来
        self.c.setFillColor(HexColor(t["accent"]))
        self.c.setStrokeColor(HexColor(t["accent"]))
        bx = self.x + 0.9 * mm
        by = self.y - size * 0.62
        if t["bullet"] == "dash":
            self.c.setLineWidth(0.9)
            self.c.line(bx, by, bx + size * 0.62, by)
        elif t["bullet"] == "plus":
            self.c.setLineWidth(0.7)
            self.c.line(bx, by - size * 0.26, bx, by + size * 0.26)
            self.c.line(bx - size * 0.26, by, bx + size * 0.26, by)
        else:
            self.c.rect(bx, by - size * 0.15, size * 0.30, size * 0.30, stroke=0, fill=1)
        self.reset_tc()
        p.drawOn(self.c, self.x + indent, self.y - h)
        self.y -= h + 1.05

    # ---------- 收尾 ----------
    def save(self):
        self._footer()
        self.c.save()


def resolve_assets(data, base):
    def fix(p):
        if not p:
            return p
        return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))

    meta = data.get("meta") or {}
    meta["photo"] = fix(meta.get("photo"))
    for sec in data.get("sections") or []:
        for it in sec.get("items") or []:
            it["logo"] = fix(it.get("logo"))
    return data


def build(data, out_path, theme_name=None):
    fonts_ok = register_fonts()
    style = data.get("style") or {}
    theme = dict(THEMES[theme_name or style.get("preset") or "swiss"])
    if style.get("accent"):
        theme["accent"] = style["accent"]
    # 通用数值覆盖：name_size / name_track / role_size / sec_size / sec_track / lead / body_size
    for k in ("name_size", "name_track", "role_size", "sec_size", "sec_track", "lead", "body_size"):
        if style.get(k) is not None:
            theme[k] = float(style[k])
    if style.get("density") == "tight":
        theme["lead"] = round(theme["lead"] - 0.05, 2)
        theme["entry_gap"] -= 0.7
        theme["sec_gap_top"] -= 1.0
    elif style.get("density") == "airy":
        theme["lead"] = round(theme["lead"] + 0.07, 2)
        theme["entry_gap"] += 1.2
        theme["sec_gap_top"] += 1.4

    theme["body"] = fonts_ok["body"]
    theme["bold"] = fonts_ok.get("body_b", fonts_ok["body"])
    theme["display"] = fonts_ok.get(theme["display"], theme["body"])

    margins = {"left": 18, "right": 18, "top": 15, "bottom": 14}
    margins.update(style.get("margins") or {})

    tmp = out_path + ".tmp.pdf"
    pages = 1
    for _ in range(2):
        doc = Doc(tmp, theme, margins)
        doc.total_pages = pages
        doc.header(data["meta"])
        for sec in data.get("sections") or []:
            doc.section_title(sec.get("title", ""), sec.get("note", ""))
            for it in sec.get("items") or []:
                doc.entry(it)
            for b in sec.get("bullets") or []:
                doc.bullet(b)
            if sec.get("body"):
                doc.draw_para(md(sec["body"]), theme["body_size"], BODY_INK, doc.w,
                              lead=theme["lead"])
                doc.y -= 2
        pages = doc.page
        doc.save()
    os.replace(tmp, out_path)
    return pages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("yaml_path")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--theme", default=None, choices=list(THEMES))
    args = ap.parse_args()

    with open(args.yaml_path, encoding="utf-8") as f:
        data = resolve_assets(yaml.safe_load(f), os.path.dirname(os.path.abspath(args.yaml_path)))

    out = args.out or os.path.splitext(args.yaml_path)[0] + ".pdf"
    pages = build(data, out, args.theme)
    print(f"OK  {out}  ({pages} 页)")


if __name__ == "__main__":
    main()
