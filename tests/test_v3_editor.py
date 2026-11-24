import copy
import base64
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_editor():
    path = ROOT / "scripts" / "editor.py"
    spec = importlib.util.spec_from_file_location("resume_editor", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EditorBuildTest(unittest.TestCase):
    def setUp(self):
        self.editor = load_editor()
        self.temp = tempfile.TemporaryDirectory()
        self.work = Path(self.temp.name)
        self.qa = self.work / "qa.json"
        self.qa.write_text(json.dumps({"checks": [
            {"name": "PDF 导出", "category": "core", "status": "PASS"},
            {"name": "重复导出逐页像素", "category": "strict", "status": "PASS"},
        ]}), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_build_from_frozen_pdf_embeds_offline_editor_and_hashes(self):
        output = self.work / "editor.html"
        state = self.editor.build_editor(ROOT / "examples/sample.yaml", ROOT / "docs/assets/sample-v3.pdf", self.qa, output)
        html = output.read_text(encoding="utf-8")
        self.assertTrue(output.stat().st_size > 50000)
        self.assertEqual(state["base"]["pdfSha256"], hashlib.sha256((ROOT / "docs/assets/sample-v3.pdf").read_bytes()).hexdigest())
        self.assertEqual(state["base"]["yamlSha256"], hashlib.sha256((ROOT / "examples/sample.yaml").read_bytes()).hexdigest())
        original_docx = (ROOT / "docs/assets/sample-v3.docx").read_bytes()
        self.assertEqual(base64.b64decode(state["base"]["docxBase64"]), original_docx)
        self.assertEqual(state["base"]["docxSha256"], hashlib.sha256(original_docx).hexdigest())
        self.assertEqual(sum(len(page) for page in state["pages"]), 33)
        self.assertTrue(state["pages"])
        self.assertIn("林示例", html)
        self.assertIn("window.ResumeEditor", html)
        self.assertIn("JSZip", html)
        self.assertNotIn("<script src=", html)
        self.assertNotIn("https://fastly.jsdelivr.net", html)

    def test_blocking_qa_and_wrong_pdf_are_rejected(self):
        self.qa.write_text(json.dumps({"checks": [{"name": "PDF 导出", "category": "core", "status": "FAIL"}]}), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "封板 QA"):
            self.editor.build_editor(ROOT / "examples/sample.yaml", ROOT / "docs/assets/sample-v3.pdf", self.qa, self.work / "bad.html")
        self.qa.write_text(json.dumps({"checks": [{"name": "重复导出逐页像素", "category": "strict", "status": "NOT_RUN"}]}), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "封板 QA"):
            self.editor.build_editor(ROOT / "examples/sample.yaml", ROOT / "docs/assets/sample-v3.pdf", self.qa, self.work / "bad2.html")
        self.qa.write_text(json.dumps({"checks": []}), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "PDF 内容覆盖"):
            self.editor.build_editor(ROOT / "examples/sample.yaml", ROOT / "docs/assets/qa-v3.md", self.qa, self.work / "bad3.html")

    def test_mismatched_frozen_docx_is_rejected(self):
        from docx import Document
        wrong = self.work / "wrong.docx"
        document = Document(ROOT / "docs/assets/sample-v3.docx")
        document.paragraphs[0].text = "错误版本"
        document.save(wrong)
        with self.assertRaisesRegex(RuntimeError, "DOCX 与 YAML"):
            self.editor.build_editor(ROOT / "examples/sample.yaml", ROOT / "docs/assets/sample-v3.pdf", self.qa, self.work / "bad-docx.html", wrong)

    def test_optional_photo_links_and_projects_do_not_create_empty_blocks(self):
        data = yaml.safe_load((ROOT / "examples/sample.yaml").read_text(encoding="utf-8"))
        data = copy.deepcopy(data)
        data["meta"].pop("photo", None)
        data["meta"]["links"] = []
        data["sections"] = [section for section in data["sections"] if "作品" not in section.get("title", "") and "项目" not in section.get("title", "")]
        state = self.editor.state_from_data(data, ROOT / "examples", ROOT / "docs/assets/sample-v3.pdf")
        self.assertIsNone(state["photo"])
        serialized = json.dumps(state, ensure_ascii=False)
        self.assertNotIn("sample-photo", serialized)
        self.assertNotIn("icon-github", serialized)
        self.assertNotIn("Vibe Coding", serialized)
        for page in state["pages"]:
            for block in page:
                self.assertTrue(block.get("html") or block.get("fields"), block)

    def test_single_file_template_has_all_editing_controls(self):
        template = (ROOT / "assets/editor-template.html").read_text(encoding="utf-8")
        for token in ("id=\"editor\"", "id=\"bold\"", "id=\"textColor\"", "id=\"fontSize\"", "id=\"lineHeight\"", "id=\"paragraphSpace\"", "id=\"exportDocx\"", "id=\"exportPdf\"", "id=\"backup\"", "id=\"restore\"", "step=\"0.1\"", "Ctrl+B"):
            self.assertIn(token, template)
        self.assertNotIn("<script src=", template)
        self.assertNotIn("fonts.googleapis", template)

    def test_node_runtime_and_ooxml_regressions(self):
        result = subprocess.run(["node", "--test", "tests/editor_runtime.test.cjs"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)


if __name__ == "__main__":
    unittest.main()
