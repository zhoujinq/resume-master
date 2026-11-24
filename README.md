# 简历工坊 Pro · resume-master

**当前版本：v2.0.0**｜MIT｜介绍页：https://zhoujinq.github.io/resume-master/

给 AI Agent 使用的通用中文简历 Skill。保留全入口、事实治理、两次确认与三套 HTML 主题，新增 **可编辑 DOCX → Microsoft Word 同源 PDF** 和可审计验收报告。底线不变：**不编造事实，不交付未经真实渲染检查的文件，不把未做写成通过。**

## 给朋友的最快用法

把整个 `resume-master` 文件夹放进支持 `SKILL.md` 的 Agent 技能目录，或直接把文件夹交给 Agent。

### 无简历／没有旧简历，也可以从零开始

> 请使用 resume-master 帮我做简历。我没有旧简历，请先给我一轮集中问卷，不要逐题追问或编造。先确认结构线框，再确认全文，最后终排和真实验收。

只有 JD、零散经历、个人主页、GitHub 或作品集也可以直接发。JD 只用于匹配，公开内容不会自动变成你的个人成果。

### 已有简历／简历 + JD

> 请使用 resume-master 优化我的简历。我要可编辑 DOCX、同源 PDF 和修改说明；不要编造数字，不要为凑页数删字。

支持 **PDF、DOCX、Markdown、TXT、YAML**，图片／扫描件可按环境能力尝试。仅简历没有 JD 也能优化；有 JD 时附差距表。虚构输入见 `examples/friend-resume.md` 与 `examples/target-jd.md`。

### 只想上传一个文件：Lite

使用 [`lite/文件版skill.md`](lite/文件版skill.md)。它完全自包含，保留事实与流程护栏，但不承诺 Pro 的固定版式、Word 导出器或脚本 QA。

## v2.0.0 核心升级

- 新增 `scripts/render_docx.py`：YAML → 可编辑 DOCX，正文不使用文本框，照片等比，URL 是真实 OOXML 链接。
- 新增 `scripts/export_word.ps1`：PDF 只由本机 **Microsoft Word** 从同一 DOCX 导出，不用浏览器或系统打印驱动冒充。
- QA 增加源文覆盖、DOCX/PDF 归一化全文一致、DOCX/PDF 链接、实际字体、PDF 照片像素与重复导出逐页像素比较。
- 报告区分 **核心／严格／建议**，使用 `PASS／WARN／FAIL／NOT_RUN／NOT_APPLICABLE`；严格项未做时总体保持 `INCOMPLETE`。
- 保留 v1.2.0 的全入口、集中问卷、两次确认、终排重检、HTML 三主题、ReportLab 兜底、Lite 和版本派生。

## 命令

```bash
# Word 主路线：双导出用于确定性验证
python scripts/render_docx.py resume.yaml -o resume.docx --pdf resume.pdf --repeat-pdf resume-repeat.pdf
python scripts/preview.py resume.pdf

# Agent 逐页看过 PNG 后，再登记视觉证据
python scripts/qa.py resume.pdf resume.yaml --docx resume.docx --repeat-pdf resume-repeat.pdf --pages 2 --visual-evidence resume.pdf.p1.png --visual-evidence resume.pdf.p2.png --report-json qa.json --report-md qa.md

# 可选严格字体白名单
python scripts/qa.py resume.pdf resume.yaml --docx resume.docx --font-allow SourceHanSans --font-allow Arial --visual-evidence resume.pdf.p1.png

# HTML／浏览器路线
python scripts/render_html.py resume.yaml -o resume.html --pdf resume.pdf
# ReportLab 兜底
python scripts/render.py resume.yaml -o resume.pdf
# 派生岗位版本
python scripts/fork.py _master/resume.yaml versions/target.yaml --target "目标岗位"
# 回归测试
python -m unittest discover -s tests -v
```

依赖：Python 3、`pyyaml`、`PyMuPDF`、`python-docx`；照片处理使用 `Pillow`，ReportLab 兜底另需 `reportlab`。Word PDF 导出需要 Windows Microsoft Word；HTML PDF 需要 Chrome／Edge。Word 导出后只对 PDF 内嵌字体做无损子集化，QA 必须复核文字、链接和页面。脚本不安装、卸载或转换字体，不修改注册表或 Word 全局选项。

## Agent 如何执行

入口是 `SKILL.md`，按需加载 `references/`。主流程：

```text
识别材料 → 集中问卷／补问（仅缺素材时）
→ 确认 1：结构线框
→ 确认 2：全文文字稿＋重点清单
→ 内容定稿后的终排
→ 选择唯一排版路线 → 真实渲染与 QA → 交付与未决项
```

## 验收不再只报“全绿”

| 层级 | 例子 |
|---|---|
| 核心 | 页数、越界、源文覆盖、DOCX/PDF 全文一致、真实链接、文本层、逐页视觉复核 |
| 严格 | 字体白名单、第二次导出逐页像素差为 0、实际 Word 编辑—撤销 |
| 建议 | PDF 内照片建议像素等 |

`NOT_RUN` 不计入通过；建议未达单独列示。QA 退出码：`0` 核心闭合、`1` 有失败、`2` 核心未完成。严格项未做仍会在报告中保留 `INCOMPLETE`。

## 版本管理与开发

原简历只读，一个岗位一份派生 YAML；事实变化先改 `_master/resume.yaml`。修改说明写清改动、依据、省略内容、验收范围与未决项。

本版按 [`docs/requirements-matrix-v2.0.0.md`](docs/requirements-matrix-v2.0.0.md) 做 MVP／TDD 小步迭代；新增脚本必须真实运行，未验证不能称为完成。实际渲染发现的问题与验证结果见 [`docs/release-notes-v2.0.0.md`](docs/release-notes-v2.0.0.md)。

## 能力边界

- 不做 ATS 打分、自动投递、面试题库、招聘平台对接，不承诺面试、录用、薪资或 offer 概率。
- HTML、ReportLab、DOCX 是不同排版路线，不能互相宣称像素一致或 Word 同源。
- 复杂版式、扫描件和网页缓存可能误读或过期，低置信度字段集中核对。
- `examples/` 与案例均为虚构；真实用户的联系方式、公司、客户、内部指标和本机路径不得写入公开仓库。
