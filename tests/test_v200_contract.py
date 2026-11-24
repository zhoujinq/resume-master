import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class V200ContractTest(unittest.TestCase):
    def test_requirement_matrix_covers_evidence_rendering(self):
        text = read("docs/requirements-matrix-v2.0.0.md")
        for phrase in ("DOCX/PDF 文本一致性", "像素差为 0", "NOT_RUN", "先红后绿", "不安装、卸载或转换用户字体"):
            self.assertIn(phrase, text)

    def test_docx_is_a_real_route_not_an_html_screenshot(self):
        self.assertTrue((ROOT / "scripts/render_docx.py").is_file())
        self.assertTrue((ROOT / "scripts/export_word.ps1").is_file())
        skill = read("SKILL.md")
        self.assertIn("render_docx.py", skill)
        self.assertIn("Microsoft Word", skill)
        self.assertNotIn("Chrome 打印保证 1:1 还原", read("scripts/render_html.py"))

    def test_qa_report_has_explicit_statuses_and_evidence(self):
        skill = read("SKILL.md") + read("references/delivery.md")
        for phrase in ("PASS", "WARN", "FAIL", "NOT_RUN", "NOT_APPLICABLE", "字体白名单", "像素差", "视觉复核"):
            self.assertIn(phrase, skill)
        self.assertIn("--report-json", skill)
        self.assertIn("--repeat-pdf", skill)

    def test_lite_does_not_claim_unperformed_checks(self):
        text = read("lite/文件版skill.md")
        self.assertIn("核心", text)
        self.assertIn("严格", text)
        self.assertIn("未做", text)
        self.assertIn("不能仅凭测试数量宣称全部通过", text)

    def test_readme_and_project_page_are_v2(self):
        readme = read("README.md")
        page = read("docs/index.html")
        self.assertIn("v2.0.0", readme)
        self.assertIn("DOCX", readme)
        self.assertIn("requirements-matrix-v2.0.0.md", readme)
        self.assertIn("v2.0.0", page)
        self.assertIn("同源", page)

    def test_v120_readme_assertion_is_updated(self):
        text = read("tests/test_skill_contract.py")
        self.assertIn("v2.0.0", text)
        self.assertNotIn('self.assertIn("v1.2.0", text)', text)


if __name__ == "__main__":
    unittest.main()
