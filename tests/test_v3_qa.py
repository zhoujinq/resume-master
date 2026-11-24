import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

import fitz

from v3_helpers import valid_data

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("resume_qa_v3", ROOT / "scripts" / "qa.py")
qa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qa)
PUBLISH_SPEC = importlib.util.spec_from_file_location("resume_publish_qa_v3", ROOT / "scripts" / "publish_qa.py")
publisher = importlib.util.module_from_spec(PUBLISH_SPEC)
PUBLISH_SPEC.loader.exec_module(publisher)


class V3QATest(unittest.TestCase):
    def test_normalization_only_touches_typography_never_facts(self):
        self.assertEqual(qa.normalize_text("通信工程・本科"), qa.normalize_text("通信工程本科"))
        self.assertEqual(qa.normalize_text("部长・校企"), qa.normalize_text("部长·校企"))
        self.assertEqual(qa.normalize_text("A B\nC"), qa.normalize_text("ABC"))
        self.assertNotEqual(qa.normalize_text("12 家"), qa.normalize_text("13 家"))
        self.assertNotEqual(qa.normalize_text("30 万"), qa.normalize_text("3 万"))
        self.assertNotEqual(qa.normalize_text("收入 30"), qa.normalize_text("收入"))

    def test_content_atoms_exclude_evidence_ledger_but_include_all_visible_content(self):
        atoms = qa.content_atoms(valid_data())
        joined = "\n".join(atoms)
        self.assertIn("独立拓展", joined)
        self.assertIn("https://example.com/demo", joined)
        self.assertIn("example@example.com", joined)
        self.assertNotIn("mailto:example@example.com", joined)
        self.assertIn("先写用户意图", joined)
        self.assertNotIn("用户确认的虚构样例事实", joined)
        self.assertNotIn("客户拓展", joined)

    def test_font_size_blank_and_advisory_gates_have_honest_status(self):
        self.assertTrue(qa.font_allowed("SourceHanSerifSC-Bold"))
        self.assertTrue(qa.font_allowed("SourceHanSansSC-Regular"))
        self.assertFalse(qa.font_allowed("ArialMT"))
        self.assertFalse(qa.font_allowed("MicrosoftYaHei"))
        self.assertEqual("PASS", qa.font_size_status([8, 8.5, 9.5, 10, 10.5, 13, 34]))
        self.assertEqual("PASS", qa.font_size_status([8.04, 8.52, 9.48, 9.96, 10.56, 12.96, 33.96]))
        self.assertEqual("FAIL", qa.font_size_status([9.5, 9.2]))
        self.assertEqual("WARN", qa.blank_page_status([80, 42]))
        self.assertEqual("PASS", qa.blank_page_status([80, 75]))
        self.assertEqual("PASS", qa.file_size_status(2_000_000))
        self.assertEqual("WARN", qa.file_size_status(2_000_001))
        self.assertEqual("NOT_RUN", qa.image_quality_status({})["status"])
        self.assertEqual("NOT_APPLICABLE", qa.photo_advisory_status(False, {(80, 80)})["status"])
        self.assertEqual("NOT_RUN", qa.photo_advisory_status(True, set())["status"])
        self.assertEqual("WARN", qa.image_quality_status({(173, 242)})["status"])
        self.assertEqual("PASS", qa.image_quality_status({(600, 840)})["status"])

    def test_bullet_metrics_ignore_middle_dots_inside_role_text(self):
        document = fitz.open()
        page = document.new_page(width=200, height=150)
        page.insert_text((10, 20), "• first")
        page.insert_text((10, 37), "• second")
        page.insert_text((10, 60), "role · collaboration")
        _, starts = qa.bullet_line_metrics(document)
        self.assertEqual([17.0], starts)
        document.close()

    def test_bullet_metrics_track_wrapped_lines_across_pdf_blocks(self):
        document = fitz.open()
        page = document.new_page(width=260, height=150)
        page.insert_text((10, 20), "• first line")
        page.insert_text((24, 34), "continuation")
        page.insert_text((24, 48), "more continuation")
        page.insert_text((10, 70), "• next")
        wraps, _ = qa.bullet_line_metrics(document)
        self.assertEqual([14.0, 14.0], wraps)
        document.close()

    def test_raw_overflow_rejects_out_of_page_glyph(self):
        class FakePage:
            rect = fitz.Rect(0, 0, 100, 100)
            number = 0

            def get_text(self, _kind):
                return {"blocks": [{"type": 0, "lines": [{"spans": [{"chars": [{"c": "X", "bbox": [-1, 10, 5, 20]}]}]}]}]}

        issues = qa.raw_overflow(FakePage())
        self.assertEqual("X", issues[0]["char"])

    def test_public_qa_report_removes_local_paths_without_changing_status(self):
        report = {"overall": "WARN", "checks": [
            {"category": "core", "name": "证据", "status": "PASS", "detail": "通过"},
            {"category": "advisory", "name": "建议", "status": "WARN", "detail": "保留"},
            {"category": "core", "name": "导出", "status": "PASS", "detail": '{"input":"C:\\\\private\\\\resume.docx","exit_code":0}'},
        ]}
        text = publisher.render_public_report(report)
        self.assertIn("**WARN**", text)
        self.assertIn("resume.docx", text)
        self.assertNotIn("C:\\", text)
        self.assertNotIn("private", text)
        self.assertIn("核心与严格项无 FAIL", text)
        self.assertNotIn("真实 V53.1", text)
        self.assertNotIn("极简候选人", text)

    def test_pixel_comparison_detects_even_small_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = fitz.open()
            page = first.new_page(width=100, height=100)
            page.insert_text((10, 30), "same")
            second = fitz.open()
            page = second.new_page(width=100, height=100)
            page.insert_text((10, 30), "same")
            third = fitz.open()
            page = third.new_page(width=100, height=100)
            page.insert_text((10, 30), "diff")
            result = qa.compare_pdf_pixels(first, second, third, dpi=72)
            self.assertEqual("PASS", result["status"])
            self.assertEqual([0], result["difference_pixels"])
            for doc in (first, second, third):
                doc.close()

    def test_docx_text_ignores_drawing_coordinates_and_link_check_includes_mailto(self):
        xml = '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"><w:body><w:p><w:r><w:t>林示例</w:t></w:r><w:drawing><wp:anchor><wp:positionH><wp:posOffset>6160770</wp:posOffset></wp:positionH><wp:positionV><wp:posOffset>534670</wp:posOffset></wp:positionV></wp:anchor></w:drawing></w:p></w:body></w:document>'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "drawing.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", xml)
            self.assertEqual("林示例", qa.docx_text(path))
        expected = {"mailto:example@example.com", "https://example.com/work"}
        self.assertEqual("PASS", qa.link_check(expected, expected, "URL")["status"])
        self.assertEqual("NOT_APPLICABLE", qa.link_check(set(), set(), "URL")["status"])
        self.assertEqual("FAIL", qa.link_check(set(), {"https://example.com/unexpected"}, "URL")["status"])
        self.assertEqual("FAIL", qa.link_check(expected, set(), "URL")["status"])

    def test_strict_not_run_never_becomes_overall_pass(self):
        checks = [
            {"name": "core", "category": "core", "status": "PASS"},
            {"name": "strict", "category": "strict", "status": "NOT_RUN"},
            {"name": "advice", "category": "advisory", "status": "WARN"},
        ]
        text = qa.report_markdown("qa.json", checks)
        self.assertIn("**INCOMPLETE**", text)
        self.assertIn("NOT_RUN", text)
        self.assertNotIn("全部通过", text)


if __name__ == "__main__":
    unittest.main()
