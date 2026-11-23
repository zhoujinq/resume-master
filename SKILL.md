---
name: resume-master
description: >
  中文简历的内容优化与 A4 排版工作流，有没有目标岗位 JD 都能用。仅提供现有简历时，直接输出一版事实不漂移、表达更清晰的优化简历；同时提供简历与 JD 时，额外做岗位匹配审计并输出更匹配的版本。支持 PDF、DOCX、Markdown、TXT、YAML 输入，默认少打断，交付 PDF 与可编辑源文件。触发：写简历、改简历、简历优化、按 JD 定制、简历排版、简历一页版、简历导出 PDF。不做：自动投递、面试题库、招聘平台对接、ATS 打分。
---

# 简历工坊 Pro

> 先判断用户给的是“仅简历”还是“简历 + JD”，直接执行，不给路由菜单。

## 一、默认两种模式

| 模式 | 输入 | 必交付 | 额外交付 |
|---|---|---|---|
| **A｜仅简历** | 一份现有简历，没有 JD | 优化版 PDF＋可编辑源文件＋修改说明 | 待确认清单（有才给） |
| **B｜简历 + JD** | 现有简历＋目标岗位 JD 原文 | 更匹配岗位的 PDF＋可编辑源文件＋修改说明 | JD 匹配差距表＋取舍依据 |

**没有 JD 也能直接优化，不追问目标岗位。** 用户主动给 JD 才进入岗位匹配；不要把 JD 变成启动条件。

## 二、按需加载

1. 读取输入与识别模式：[`references/intake.md`](references/intake.md)。
2. 事实、隐私、归属与提问纪律：[`references/guardrails.md`](references/guardrails.md)，每次都守。
3. 内容改写：[`references/content-rules.md`](references/content-rules.md) 与 [`references/provenance.md`](references/provenance.md)。
4. 强调决策：[`references/emphasis.md`](references/emphasis.md)，先给标蓝与不标蓝清单，默认少标。
5. 排版：[`references/design-system.md`](references/design-system.md)。
6. 渲染和交付门禁：[`references/operating-discipline.md`](references/operating-discipline.md) 与 [`references/delivery.md`](references/delivery.md)。

## 三、主流程

1. **读取**：保留原文件；提取教育、经历、项目、技能、联系方式和已有数字，标注低置信度字段。
2. **审计**：区分 A 已核验／B 用户陈述／C 我的推断／D 未知；识别团队成果、个人成果、协助角色，不夸大归属。
3. **集中确认**：只问会改变事实或方向的问题，合并成一轮，最多 3 个；其余合理默认并写入修改说明。先给可用草案，不用提问代替交付。
4. **重构**：先给全文文字稿与标蓝／不标蓝清单。模式 B 额外给 JD 匹配差距表：JD 要求、已有证据、缺口、拟强化位置；关键词只写确有证据的。
5. **排版**：用同一 `resume.yaml` 生成 HTML 和 PDF；默认 A4、克制层级、少而精的强调，不为塞版面悄悄删字。
6. **验收**：运行 `scripts/qa.py` 与 `scripts/preview.py`，检查页数、首末行、越界、照片与链接；可选 DOCX 必须真实渲染后再与 PDF 比对。真实渲染不合格就修复责任源，不在成品上遮盖。

## 四、命令

```bash
# 主路径：YAML → HTML → PDF
python scripts/render_html.py resume.yaml -o resume.html --pdf resume.pdf
python scripts/qa.py resume.pdf resume.yaml --pages 2
python scripts/preview.py resume.pdf

# 无浏览器时的兜底路径
python scripts/render.py resume.yaml -o resume.pdf

# 从事实基线派生岗位版本，拒绝覆盖
python scripts/fork.py _master/resume.yaml versions/target.yaml --target "目标岗位"
```

## 五、YAML 最小结构

```yaml
meta:
  name: 姓名
  role: 求职意向             # 无 JD 时可沿用原简历或写通用方向
  contact: ["电话", "邮箱", "城市"]
  links: [{label: 作品集, url: "https://example.com", short: "example.com"}]
style:
  preset: swiss               # swiss | editorial | mono
  accent: "#2F5BEA"
  density: normal             # tight | normal | airy
sections:
  - title: 教育背景
    items:
      - {org: 学校, role: 专业 · 学历, date: 2021.09 – 2025.06, bullets: ["..."]}
  - title: 工作经历
    items:
      - {org: 公司, role: 职位, date: 2025.07 – 至今, bullets: ["**标签**：具体动作与可验证结果"]}
```

`section` 可用 `items`／`bullets`／`body`；`**...**` 表示加粗。路径相对 YAML 所在目录解析。

## 六、版本与事实基线

- 原简历只读，不覆盖；优化版写入新目录或新文件名。
- 一个岗位一份派生 YAML；事实变化先回 `_master/resume.yaml` 修改，再重新派生，避免不同岗位版本互相继承漂移。
- 修改说明写清：改了什么、依据是什么、哪些数字或术语仍待用户确认。

## 七、边界

- 支持从 PDF／DOCX／Markdown／TXT 读取旧简历；扫描件或复杂版式可能误读，低置信度字段必须确认，不能猜。
- 不做 ATS 关键词打分、自动投递、面试题库和招聘平台对接。
- 不做视觉炫技；三套主题只改版式，不改事实。
- 不承诺面试、录用、薪资或 offer 概率。
