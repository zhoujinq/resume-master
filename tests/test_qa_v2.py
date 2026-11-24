import importlib.util
import tempfile
import unittest
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("resume_qa_v2", ROOT / "scripts" / "qa.py")
qa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qa)


class FakeDoc:
    def __init__(self, text):
        self.text = text

    def __iter__(self):
        return iter([self])

    def get_text(self):
        return self.text


class QaV2Test(unittest.TestCase):
    def setUp(self):
        qa.results.clear()
        qa.checks.clear()

    def test_normalization_removes_layout_noise_not_meaning(self):
        self.assertEqual(qa.normalize_text(" A–B\u00ad\n2 万元 "), "A-B2万元")
        self.assertEqual(qa.normalize_text("A・B"), qa.normalize_text("A·B"))
        self.assertEqual(qa.normalize_text("•项目"), qa.normalize_text("·项目"))
        self.assertNotEqual(qa.normalize_text("2 万元"), qa.normalize_text("3 万元"))

    def test_placeholder_blocks_delivery(self):
        qa.check_text(FakeDoc("教育经历【待补】"))
        self.assertTrue(any(level == "❌" and item == "待补占位" for level, item, _ in qa.results))

    def test_item_url_is_included_in_expected_links(self):
        data = {"sections": [{"items": [
            {"org": "A", "url": "https://example.com/a"},
            {"org": "B", "link": "https://example.com/b"},
        ]}]}
        self.assertEqual(qa.expected_links(data), ["https://example.com/a", "https://example.com/b"])
        atoms = qa.expected_text_atoms(data)
        self.assertIn("https://example.com/a", atoms)
        self.assertIn("https://example.com/b", atoms)

    def test_pdf_size_is_an_advisory_not_a_core_failure(self):
        self.assertEqual(qa.file_size_status(1024)[0], "PASS")
        self.assertEqual(qa.file_size_status(11 * 1024 * 1024)[0], "WARN")

    def test_core_and_strict_results_are_not_collapsed(self):
        qa.record("文本一致性", "PASS", "core", "一致")
        qa.record("字体白名单", "FAIL", "strict", "出现其他字体")
        summary = qa.build_summary()
        self.assertEqual(summary["core"], "PASS")
        self.assertEqual(summary["strict"], "FAIL")
        self.assertEqual(summary["overall"], "FAIL")

    def test_not_run_is_not_a_pass(self):
        qa.record("视觉复核", "NOT_RUN", "core", "未提供证据")
        summary = qa.build_summary()
        self.assertEqual(summary["overall"], "INCOMPLETE")
        self.assertNotEqual(summary["overall"], "PASS")

    def test_font_allowlist_is_a_separate_strict_check(self):
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "hello", fontname="helv")
        qa.check_fonts(doc, allowed=["SourceHanSans"])
        self.assertTrue(any(c["item"] == "PDF文本层" and c["status"] == "PASS" for c in qa.checks))
        self.assertTrue(any(c["item"] == "字体白名单" and c["status"] == "FAIL" and c["kind"] == "strict" for c in qa.checks))
        doc.close()

    def test_trailing_space_is_not_visible_overflow_but_letters_are(self):
        raw = {"size": 9.5, "chars": [
            {"c": "I", "bbox": [544.52, 0, 547.16, 10]},
            {"c": " ", "bbox": [547.16, 0, 549.79, 10]},
        ]}
        self.assertEqual(qa._visible_span(raw)["bbox"][2], 547.16)
        raw["chars"][0]["bbox"] = [544.52, 0, 549.16, 10]
        self.assertGreater(qa._visible_span(raw)["bbox"][2], qa.MARGIN_R + 1.5)

    def test_only_one_hanging_punctuation_is_tolerated(self):
        span = {"text": "天。", "bbox": [537.7, 0, 556.7, 10], "size": 9.5}
        self.assertTrue(qa._is_hanging_punctuation(span))
        self.assertFalse(qa._is_hanging_punctuation({**span, "text": "天A"}))
        self.assertFalse(qa._is_hanging_punctuation({**span, "bbox": [547.8, 0, 566.8, 10]}))

    def test_repeat_export_compares_every_pixel(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.pdf"
            b = Path(tmp) / "b.pdf"
            c = Path(tmp) / "c.pdf"
            for path, text in ((a, "same"), (b, "same"), (c, "different")):
                doc = fitz.open()
                page = doc.new_page(width=200, height=100)
                page.insert_text((20, 40), text)
                doc.save(path)
                doc.close()
            same = qa.compare_pdf_pixels(a, b, dpi=72)
            different = qa.compare_pdf_pixels(a, c, dpi=72)
            self.assertTrue(same["equal"])
            self.assertEqual(same["diff_pixels"], 0)
            self.assertFalse(different["equal"])
            self.assertGreater(different["diff_pixels"], 0)

    def test_expected_atoms_cover_content_but_not_markdown(self):
        data = {
            "meta": {"name": "虚构姓名", "links": [{"label": "作品", "url": "https://example.com", "short": "example.com"}]},
            "sections": [{"title": "项目", "items": [{"org": "虚构项目", "bullets": ["**独立**完成"]}]}],
        }
        atoms = qa.expected_text_atoms(data)
        self.assertIn("虚构姓名", atoms)
        self.assertIn("example.com", atoms)
        self.assertIn("独立完成", atoms)
        self.assertNotIn("**独立**完成", atoms)
        self.assertNotIn("https://example.com", atoms)


if __name__ == "__main__":
    unittest.main()
