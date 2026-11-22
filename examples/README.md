# examples

全部样例为**虚构内容**：人物「张三」、邮箱 `example.com`、公司均标注（虚构），不含任何真实个人信息。

| 文件 | 演示什么 |
|---|---|
| `sample.yaml` | 单文件完整样例，`style.preset: swiss` |
| `demo-swiss.pdf` / `demo-editorial.pdf` / `demo-mono.pdf` | 同一份内容的三套版式成品，`qa.py` 全绿（mono 的末页占用 35%，会给 ⚠️ 提醒） |
| `workspace/_master/resume.yaml` | master-first 的基线，只在这里维护事实 |
| `workspace/versions/saas-2026-11.yaml` | 派生版本：偏 SaaS 渠道，改职位名与定位，不改事实 |
| `workspace/versions/hardware-2026-11.yaml` | 派生版本：偏硬件分销 |
| `one-pager.yaml` / `one-pager.pdf` | 同一引擎渲染非简历文档（一页纸商业假设），演示 `body` 段与 `note` 小注 |

复现三份 PDF：

```bash
# 逐个改 style.preset（swiss / editorial / mono）后渲染
python scripts/render_html.py examples/sample.yaml -o /tmp/s.html --pdf /tmp/s.pdf
```

派生版本由 `fork.py` 生成，文件头的三行注释即来源、目标与日期：

```bash
python scripts/fork.py examples/workspace/_master/resume.yaml examples/workspace/versions/new.yaml --target "目标岗位"
```

换成自己的素材时，`contact`、`assets/photo.jpg`、`logo` 会随 PDF 一起对外分发，投递前确认一遍。
