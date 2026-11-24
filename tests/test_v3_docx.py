import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from docx import Document
from lxml import etree
from PIL import Image

from v3_helpers import minimal_data, valid_data

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("resume_docx_v3", ROOT / "scripts" / "render_docx.py")
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main", "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"}


class V3DocxTest(unittest.TestCase):
    def build(self, tmp, mutate=None):
        photo = Path(tmp) / "photo.png"
        logo = Path(tmp) / "logo.png"
        Image.new("RGB", (600, 840), "#D8D8D8").save(photo)
        Image.new("RGB", (160, 160), "#2F5BEA").save(logo)
        data = valid_data()
        data["meta"]["photo"] = str(photo)
        data["sections"][0]["items"][0]["logo"] = str(logo)
        data["sections"][0]["items"][0]["logo_width"] = 12.8
        if mutate:
            mutate(data)
        out = Path(tmp) / "resume.docx"
        renderer.build_docx(data, out)
        return out

    def test_fixed_fonts_sizes_colors_and_no_footer(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.build(tmp)
            with zipfile.ZipFile(out) as zf:
                root = etree.fromstring(zf.read("word/document.xml"))
                settings = zf.read("word/settings.xml").decode("utf-8")
                names = zf.namelist()
            self.assertNotIn("word/footer1.xml", names)
            self.assertIn("doNotAutoCompressPictures", settings)
            allowed_fonts = {"思源宋体", "思源黑体"}
            allowed_sizes = {"16", "17", "19", "20", "21", "26", "68"}
            for run in root.xpath(".//w:r", namespaces=NS):
                text = "".join(run.xpath(".//w:t/text()", namespaces=NS))
                if not text:
                    continue
                fonts = run.xpath("./w:rPr/w:rFonts", namespaces=NS)
                self.assertTrue(fonts, text)
                for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
                    value = fonts[0].get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}" + attr)
                    self.assertIn(value, allowed_fonts, text)
                sizes = run.xpath("./w:rPr/w:sz/@w:val", namespaces=NS)
                self.assertTrue(sizes, text)
                self.assertIn(sizes[0], allowed_sizes, text)
                colors = run.xpath("./w:rPr/w:color/@w:val", namespaces=NS)
                if colors:
                    self.assertIn(colors[0].upper(), {"000000", "2F5BEA", "141519", "2B3038", "5A6069", "857F74"}, text)
            name = root.xpath(".//w:t[text()='林示例']/parent::w:r", namespaces=NS)[0]
            self.assertEqual(["68"], name.xpath("./w:rPr/w:sz/@w:val", namespaces=NS))
            self.assertEqual("思源宋体", name.xpath("./w:rPr/w:rFonts/@w:eastAsia", namespaces=NS)[0])

    def test_structure_photo_logo_links_and_page_section_match_v53(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.build(tmp)
            with zipfile.ZipFile(out) as zf:
                xml = zf.read("word/document.xml").decode("utf-8")
                root = etree.fromstring(zf.read("word/document.xml"))
                rels = zf.read("word/_rels/document.xml.rels").decode("utf-8")
            self.assertNotIn("txbxContent", xml)
            self.assertNotIn("<w:br", xml)
            self.assertIn("wp:anchor", xml)
            self.assertIn('cx="792480"', xml)
            self.assertIn('cy="1108710"', xml)
            self.assertGreaterEqual(len(root.xpath(".//w:sectPr", namespaces=NS)), 2)
            self.assertIn("https://example.com/demo", rels)
            self.assertIn("https://example.com/work", rels)
            self.assertIn("mailto:example@example.com", rels)
            url_nodes = root.xpath(".//w:hyperlink[.//w:t[contains(text(), 'example.com/demo')]]", namespaces=NS)
            self.assertTrue(url_nodes)
            self.assertEqual(["000000"], url_nodes[0].xpath(".//w:color/@w:val", namespaces=NS))
            self.assertEqual(["single"], url_nodes[0].xpath(".//w:u/@w:val", namespaces=NS))
            texts = [p.text for p in Document(out).paragraphs]
            self.assertLess(texts.index("先写用户意图，再写可核验证据。"), next(i for i, text in enumerate(texts) if "示例文档工具" in text))
            self.assertTrue(any("https://example.com/demo" in text and "2025.02–2025.03" in text for text in texts))

    def test_style_override_and_unknown_route_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for key, value in (("preset", "other"), ("font_east_asia", "Arial"), ("accent", "#000000"), ("body_size", 8)):
                def change(data, key=key, value=value):
                    data["style"] = {key: value}
                with self.subTest(key=key):
                    with self.assertRaises(ValueError):
                        self.build(tmp, change)

    def test_fixed_renderer_constants_are_not_parameters(self):
        self.assertEqual("思源宋体", renderer.SERIF)
        self.assertEqual("思源黑体", renderer.SANS)
        self.assertEqual("2F5BEA", renderer.ACCENT)
        self.assertEqual(9.5, renderer.BODY_PT)
        self.assertEqual(792480, renderer.PHOTO_CX)
        self.assertEqual(1108710, renderer.PHOTO_CY)
    def test_word_child_process_cannot_pick_incompatible_utility_module(self):
        env = renderer.word_powershell_env({
            "PSModulePath": r"C:\custom\pwsh\Modules",
            "SystemRoot": r"C:\Windows",
            "ProgramFiles": r"C:\Program Files",
        }, windows=True)
        self.assertNotIn("custom", env["PSModulePath"])
        self.assertIn(r"C:\Windows\System32\WindowsPowerShell\v1.0\Modules", env["PSModulePath"])
        for name in ("export_word.ps1", "verify_word_edit.ps1"):
            text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            self.assertIn("Microsoft.PowerShell.Utility.psd1", text)
    def test_no_photo_and_long_url_remain_valid_docx(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = valid_data()
            data["meta"].pop("photo", None)
            long_url = "https://github.com/example/" + "very-long-segment/" * 5
            data["meta"]["links"] = [{"label": "GitHub", "url": long_url}]
            out = Path(tmp) / "no-photo.docx"
            renderer.build_docx(data, out)
            with zipfile.ZipFile(out) as zf:
                xml = zf.read("word/document.xml").decode("utf-8")
                rels = zf.read("word/_rels/document.xml.rels").decode("utf-8")
            self.assertNotIn("<w:drawing>", xml)
            self.assertIn(long_url, rels)
            root = etree.fromstring(xml.encode("utf-8"))
            role_paragraph = root.xpath(".//w:body/w:p", namespaces=NS)[1]
            right = role_paragraph.find("w:pPr/w:ind", namespaces=NS).get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}right")
            self.assertEqual("0", right)

    def test_minimal_candidate_has_no_blank_link_line_or_project_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "minimal.docx"
            renderer.build_docx(minimal_data(), target)
            document = Document(target)
            texts = [paragraph.text.strip() for paragraph in document.paragraphs]
            self.assertTrue(texts)
            self.assertTrue(all(texts), f"unexpected blank body paragraph: {texts}")
            self.assertFalse(any("项目经历" in text for text in texts))
            self.assertFalse(any("GitHub" in text or "http" in text for text in texts))
            with zipfile.ZipFile(target) as archive:
                rels = archive.read("word/_rels/document.xml.rels").decode("utf-8")
                self.assertNotIn("https://", rels)
                self.assertNotIn("mailto:", rels)

    def test_missing_word_fails_instead_of_faking_pdf(self):
        with mock.patch.object(renderer.subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaises(SystemExit) as caught:
                renderer.export_pdf_with_word(Path("input.docx"), Path("output.pdf"))
            self.assertIn("Microsoft Word", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
