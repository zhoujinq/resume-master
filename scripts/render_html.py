#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resume-master · HTML 渲染器
YAML -> 自包含 HTML ->（可选）Chrome 无头打印成 A4 PDF

用法:
    python render_html.py resume.yaml -o resume.html
    python render_html.py resume.yaml -o resume.html --pdf resume.pdf

为什么先 HTML 再 PDF：
  CSS 的排版能力（字距、行高、对齐、悬挂缩进、分页控制）比 reportlab 精细，
  而且同一份 HTML 可以直接当网页用。Chrome 打印保证 1:1 还原。
"""
import argparse
import html as _html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
CSS_PATH = os.path.join(HERE, "..", "assets", "resume.css")
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def md(s):
    """**粗体** -> <b>，其余转义。"""
    s = _html.escape(str(s), quote=False)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)


def esc(s):
    return _html.escape(str(s), quote=False)


def build_html(data, css):
    meta = data.get("meta") or {}
    style = data.get("style") or {}
    preset = style.get("preset") or "swiss"

    vars_ = []
    if style.get("accent"):
        vars_.append(f"--accent:{style['accent']}")
    if style.get("body_size"):
        vars_.append(f"--fs-body:{style['body_size']}pt")
    if style.get("lead"):
        vars_.append(f"--lh:{style['lead']}")
    if style.get("gap_entry"):
        vars_.append(f"--gap-entry:{style['gap_entry']}mm")
    if style.get("gap_sec"):
        vars_.append(f"--gap-sec:{style['gap_sec']}mm")
    if style.get("density") == "ultra":
        vars_ += ["--gap-entry:1.8mm", "--gap-sec:3.4mm", "--fs-body:9.0pt"]
    elif style.get("density") == "compact":
        vars_ += ["--gap-entry:2.4mm", "--gap-sec:4.2mm", "--fs-body:9.0pt"]
    elif style.get("density") == "tight":
        vars_ += ["--gap-entry:3.6mm", "--gap-sec:6.0mm"]
    elif style.get("density") == "airy":
        vars_ += ["--gap-entry:5.6mm", "--gap-sec:9.0mm"]
    var_style = f' style="{";".join(vars_)}"' if vars_ else ""

    out = [f'<div class="doc preset-{preset}"{var_style}>']

    # ---- 报头 ----
    out.append("<header>")
    photo = meta.get("photo")
    if photo and os.path.exists(photo):
        out.append(f'<img class="photo" src="data:image/jpeg;base64,{b64(photo)}" alt="">')
    out.append('<div class="ident">')
    out.append(f"<h1>{esc(meta.get('name', ''))}</h1>")
    if meta.get("role"):
        out.append(f'<div class="role">{esc(meta["role"])}</div>')
    out.append('<div class="masthead-rule"></div>')

    bits = []
    for x in (meta.get("contact") or []):
        if isinstance(x, dict):
            label = esc(x.get("t", ""))
            url = x.get("u")
            if x.get("br"):
                bits.append("<br>")
            bits.append(f'<span><a href="{esc(url)}">{label}</a></span>' if url else f"<span>{label}</span>")
        else:
            bits.append(f"<span>{esc(x)}</span>")
    if bits:
        out.append(f'<div class="contact">{"".join(bits)}</div>')

    links = meta.get("links") or []
    if links:
        ls = []
        for l in links:
            ls.append(
                f'<span><span class="lab">{esc(l.get("label", ""))}</span> '
                f'<a href="{esc(l.get("url", ""))}">{esc(l.get("short") or l.get("url", ""))}</a></span>'
            )
        out.append(f'<div class="links">{"".join(ls)}</div>')

    stats = meta.get("stats") or []
    if stats:
        cells = "".join(
            f'<div class="item"><div class="n">{esc(x.get("n", ""))}</div>'
            f'<div class="l">{esc(x.get("l", ""))}</div></div>'
            for x in stats
        )
        out.append(f'<div class="stats">{cells}</div>')
    out.append("</div>")

    lede = (meta.get("lede") or "").strip()
    if lede:
        out.append(f'<div class="lede">{md(lede)}</div>')
    out.append("</header>")

    # ---- 章节 ----
    for sec in data.get("sections") or []:
        out.append("<section>")
        note = f'<span class="note">{esc(sec["note"])}</span>' if sec.get("note") else ""
        out.append(f'<h2>{esc(sec.get("title", ""))}{note}</h2>')

        for it in sec.get("items") or []:
            out.append('<div class="entry keep">' if it.get("keep") else '<div class="entry">')
            out.append('<div class="head">')
            logo = it.get("logo")
            if logo and os.path.exists(logo):
                lw = it.get("logo_w")
                style = f' style="width:{lw}mm"' if lw else ""
                out.append(f'<img class="logo" src="data:image/png;base64,{b64(logo)}" alt=""{style}>')
            out.append(f'<span class="org">{md(it.get("org", ""))}</span>')
            if it.get("role"):
                out.append(f'<span class="pos">{esc(it["role"])}</span>')
            if it.get("date"):
                out.append(f'<span class="date">{esc(it["date"])}</span>')
            elif it.get("link"):
                # 项目类条目：右侧放可点链接，占 date 的位置
                lk = it["link"]
                if isinstance(lk, dict):
                    txt, url = (lk.get("text") or lk.get("url", "")), lk.get("url", "")
                else:
                    txt, url = str(lk), str(lk)
                if url:
                    out.append(
                        f'<span class="date"><a class="plink" href="{esc(url)}" '
                        f'target="_blank" rel="noopener">{esc(txt)}</a></span>'
                    )
                else:
                    # 只有占位文字、没有链接：不上 <a>，避免生成死链注解
                    out.append(f'<span class="date ph">{esc(txt)}</span>')
            out.append("</div>")
            if it.get("bullets"):
                out.append("<ul>")
                out.extend(f"<li>{md(b)}</li>" for b in it["bullets"])
                out.append("</ul>")
            out.append("</div>")

        if sec.get("bullets"):
            out.append("<ul>")
            out.extend(f"<li>{md(b)}</li>" for b in sec["bullets"])
            out.append("</ul>")

        if sec.get("body"):
            out.append(f'<p class="body-text">{md(sec["body"])}</p>')

        out.append("</section>")

    out.append("</div>")

    title = meta.get("name", "resume")
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<title>{esc(title)}</title>\n<style>\n{css}\n</style>\n</head>\n<body>\n"
        + "\n".join(out)
        + "\n</body>\n</html>\n"
    )


def b64(path):
    import base64
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def find_chrome():
    for p in CHROME_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def html_to_pdf(html_path, pdf_path, timeout=40):
    chrome = find_chrome()
    if not chrome:
        sys.exit("找不到 Chrome / Edge，无法导出 PDF。可先用浏览器手动打印。")
    # 用纯 ASCII 临时目录，规避中文路径在子进程里的编码问题
    tmp = tempfile.mkdtemp(prefix="rm-")
    tmp_html = os.path.join(tmp, "index.html")
    tmp_pdf = os.path.join(tmp, "out.pdf")
    shutil.copyfile(html_path, tmp_html)
    subprocess.run(
        [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
         f"--user-data-dir={os.path.join(tmp, 'prof')}",
         f"--print-to-pdf={tmp_pdf}", "file:///" + tmp_html.replace("\\", "/")],
        capture_output=True, timeout=timeout,
    )
    for _ in range(40):
        if os.path.exists(tmp_pdf) and os.path.getsize(tmp_pdf) > 1000:
            break
        time.sleep(0.5)
    if not os.path.exists(tmp_pdf):
        sys.exit("Chrome 没有产出 PDF（可能被占用或超时）")
    shutil.move(tmp_pdf, pdf_path)
    shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("yaml_path")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--pdf", default=None)
    args = ap.parse_args()

    with open(args.yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    base = os.path.dirname(os.path.abspath(args.yaml_path))

    asset_fallback = os.path.join(HERE, "..", "examples", "assets")

    def fix(p):
        """相对路径按 YAML 所在目录解析；找不到就回退到技能的 examples/assets。"""
        if not p:
            return p
        path = p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))
        if not os.path.exists(path):
            alt = os.path.join(asset_fallback, os.path.basename(path))
            if os.path.exists(alt):
                return alt
        return path

    meta = data.setdefault("meta", {})
    meta["photo"] = fix(meta.get("photo"))
    for sec in data.get("sections") or []:
        for it in sec.get("items") or []:
            it["logo"] = fix(it.get("logo"))

    css = open(CSS_PATH, encoding="utf-8").read()
    html = build_html(data, css)

    out = args.out or os.path.splitext(args.yaml_path)[0] + ".html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK  {out}")

    if args.pdf:
        html_to_pdf(out, args.pdf)
        print(f"OK  {args.pdf}")


if __name__ == "__main__":
    main()
