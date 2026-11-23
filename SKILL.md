---
name: resume-master
description: >
  通用中文简历的内容优化与 A4 排版工作流，有无旧简历、目标岗位 JD、个人主页、GitHub 或作品集都能开始。无简历时用一轮集中问卷收集真实经历，少量缺失再集中补问；默认经过结构线框与全文文字稿两次确认，正文定稿后重新终排并做真实渲染验收。支持 PDF、DOCX、Markdown、TXT、YAML 输入，交付 PDF 与可编辑源文件。触发：写简历、改简历、没有简历想新建、简历优化、按 JD 定制、只有 JD、根据 GitHub 或主页写简历、简历排版、导出 PDF。不做：自动投递、面试题库、招聘平台对接、ATS 打分。
---

# 简历工坊 Pro

> 不先问“走哪种模式”，先识别已经有什么。所有入口最终汇入：**素材齐备 → 确认 1 结构线框 → 确认 2 全文文字稿 → 终排与验收**。

## 一、所有输入入口

| 已有材料 | 启动动作 |
|---|---|
| **已有简历**：仅简历，或简历 + JD | 直接读取并审计；仅简历没有 JD 也能优化，不强迫补目标岗位 |
| **无简历，但有零散经历** | 先整理已有事实，再用一轮集中问卷补齐，不逐题访谈 |
| **只有 JD** | JD 只用于确定素材优先级，仍须通过问卷获得个人经历，不能把要求写成经历 |
| **个人主页 / GitHub / 作品集等链接** | 读取公开内容作为素材线索，集中核对归属、时间和结果；公开可见不等于用户已确认 |
| **没有任何材料** | 直接发一轮通用、易回答的集中问卷，不要求先制作旧简历 |

PDF、DOCX、Markdown、TXT、YAML、图片／扫描件按环境能力读取。保留原文件，不覆盖。

## 二、按需加载

1. 输入识别与事实缺口：[`references/intake.md`](references/intake.md)。
2. 无简历或素材不足：[`references/questionnaire.md`](references/questionnaire.md)，整轮发出，不逐题追问。
3. 事实、隐私、归属：[`references/guardrails.md`](references/guardrails.md)，每次都守。
4. 结构线框与确认 1：[`references/wireframe.md`](references/wireframe.md)。
5. 内容改写与确认 2：[`references/content-rules.md`](references/content-rules.md)、[`references/provenance.md`](references/provenance.md)、[`references/emphasis.md`](references/emphasis.md)。
6. 脱敏方法案例：[`references/case-studies.md`](references/case-studies.md)，只借判断，不套数字。
7. 终排与交付：[`references/design-system.md`](references/design-system.md)、[`references/operating-discipline.md`](references/operating-discipline.md)、[`references/delivery.md`](references/delivery.md)。

## 三、主流程：两次确认，最后重新终排

1. **读取与审计**：提取教育、工作、项目、技能、联系方式、链接、日期和数字；区分 A 已核验／B 用户陈述／C Agent 推断／D 未知，识别团队成果、个人贡献与协助角色。
2. **集中补齐**：无简历或素材不足时，一次发完通用问卷；已有简历时，只把影响成稿的缺失合并成一轮。少量缺失继续**集中补问**，不重复问已答内容。**不生成带 `【待补】` 的初稿**；非关键项用户不愿补，就省略并记录。
3. **确认 1｜结构线框**：先给目标页数、章节顺序、页面配比、阅读顺序、题头与日期布局、主题／密度和拟突出重点。此阶段确认“先看什么、怎么排才好看”，不提前渲染三套完整简历。用户确认后再写全文。
4. **确认 2｜全文文字稿**：一次性给出完整正文，不逐段挤牙膏；同时给标蓝／不标蓝清单。若有 JD，附“要求—已有证据—真实缺口—处理”差距表。用户确认后才进入终排。
5. **终排**：以确认的同一内容源生成 HTML／PDF。正文定稿后必须重新评估内容膨胀、页数、分页位置、孤行、密度和末页留白，不机械沿用线框。非语义排版可直接修；需要删改语义则回到确认 2。
6. **验收与交付**：运行 `scripts/qa.py` 与 `scripts/preview.py`，检查真实渲染的层级、留白、对齐、边缘、链接和页数。默认交付 PDF＋可编辑源文件＋修改说明；未做的验收如实写“未做”。

用户明确说“跳过确认，直接交付”时可合并两次确认，但仍须保留线框、全文和重点清单，且不能跳过事实与终排验收。

## 四、命令

```bash
# 主路径：确认后的 YAML → HTML → PDF
python scripts/render_html.py resume.yaml -o resume.html --pdf resume.pdf
python scripts/qa.py resume.pdf resume.yaml --pages 2
# 仅当用户明确确认某个词是具体工作表述时，才显式豁免：
# python scripts/qa.py resume.pdf resume.yaml --pages 2 --allow-word "赋能"
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
  role: 求职意向
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
- 一个岗位一份派生 YAML；事实变化先回 `_master/resume.yaml` 修改，再重新派生。
- 修改说明写清：改了什么、依据是什么、哪些内容被省略、哪些验收未做。
- 公开案例、测试和文档只使用虚构或充分脱敏素材，不把用户姓名、联系方式、公司、客户与内部指标写回仓库。

## 七、边界

- 扫描件、复杂版式与公开链接都可能误读或过期；低置信度字段必须集中核对。
- 不做 ATS 关键词打分、自动投递、面试题库和招聘平台对接。
- 不做视觉炫技；三套主题只改版式，不改事实。
- 不承诺面试、录用、薪资或 offer 概率。
