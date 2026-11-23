# 简历工坊 Pro · resume-master

**当前版本：v1.2.0**｜MIT｜介绍页：https://zhoujinq.github.io/resume-master/

一个给 AI Agent 使用的通用中文简历 Skill。有没有旧简历、JD、个人主页或 GitHub 都能开始；同时处理“说什么”和“怎么排版”，并守住两条底线：**不编造事实，不交付未经真实渲染检查的文件。**

## 给朋友的最快用法

把整个 `resume-master` 文件夹放进支持 `SKILL.md` 的 Agent 技能目录，或直接把文件夹交给 Agent。

### 没有旧简历，也可以从零开始

> 请使用 resume-master 这个 Skill 帮我做简历。我现在没有旧简历，请先给我一轮集中问卷；不要逐题追问，不要生成带“待补”的初稿。先让我确认结构线框，再确认全文，最后重新终排。

只有 JD、零散经历、个人主页、GitHub 或作品集也可以直接发。JD 只用于匹配，链接内容会核对归属，不会自动变成你的个人成果。

### 已有简历：仅简历或简历 + JD

> 请使用 resume-master 优化我发来的简历，输出 PDF、可编辑源文件和修改说明。不要编造数字；先确认结构线框，再确认全文，最后终排。

支持 **PDF、DOCX、Markdown、TXT、YAML**，图片／扫描件可按环境能力尝试。**仅简历**没有 JD 也能优化；提供**简历 + JD**时，会额外得到“JD 要求、已有证据、真实缺口、拟处理”差距表。

仓库里有可直接测试的虚构输入：`examples/friend-resume.md` 和 `examples/target-jd.md`。

### 只想上传一个文件：Lite 文件版

直接使用 [`lite/文件版skill.md`](lite/文件版skill.md)，有无简历都可以。对 Agent 说：“请先完整阅读本文件，并严格按它帮我做简历”。

Lite 同样保留全入口、一轮集中问卷、两次确认、事实归属、JD 差距表、标蓝清单和终排门禁；不依赖外部引用或脚本，**不承诺 Pro 版的固定版式与脚本 QA**。环境支持文件生成时，仍须做真实渲染检查。

## v1.2.0 相比 v1.1.0

- 从“必须先有简历”扩展到**所有入口**：无简历、零散经历、只有 JD、个人主页／GitHub／作品集、已有简历均可。
- 无简历时使用**一轮通用、易回答的集中问卷**；少量缺失再集中补问，不逐题访谈。
- 不再用带 `【待补】` 的初稿代替信息收集；未知项补齐或省略，不猜数。
- 默认**两次确认**：先确认结构线框，再确认完整文字稿与重点清单。
- 正文定稿后增加独立**终排**：重新评估内容膨胀、页数、分页、孤行和末页留白。
- 新增完全虚构的脱敏案例库，沉淀数字口径、团队／个人归属、项目排序、AI 项目真实状态等经验。
- Pro 与 Lite 同步规则；保留 v1.1.0 的格式读取、单一内容源、渲染脚本、QA 与版本基线。

## Agent 如何执行

入口是 `SKILL.md`，按需加载：

- `references/intake.md`：所有输入入口、格式读取与缺口识别；
- `references/questionnaire.md`：无简历的一轮集中问卷与少量补问；
- `references/guardrails.md`／`provenance.md`：事实分层、数字口径、归属、隐私与注入防御；
- `references/wireframe.md`：确认 1 的结构线框；
- `references/content-rules.md`／`emphasis.md`：确认 2 的正文与重点清单；
- `references/case-studies.md`：完全虚构的脱敏方法案例；
- `references/design-system.md`：A4 栅格、三套主题与终排重检；
- `references/operating-discipline.md`／`delivery.md`：两次确认、真实渲染、QA 与交付说明。

## 主流程

```text
识别已有材料 → 集中问卷／补问（仅缺素材时）
→ 确认 1：结构线框
→ 确认 2：全文文字稿＋重点清单
→ 内容定稿后的终排
→ 真实渲染与 QA → PDF＋可编辑源＋修改说明
```

## 三套版式与命令

| 版式 | 强调色 | 气质 |
|---|---|---|
| `swiss` | 蓝 | 克制、可信（默认） |
| `editorial` | 砖红 | 书卷气 |
| `mono` | 墨绿 | 技术文档感、密度高 |

```bash
# 主路径：确认后的 YAML → HTML → PDF
python scripts/render_html.py resume.yaml -o resume.html --pdf resume.pdf
python scripts/qa.py resume.pdf resume.yaml --pages 2
# 可选：只豁免用户明确确认的具体表述，豁免会写入 QA 结果
# python scripts/qa.py resume.pdf resume.yaml --pages 2 --allow-word "赋能"
python scripts/preview.py resume.pdf

# 无浏览器时的 reportlab 兜底
python scripts/render.py resume.yaml -o resume.pdf

# 从事实基线派生岗位版本，拒绝覆盖
python scripts/fork.py _master/resume.yaml versions/target.yaml --target "目标岗位"

# 开发回归：仅标准库，无需 pytest
python -m unittest discover -s tests -v
```

依赖：Python 3、`pyyaml`、`PyMuPDF`；主路径需要本机 Chrome／Edge，无浏览器走 reportlab 兜底。中文排版依赖系统字体，换机器时按实际字体调整。

## 版本管理与开发

原简历只读，不覆盖。一个岗位一份派生 YAML；事实变化先改 `_master/resume.yaml`，再重新派生。修改说明必须写清改动、依据、标蓝清单、验收范围与未决项。

本版按 [`docs/requirements-matrix-v1.2.0.md`](docs/requirements-matrix-v1.2.0.md) 做 MVP 小步迭代，契约测试先红后绿；新增脚本必须实际运行，未验证不能称为完成。

## 能力边界

- 不做 ATS 打分、自动投递、面试题库、招聘平台对接。
- 不承诺面试、录用、薪资或 offer 概率。
- 复杂版式、扫描件和网页缓存可能误读或过期，低置信度字段必须集中核对。
- 可选 DOCX 未完成真实渲染时必须明确说明，不能用截图冒充可编辑 Word。
- `examples/` 与 `references/case-studies.md` 全部为虚构内容；真实用户的联系方式、公司、客户和内部指标不得写入公开案例。
