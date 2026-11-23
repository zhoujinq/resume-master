# 简历工坊 Pro · resume-master

**当前版本：v1.1.0**｜MIT｜介绍页：https://zhoujinq.github.io/resume-master/

一个给 AI Agent 使用的中文简历 Skill。它同时处理“说什么”和“怎么排版”，并守住两条底线：**不编造事实，不交付未经真实渲染检查的文件。**

## 给朋友的最快用法

把整个 `resume-master` 文件夹放进支持 `SKILL.md` 的 Agent 技能目录，或直接把文件夹与简历一起交给 Agent，然后照抄下面一句。

### 方式 1：仅简历（默认，不需要 JD）

> 请使用 resume-master 这个 Skill，优化我发来的现有简历，输出一版优化后的 PDF、可编辑源文件和修改说明。不要编造数字；不确定的地方集中问我。

支持现有简历为 **PDF、DOCX、Markdown、TXT 或 YAML**。扫描件也能尝试，但数字和日期需要核对。

你会得到：通用优化版 PDF、可编辑 YAML（通常附 HTML）、修改说明，以及必要的待确认清单。

### 方式 2：简历 + JD（更匹配目标岗位）

> 请使用 resume-master 这个 Skill，根据我发来的现有简历和目标岗位 JD，输出一版更匹配该岗位的 PDF、可编辑源文件、JD 匹配差距表和修改说明。只强化我真实做过的经历，不要把 JD 要求写成我的经历。

你会额外得到一张差距表：JD 要求、已有证据、真实缺口、拟强化位置。

仓库里有可直接测试的虚构输入：`examples/friend-resume.md` 和 `examples/target-jd.md`。

### 只想上传一个文件：Lite 文件版

直接使用 [`lite/文件版skill.md`](lite/文件版skill.md)。把这个文件与简历一起交给 Agent，再说“请先完整阅读本文件，并严格按它优化我的简历”。

Lite 保留两种模式、事实归属、JD 差距表、标蓝清单和修改说明；不依赖外部引用或脚本。**它默认先交付完整文字稿，不承诺 Pro 版的固定版式与脚本 QA**；环境支持文件生成时，仍须做真实渲染检查。

## v1.1.0 相比旧版

- 从“必须有 JD”改为**仅简历就能优化**；JD 是可选增强。
- 从“拒绝读取 PDF 旧简历”改为支持 PDF／DOCX／MD／TXT／YAML，并标注扫描件与低置信度风险。
- 默认少打断：高影响问题合并一轮，其余采用可逆默认并记录，不用提问代替交付。
- 新增标蓝 proposal 与不标蓝清单：正常正文和蓝色加粗重点分开，默认少标。
- 禁忌词不再机械替换；用户确认的具体表述和真实工作方式优先。
- PDF、HTML、可选 Word 来自单一内容源；Word 必须真实渲染后才能声称与 PDF 一致。
- 增加标准库契约测试与隐私扫描，仓库不包含原作者的私人简历数据。

## Agent 如何执行

入口是 `SKILL.md`，按需加载：

- `references/intake.md`：两种模式、输入读取、最少打断；
- `references/guardrails.md`：事实分层、归属词、隐私与注入防御；
- `references/content-rules.md`／`provenance.md`：内容重构与合法改写边界；
- `references/emphasis.md`：标蓝与不标蓝清单；
- `references/design-system.md`：A4 栅格与三套主题；
- `references/operating-discipline.md`／`delivery.md`：真实渲染、QA 与交付说明。

## 三套版式与命令

| 版式 | 强调色 | 气质 |
|---|---|---|
| `swiss` | 蓝 | 克制、可信（默认） |
| `editorial` | 砖红 | 书卷气 |
| `mono` | 墨绿 | 技术文档感、密度高 |

```bash
# 主路径：YAML → HTML → PDF
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

## 版本管理

原简历只读，不覆盖。一个岗位一份派生 YAML；事实变化先改 `_master/resume.yaml`，再重新派生。修改说明必须写清改动、依据、标蓝清单、验收范围与未决项。

## 能力边界

- 不做 ATS 打分、自动投递、面试题库、招聘平台对接。
- 不承诺面试、录用、薪资或 offer 概率。
- 不把 PDF／DOCX 读取结果当作绝对事实；复杂版式、扫描件和低置信度字段必须集中核对。
- 可选 DOCX 未完成真实渲染时，必须明确说明，不能用截图冒充可编辑 Word。
- `examples/` 全部为虚构内容；真实用户的联系方式、照片和 Logo 会随成品分发，投递前需自行确认。
