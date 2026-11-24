# Resume Master v3.0.0 公开样例 QA

数据来源：仓库内虚构样例。本报告只脱敏本机路径，不改写检查状态，也不声称自动证明事实真实。

**WARN**；核心与严格项无 FAIL／NOT_RUN。建议 WARN 如实保留，不等于核心 FAIL。

| 层级 | 检查 | 状态 | 证据 |
|---|---|---|---|
| core | 证据台账与 JD 映射 | PASS | 12 条事实可追溯 |
| advisory | 内容审计 JD_GAP | WARN | 真实缺口：可量化语言考试成绩 |
| core | 源文覆盖 DOCX | PASS | 缺失 0 段：[] |
| core | PDF 导出 | PASS | 1 页，103630 bytes |
| core | 页数 | PASS | 实际 1，目标 1 |
| core | 源文覆盖 PDF | PASS | 缺失 0 段：[] |
| core | 文本层非空 | PASS | 逐页检查 |
| core | DOCX/PDF 全文一致 | PASS | 仅统一换行与项目符号；数字与字母不删除 |
| core | 占位符 | PASS | [] |
| core | 逐字符越界与页底 | PASS | 0 处；[] |
| core | 实际 PDF 字体 | PASS | ['SourceHanSansSC-Bold', 'SourceHanSansSC-Regular', 'SourceHanSerifSC-Bold', 'SourceHanSerifSC-Regular'] |
| core | 固定字号 | PASS | [8.04, 8.52, 9.48, 9.96, 10.56, 12.96, 33.96] |
| core | 正文与强调色 | PASS | 实际=['0x0', '0x141519', '0x2b3038', '0x2f5bea', '0x5a6069', '0x857f74']；越界=[] |
| core | PDF 真实链接 | PASS | URL 6/6；缺失=[]；额外=[] |
| core | DOCX 真实链接 | PASS | DOCX URL 6/6；缺失=[]；额外=[] |
| core | 链接双端同步 | PASS | PDF 缺失 [] |
| core | 照片坐标与尺寸 | PASS | page=1 x=485.1 y=42.1 w=62.4 h=87.3 |
| advisory | 照片建议像素 | WARN | 照片实际像素 173×242；建议至少 400×560 |
| core | 项目符号行距 | NOT_APPLICABLE | 没有折行项目符号 |
| strict | 项目符号起始间距 | PASS | 起始间距=[16.92, 17.04, 17.07, 16.92, 16.92, 17.04, 17.04, 17.04, 16.92, 17.04, 17.04]pt |
| core | 逐页视觉复核证据 | PASS | 收到 1/1 页；每页须为真实目标产物图像 |
| core | Word COM 导出证据 | PASS | {"exporter": "Microsoft.Office.Interop.Word", "engine_version": "16.0", "input": "sample.docx", "output": "sample.pdf", "repeat_output": "sample-repeat.pdf", "exit_code": 0, "sha256": "eaea6f87d5d874bad9112b2756ce4c70f48c16b55aeb976e177022c73d618a2a", "repeat_sha256": "dcf0c7576c07ee2b53fd0b3c3b1aa0b8157c70225010e07750b5e5004a0421cd", "timestamp": "2026-11-24T19:07:25.5228888+08:00"} |
| strict | 真实 Word 编辑—撤销 | PASS | {"exporter": "Microsoft.Office.Interop.Word", "source": "sample.docx", "temp_copy": true, "before_sha256": "10ef54bf3fe0936052f727245cc77eb70c4b26727251a85735e923d112e5d3f7", "during_sha256": "304c5f2f1f8f9fbc5d18d0c5ce7619cf21e067cf165d606c595ebff986b32c9d", "after_sha256": "10ef54bf3fe0936052f727245cc77eb70c4b26727251a85735e923d112e5d3f7", "replacement_count": 1, "undo_count": 1, "pages_before": 1, "pages_after": 1, "saved": false, "source_unchanged": true, "timestamp": "2026-11-24T19:07:46.9541828+08:00"} |
| strict | 重复导出逐页像素 | PASS | 144 DPI 逐页差分 [0] |
| advisory | 末页留白 | PASS | 逐页文字纵坐标占比=[88.9]；仅提醒 |
| advisory | PDF 体积 | PASS | 0.10 MB；建议不超过 2 MB |

## 补充实证边界

- 真实 V53.1 内容的私有影子输入完成两页 DOCX／Word PDF 双导出；32 条事实、6/6 链接、逐页文本与 144 DPI 重复导出像素差 0 均通过。私有数据、路径和图像不进入公开仓库。
- 另一组完全虚构的无照片、超长链接、三页长文样例完成同一路线验收；15/15 链接、3 页页数、编辑—撤销和逐页像素差 0 均通过。
- 上述补充结果只说明本次实测，不构成对任意环境、任意内容或任意 Word 版本的保证。
