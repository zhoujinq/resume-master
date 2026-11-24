#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成公开仓库使用的虚构测试图片，不包含真实人物或企业素材。"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

photo = Image.new("RGB", (600, 840))
pixels = photo.load()
for y in range(photo.height):
    value = int(238 - 28 * y / photo.height)
    for x in range(photo.width):
        pixels[x, y] = (value, value, min(255, value + 3))
draw = ImageDraw.Draw(photo)
draw.ellipse((190, 150, 410, 370), fill="#B8BDC7")
draw.rounded_rectangle((105, 390, 495, 790), radius=150, fill="#A8AFBB")
photo.save(ASSETS / "sample-photo.png", optimize=True)

logo = Image.new("RGB", (160, 160), "#2F5BEA")
draw = ImageDraw.Draw(logo)
draw.rounded_rectangle((35, 35, 125, 125), radius=24, outline="white", width=10)
draw.line((55, 100, 80, 65, 108, 92), fill="white", width=10, joint="curve")
logo.save(ASSETS / "sample-logo.png", optimize=True)

github = Image.new("RGB", (64, 64), "white")
draw = ImageDraw.Draw(github)
draw.ellipse((8, 8, 24, 24), fill="#2F5BEA")
draw.ellipse((40, 8, 56, 24), fill="#2F5BEA")
draw.ellipse((24, 40, 40, 56), fill="#2F5BEA")
draw.line((16, 24, 16, 32, 32, 40), fill="#2F5BEA", width=5)
draw.line((48, 24, 48, 32, 32, 40), fill="#2F5BEA", width=5)
github.save(ASSETS / "icon-github.png", optimize=True)

gmail = Image.new("RGB", (64, 64), "white")
draw = ImageDraw.Draw(gmail)
draw.rounded_rectangle((5, 12, 59, 52), radius=5, outline="#2F5BEA", width=5)
draw.line((9, 17, 32, 36, 55, 17), fill="#2F5BEA", width=5, joint="curve")
gmail.save(ASSETS / "icon-gmail.png", optimize=True)
print("OK  4 个虚构测试图片")
