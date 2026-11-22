# 简历工坊 Pro · resume-master

> 一份简历只有两个问题：**说什么**（内容）和**怎么说**（版式）。
> 大多数简历工具只解决一个。这里两个都管，而且最后有两道门禁。

一个给 AI Agent 用的中文简历技能（Skill）：从目标 JD 出发审计并重构经历，写出 A4 精度的 HTML，用 Chrome 无头打印成 PDF，再跑计算项门禁 + 视觉复核，两道都过才允许交付。

**介绍页**：https://zhoujinq.github.io/resume-master/

- **版本**：v0.5.0
- **许可**：MIT
- **依赖**：Python 3 + `pyyaml` + `PyMuPDF`；PDF 主路径需要本机 Chrome（无 Chrome 走 reportlab 兜底）

---

## 它解决什么

改简历的返工，绝大多数来自三个地方：

1. **内容只有动作，没有判断**：写"负责区域渠道开拓"，谁都能写；写"渠道散、跟进靠记忆，所以先做客户分层再看板化跟进，3 个月开发 36 家"，才有信息量。
2. **版式靠装饰撑**：加底色、加图标、加彩色分隔线，把颜色和 logo 全去掉就散了。
3. **没人在交付前拦一道**：错别字、越界、禁忌词、末页只剩两行，全靠肉眼撞运气。

这个技能把三件事拆成三条硬约束：内容宪法（`content-rules.md`）、版式规范（`design-system.md`）、可执行门禁（`qa.py`）。

---

## 四条路由（选一条，不给菜单）

| 路由 | 请求形态 | 前置条件 | 产出 |
|---|---|---|---|
| **A 新建** | 从零写一份 | 素材齐全（学历 / 经历 / 项目） | `resume.yaml` + PDF |
| **B 按 JD 定制** | 已有一份，改投某岗位 | master + JD 原文 | 新 YAML + 差距表 |
| **C 只换版式** | 内容不动，换皮 | 已定稿 YAML | 新 PDF（同内容） |
| **D 体检** | 不动内容，只找问题 | PDF 或 YAML | `qa-report.txt` |

请求已能对上其中一行时不给选项；只在歧义时问**一个**判别问题。

## 三道门禁

| 门 | 位置 | 通过条件 |
|---|---|---|
| **G1 事实确认** | 内容定稿前 | 用户逐条确认数字、角色、范围 |
| **G2 定稿** | 渲染前 | 章节顺序、取舍、删减已确认 |
| **G3 交付** | 交付前 | `qa.py` 全绿 + 视觉复核四项通过 |

门禁处必须停。越过门禁直接产出成品，是最常见的返工原因。

## 三套版式

| 版式 | 姓名 | 强调色 | 气质 |
|---|---|---|---|
| `swiss` | 等线 Bold 25pt | `#2F5BEA` 蓝 | 克制、可信（默认） |
| `editorial` | 宋体 29pt / 字距 3.0 | `#B4472B` 砖红 | 有书卷气 |
| `mono` | 等宽 21pt | `#0F766E` 墨绿 | 技术文档感 |

A4 210×297mm，左右 18mm，版心 174mm。层级靠**留白 → 字重 → 细线 → 颜色**，颜色一页最多用 3 次。
换版式不改内容；换版式后某条读着别扭，是内容的问题，不是版式的问题。

---

## 命令

```bash
# 主路径：YAML → HTML → PDF
python scripts/render_html.py resume.yaml -o resume.html --pdf resume.pdf

# 门禁：越界 / 页数 / 末页留白 / 禁忌词 / 占位符 / 联系方式 / 日期格式 / 内容密度
python scripts/qa.py resume.pdf resume.yaml --pages 2

# 视觉复核素材：PDF → PNG
python scripts/preview.py resume.pdf

# 从基线派生一个岗位版本（拒绝覆盖已有文件）
python scripts/fork.py _master/resume.yaml versions/target-2026-11.yaml --target "示例目标岗位"
```

**为什么先 HTML 再 PDF**：字距、行高、两端对齐、悬挂缩进、分页控制都是 CSS 原生能力，比直接画 PDF 精细；同一份 HTML 还能直接当网页用。Chrome 打印保证 1:1 还原 A4。

**兜底路径（无浏览器）**：`python scripts/render.py resume.yaml -o resume.pdf`（reportlab 直出，版式精度次一档）。

## 版本管理（master-first）

```
workspace/
  _master/resume.yaml        # 基线，只在这里维护事实
  versions/
    target-2026-11.yaml      # 派生：改措辞与取舍，不改事实
```

改了事实要回 `_master` 改一遍再重新派生，否则下个岗位会继承上一版的漂移。

---

## 目录结构

```
SKILL.md                      # 路由 + 护栏 + 流程 + 版本管理（Agent 入口）
references/
  content-rules.md            # 一条 bullet 怎么写：问题 → 判断 → 动作 → 结果
  provenance.md               # 可以改说法，不可以改事实（8 种合法 / 6 种禁止）
  design-system.md            # 栅格、字号阶梯、三套版式差异
  operating-discipline.md     # 四条路由、三道门、责任源修复
  guardrails.md               # 事实四级分层、隐私红线、注入防御、不做承诺
scripts/
  render_html.py              # YAML → HTML →（Chrome）PDF
  render.py                   # YAML → PDF（reportlab 兜底）
  qa.py                       # 计算项门禁，能红，退出码 1 = 阻断
  preview.py                  # PDF → PNG，供视觉复核
  fork.py                     # 从 _master 派生版本，拒绝覆盖
assets/
  resume.css                  # A4 版式样式表
  banned-words.json           # 19 个不可证伪的空话词，命中 ≥6 次阻断
examples/
  sample.yaml                     # 单文件完整样例（虚构人物）
  workspace/_master/resume.yaml   # 基线样例
  workspace/versions/             # 派生样例（saas / hardware 两个方向）
  one-pager.yaml                  # 一页纸商业假设（同一引擎渲染非简历文档）
  demo-{swiss,editorial,mono}.pdf # 三套版式的成品样例
  one-pager.pdf                   # 一页纸成品
```

## 装回 WorkBuddy

技能目录默认在 `~/.workbuddy/skills/`，把本仓库放成 `resume-master` 子目录即可（重启后识别）：

```bash
git clone <this-repo> "$HOME/.workbuddy/skills/resume-master"
```

其他支持 `SKILL.md` 约定的 Agent（Claude Code / Codex 等）放进各自的 skills 目录同构。

---

## 能力边界

- **不做** ATS 关键词打分。
- **不做** 视觉炫技（彩条、时间轴、图标墙）；本引擎的审美是克制的版式。
- **不做** 英文润色，只做结构与版式迁移。
- **不做** 从 PDF 读取旧简历（扫描件尤其不行，数字字段幻觉率高）：要么给 YAML，要么人工重录。
- 中文排版依赖 Windows 字体（等线 / 宋体 / 黑体）；换机器改 `scripts/render.py` 顶部 `FONT_MAP`。

---

## 关于 examples

`examples/` 全部为**虚构样例**（张三 / example.com / 示例公司），仅用于演示渲染与门禁，不含任何真实个人信息。替换成你自己的素材时，注意 YAML 里的 `contact`、`assets/photo.jpg`、`logo` 会随 PDF 一起对外分发。

`demo-mono.pdf` 的末页占用低于 40%，`qa.py` 会给出 ⚠️ 提醒——这是 mono 高密度预设下同一份内容的正常结果，不是 bug；正式使用时按提示补内容或压成一页。
