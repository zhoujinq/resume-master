# 公开虚构样例

`sample.yaml` 与 `target-jd.md` 中的人名、公司、学校、数字、链接和项目均为虚构，仅用于验证证据映射、DOCX 与 Word PDF 生产链。图片也只为测试生成，不代表真实人物或企业。

从仓库根目录运行：

```powershell
python scripts/evidence.py examples/sample.yaml
python scripts/render_docx.py examples/sample.yaml -o sample.docx --pdf sample.pdf --repeat-pdf sample-repeat.pdf
python scripts/preview.py sample.pdf
```

随后在临时副本上执行真实 Word 编辑—撤销，并把导出日志、撤销证据和逐页预览传给 `scripts/qa.py`。完整命令见根目录 `README.md`。

公开仓库不得替换为真实私人简历、联系方式、公司指标或本机路径。
