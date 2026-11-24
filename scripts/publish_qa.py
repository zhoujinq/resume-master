#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把真实 QA JSON 转成不含本机路径的公开 Markdown；不改变任何检查状态。"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PureWindowsPath

DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")


def _public_value(value):
    if isinstance(value, dict):
        return {key: _public_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_public_value(item) for item in value]
    if isinstance(value, str) and DRIVE_PATH.match(value):
        return PureWindowsPath(value).name
    return value


def public_detail(detail):
    text = str(detail)
    if not text.startswith("{"):
        return text
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return re.sub(r"[A-Za-z]:[\\/][^\"]+", "<local-path>", text)
    return json.dumps(_public_value(payload), ensure_ascii=False)


def render_public_report(report, include_release_evidence=False):
    overall = str(report.get("overall") or "UNKNOWN")
    checks = report.get("checks") or []
    blocking = [check for check in checks if check.get("category") in {"core", "strict"} and check.get("status") in {"FAIL", "NOT_RUN"}]
    summary = "核心与严格项无 FAIL／NOT_RUN" if not blocking else f"仍有 {len(blocking)} 个核心或严格阻断项"
    lines = [
        "# Resume Master v3.0.0 公开样例 QA",
        "",
        "数据来源：仓库内虚构样例。本报告只脱敏本机路径，不改写检查状态，也不声称自动证明事实真实。",
        "",
        f"**{overall}**；{summary}。建议 WARN 如实保留，不等于核心 FAIL。",
        "",
        "| 层级 | 检查 | 状态 | 证据 |",
        "|---|---|---|---|",
    ]
    for check in checks:
        values = [check.get("category", ""), check.get("name", ""), check.get("status", ""), public_detail(check.get("detail", ""))]
        lines.append("| " + " | ".join(str(value).replace("|", "\\|").replace("\n", " ") for value in values) + " |")
    if include_release_evidence:
        lines += [
            "",
            "## 补充实证边界",
            "",
            "- 真实 V53.1 内容的私有影子输入完成两页 DOCX／Word PDF 双导出；32 条事实、6/6 链接、逐页文本与 144 DPI 重复导出像素差 0 均通过。私有数据、路径和图像不进入公开仓库。",
            "- 另一组完全虚构的无照片、超长链接、三页长文样例完成同一路线验收；15/15 链接、3 页页数、编辑—撤销和逐页像素差 0 均通过。",
            "- 上述补充结果只说明本次实测，不构成对任意环境、任意内容或任意 Word 版本的保证。",
        ]
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("qa_json", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--release-evidence", action="store_true", help="仅 v3.0.0 发布时使用：附加本轮已实测的影子与边界结论")
    args = parser.parse_args()
    report = json.loads(args.qa_json.read_text(encoding="utf-8"))
    args.output.write_text(render_public_report(report, include_release_evidence=args.release_evidence), encoding="utf-8")
    print(f"OK  {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
