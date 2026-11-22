#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 master 派生一个新版本（master-first）。

用法:
    python fork.py _master/resume.yaml versions/target-2026-11.yaml --target "示例目标岗位"

行为:
  - 只复制，不改内容
  - 在文件头写派生三行注释（源于哪份 master、目标岗位、日期）
  - 已存在则拒绝覆盖（防止把定稿改掉）
"""
import argparse
import datetime
import io
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("master")
    ap.add_argument("out")
    ap.add_argument("--target", default="", help="目标岗位 / 公司")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.master):
        sys.exit(f"master 不存在: {args.master}")
    if os.path.exists(args.out) and not args.force:
        sys.exit(f"目标已存在，拒绝覆盖: {args.out}（确需覆盖加 --force）")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    body = io.open(args.master, encoding="utf-8").read()
    head = (
        f"# fork: from={os.path.relpath(args.master)}\n"
        f"# target: {args.target or '未指定'}\n"
        f"# date: {datetime.date.today().isoformat()}\n"
        "# 注意：这是派生版本，源文件是 master；改内容只改这里，不要回写 master。\n"
    )
    io.open(args.out, "w", encoding="utf-8").write(head + body)
    print(f"OK  {args.out}")


if __name__ == "__main__":
    main()
