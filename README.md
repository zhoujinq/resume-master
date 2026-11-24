# 简历工坊 Pro · resume-master

**v3.2.0**｜MIT｜[项目预览](https://zhoujinq.github.io/resume-master/)

给 AI Agent 使用的中文简历工作流。v3 把目标从“提供更多模板”改为“减少错误自由度”：一份事实基线、一份定向正文、一个 DOCX 排版源、一次 Microsoft Word 同源导出、一套真实产物验收。

唯一视觉标准：**思源宋体＋思源黑体，强调色 #2F5BEA**。没有主题切换、字体覆盖、备用渲染器或第二条 PDF 路线。

## 为什么推倒重来

真实封板过程证明，质量来自内容证据、明确归属、克制排版和真实 Word 验收，而不是模板数量。旧实现的多路线造成多个事实源、排版源和验收口径，正是返工与回滚的共同土壤。

v3 将 11 月 20—24 日的 16 类问题归并为八个根因：目标漂移、多个真相源、授权边界模糊、局部补丁替代架构修正、代理指标冒充真实结果、交接丢失已确认状态、成功样本过拟合，以及用规则堆积替代真实任务学习。对应门禁见 [阶段性复盘](docs/postmortem-2026-11-20-to-24.md)。

## 最快使用

把整个文件夹交给支持 `SKILL.md` 的 Agent，并说：

> 请使用 resume-master 优化我的简历。先建立事实证据台账，再按 JD 定向正文；不要编造数字或把团队成果写成我个人成果。最后交付可编辑 DOCX、Microsoft Word 同源 PDF 和完整 QA。

无旧简历、只有 JD 或零散经历也可以开始。个人主页、GitHub、Vibe Coding／其他项目、作品集和照片均为可选素材，不是好简历的默认组成；没有就省略，不生成空区或虚构内容。材料不足时一轮集中补问；只有 JD 时，JD 只决定素材优先级，不会变成你的经历。

只想上传一个文件时，使用自包含的 [Lite 文件版](lite/文件版skill.md)。Lite 同样遵循 v3.2.0 的唯一视觉标准，但不承诺脚本和 Word 自动化一定可用。

## v3.2.0 的七个核心机制

1. **证据台账**：每条 bullet 引用事实 ID；事实记录来源、确认状态、归属和可答辩说明。暂定事实不能进入终稿。
2. **JD 差距映射**：区分已有证据与真实缺口，不生成虚构匹配分，不用 ATS 分数代替招聘判断。
3. **结构套话审计**：定位铺垫、夸大、无名权威、抽象三连、对话残留等模式。弱信号只 WARN，真实对比、日期和专业术语不自动改写；命中数不是写作配额。
4. **改前改后事实对账**：纯润色只允许 `bullet.text` 变化，数字词元不得增删；机械对账后仍保留人工语义复核，不输出 AI 概率、人味百分比或伪精确写作分。
5. **按需信息架构**：个人主页、GitHub、任何项目和照片都可省略；章节由真实证据与 JD 决定。未配置链接与“配置后丢失”严格区分，前者 N/A，后者 FAIL。
6. **唯一 DOCX 路线**：正文、编号、链接、照片和 Logo 写入可编辑 OOXML；PDF 只由 Microsoft Word 从同一 DOCX 导出。
7. **真实 QA**：检查全文一致、文本层、实际字体与字号、颜色、链接、照片坐标、越界、逐页视觉、重复导出像素差和真实 Word 编辑—撤销。

本轮完整研读指定文章正文及 48 张配图，并审查 Humanizer 4.0.0。吸收真实样本、逐句反馈、同题对照和渐进披露的方法，但不照搬英文禁令，不把十篇样本变成启动门槛。写作细节见 [写作与同题对照](references/writing-style.md)；Humanizer 原作者 MIT 许可保留在 `licenses/humanizer-LICENSE`。

自动校验只证明“可追溯、可检查”，不声称自动证明事实真实，也不替代用户最终确认。

## 快速验证公开虚构样例

安装 Python 依赖：

```bash
python -m pip install -e .
```

运行门禁与唯一生产链：

```bash
python scripts/evidence.py examples/sample.yaml --json evidence.json
python scripts/content_audit.py examples/sample.yaml --json content-audit.json
# 纯表达润色时：python scripts/content_audit.py revised.yaml --baseline before.yaml --json writing-audit.json
python scripts/render_docx.py examples/sample.yaml -o sample.docx --pdf sample.pdf --repeat-pdf sample-repeat.pdf
python scripts/preview.py sample.pdf
```

PDF 导出需要 Windows Microsoft Word；只生成 DOCX 不需要 Word。字体子集化会先保留原始产物，再比较逐页文本、链接和像素哈希；任何变化都会中止替换。脚本不安装字体、不修改注册表或 Word 全局选项。

在临时副本验证真实 Word 编辑—撤销：

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_word_edit.ps1 -Docx sample.docx -FindText "林示例" -ReplaceWith "测试替换" -EvidencePath edit-undo.json
```

逐页实际查看 PNG 后运行完整 QA：

```bash
python scripts/qa.py examples/sample.yaml --pdf sample.pdf --docx sample.docx --repeat-pdf sample-repeat.pdf --word-export-log sample.word-export.json --edit-undo-evidence edit-undo.json --visual-evidence sample.pdf.p1.png --report-json qa.json --report-md qa.md
```

多页简历为每一页追加一个 `--visual-evidence`。目标页数可写在 YAML 的 `delivery.pages`，也可用 `--pages` 覆盖。目标页数只是验收口径；需要强制从新页开始的章节必须另写 `page_break_before: true`，渲染器会创建独立分节。

公开发布虚构样例报告时，可脱敏本机路径；状态原样保留：

```bash
python scripts/publish_qa.py qa.json qa-public.md
```

## 数据契约

```yaml
meta:
  name: 林示例
  role: AI 产品用户运营
  contact: [深圳, {t: example@example.com, u: "mailto:example@example.com"}]
delivery: {pages: 1}
facts:
  - id: F001
    statement: 独立设计 12 封新人引导邮件，示例激活率为 30%。
    status: confirmed
    ownership: personal
    source: 虚构样例事实
    note: 可解释激活口径与邮件分批方式。
sections:
  - title: 工作经历
    items:
      - org: 示例公司
        role: 用户运营
        date: 2023.07–至今
        bullets:
          - {text: "独立设计 [[12 封]]新人引导邮件，示例激活率达到 **30%**。", facts: [F001]}
```

完整字段和 JD 映射见 [`examples/sample.yaml`](examples/sample.yaml)。上面的最小骨架没有外部链接、项目或照片，仍是完整输入；只有实际存在且能增加岗位判断信息时才添加 `meta.links`、项目章节或 `meta.photo`。空章节与已配置但无 URL 的链接会被阻断。`[[...]]` 是蓝色加粗，`**...**` 是普通加粗；两者都进入同一正文流。`delivery.pages` 不控制分页；需要另起一页的章节设置 `page_break_before: true`，再用真实 Word 页数核对目标。

## 防重犯测试族

| 测试族 | 阻断的问题 |
|---|---|
| D · 单路线 | 主题残留、样式覆盖、多排版源、网页与代码不一致 |
| E · 事实证据 | 数字无来源、暂定事实进终稿、团队成果个人化、派生降级、空章节或无效链接 |
| A · 真实产物 | DOCX/PDF 文本和链接不一致、字体或照片错误、无链接空段、真实 Word 不可编辑 |
| Q · QA 自证 | 未做冒充通过、0/0 假通过、像素比较漏报、比较器误报、严格项被核心通过掩盖 |
| H · 交接与范围 | 已确认事实被降级、来源哈希变化未提示、公开仓库泄漏隐私 |
| W · 写作与对账 | 结构套话、误伤真实表达、对话残留、非正文字段或数字漂移、语义假通过 |

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

开发依据：[需求依赖矩阵](docs/requirements-matrix-v3.2.0.md) · [第一性原理与反方评审](docs/design-rationale-v3.2.0.md) · [验收规则](references/acceptance.md)。

## 验收口径

- **核心**：证据、页数、源文覆盖、全文一致、文本层、链接、字体、字号、颜色、照片、越界和逐页视觉。
- **严格**：重复导出同 DPI 逐页像素差为 0、真实 Word 编辑—撤销、项目符号间距。
- **建议**：照片建议像素、末页留白、PDF 体积、真实 JD 缺口提醒。

`PASS／WARN／FAIL／NOT_RUN／NOT_APPLICABLE` 必须如实区分。未配置可选链接或照片时是 `NOT_APPLICABLE`；已配置却丢失仍是 `FAIL`。核心通过不代表严格全过；建议 WARN 不等于核心失败。

## 边界

- 不做 ATS 打分、自动投递、招聘平台对接、面试题库，不承诺面试或录用结果。
- 没有 Microsoft Word 时，PDF 双导出和 Word 编辑—撤销必须保持 `NOT_RUN`，不能换第二条路线冒充完成。
- 公开样例和测试全部虚构；真实姓名、联系方式、公司、客户、内部指标、照片和本机路径不得进入公开仓库。
- Git 历史保留旧版本用于回滚；活跃代码、样例、Skill 与项目页面只维护 v3.2.0 这一条生产标准。
