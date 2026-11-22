#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 PDF 每页导出 PNG，供视觉复核（140 dpi）。"""
import sys

import fitz


def main():
    if len(sys.argv) < 2:
        sys.exit("用法: python preview.py out.pdf")
    pdf = sys.argv[1]
    doc = fitz.open(pdf)
    for i, page in enumerate(doc):
        path = f"{pdf}.p{i + 1}.png"
        page.get_pixmap(dpi=140).save(path)
        print(path)


if __name__ == "__main__":
    main()
