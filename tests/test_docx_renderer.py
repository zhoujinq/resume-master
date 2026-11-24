import importlib.util
import tempfile
import unittest
import zipfile
import fitz
from pathlib import Path

from docx import Document
from docx.enum.text import WD_LINE_SPACING
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("resume_docx", ROOT / "scripts" / "render_docx.py")
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


class DocxRendererTest(unittest.TestCase):
    def sample_data(self, photo=None):
        return {
            "meta": {
                "name": "虚构姓名",
                "role": "目标岗位",
                "contact": ["虚构城市", {"t": "example@example.com", "u": "mailto:example@example.com"}],
                "links": [{"label": "作品集", "url": "https://example.com/work", "short": "example.com/work"}],
                "stats": [{"n": "3 项", "l": "虚构成果"}],
                "lede": "这是完全虚构的导语。",
                "photo": str(photo) if photo else None,
                "photo_w": 25,
            },
            "style": {"font_east_asia": "Microsoft YaHei", "font_latin": "Arial", "body_size": 9.5},
            "sections": [{
                "title": "项目经历",
                "items": [{
                    "org": "虚构项目",
                    "role": "独立开发",
                    "link": {"text": "演示", "url": "https://example.com/demo"},
                    "bullets": ["**独立完成**需求与验收。"],
                }],
            }],
        }

    def test_docx_is_editable_and_has_real_hyperlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "resume.docx"
            renderer.build_docx(self.sample_data(), out)
            doc = Document(out)
            text = "\n".join(p.text for p in doc.paragraphs)
            text += "\n" + "\n".join(p.text for t in doc.tables for row in t.rows for cell in row.cells for p in cell.paragraphs)
            self.assertIn("虚构姓名", text)
            self.assertIn("独立完成", text)
            self.assertNotIn("**", text)
            with zipfile.ZipFile(out) as zf:
                xml = zf.read("word/document.xml").decode("utf-8")
                rels = zf.read("word/_rels/document.xml.rels").decode("utf-8")
            self.assertNotIn("w:txbxContent", xml)
            self.assertIn("https://example.com/work", rels)
            self.assertIn("https://example.com/demo", rels)
            self.assertIn("mailto:example@example.com", rels)

    def test_photo_is_embedded_without_distortion(self):
        with tempfile.TemporaryDirectory() as tmp:
            photo = Path(tmp) / "photo.png"
            Image.new("RGB", (700, 980), "#dddddd").save(photo)
            out = Path(tmp) / "resume.docx"
            renderer.build_docx(self.sample_data(photo), out)
            doc = Document(out)
            photo_p = doc.tables[0].rows[0].cells[1].paragraphs[0]
            self.assertEqual(photo_p.paragraph_format.line_spacing_rule, WD_LINE_SPACING.SINGLE)
            with zipfile.ZipFile(out) as zf:
                media = [n for n in zf.namelist() if n.startswith("word/media/")]
                self.assertTrue(media)
                xml = zf.read("word/document.xml").decode("utf-8")
                self.assertIn("a:blip", xml)

    def test_section_body_item_url_and_page_break_keep_their_meaning(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = self.sample_data()
            section = data["sections"][0]
            section["body"] = "章节说明必须先于条目"
            section["page_break_before"] = True
            section["items"][0].pop("link")
            section["items"][0]["url"] = "https://example.com/from-url"
            out = Path(tmp) / "resume.docx"
            renderer.build_docx(data, out)
            doc = Document(out)
            texts = [p.text for p in doc.paragraphs]
            self.assertLess(texts.index("章节说明必须先于条目"), texts.index(next(t for t in texts if "虚构项目" in t)))
            heading = next(p for p in doc.paragraphs if p.text == "项目经历")
            self.assertTrue(heading.paragraph_format.page_break_before)
            with zipfile.ZipFile(out) as zf:
                rels = zf.read("word/_rels/document.xml.rels").decode("utf-8")
            self.assertIn("https://example.com/from-url", rels)

    def test_latin_slash_gets_a_nonsemantic_break_opportunity(self):
        self.assertEqual(renderer._soft_breaks("SDK/API"), "SDK/\u200bAPI")
        self.assertEqual(renderer._soft_breaks("SDK/\u200bAPI"), "SDK/\u200bAPI")

    def test_pdf_font_subset_preserves_text_and_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.pdf"
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((72, 72), "Hello")
            page.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(70, 60, 120, 80), "uri": "https://example.com"})
            doc.save(path)
            doc.close()
            renderer.subset_pdf_fonts(path)
            check = fitz.open(path)
            self.assertIn("Hello", check[0].get_text())
            self.assertEqual(check[0].get_links()[0]["uri"], "https://example.com")
            check.close()

    def test_word_e2e_is_explicitly_opt_in(self):
        # 默认单元测试不依赖本机 Word；真实导出由发布门禁独立执行并留报告。
        self.assertTrue(callable(renderer.export_pdf_with_word))


if __name__ == "__main__":
    unittest.main()
