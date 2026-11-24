import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class V3SingleRouteContractTest(unittest.TestCase):
    def test_active_tree_has_no_legacy_theme_or_style_override(self):
        roots = [ROOT / "SKILL.md", ROOT / "README.md", ROOT / "docs/index.html"]
        for directory in ("scripts", "references", "examples", "lite"):
            roots.extend(p for p in (ROOT / directory).rglob("*") if p.suffix.lower() in {".py", ".md", ".yaml", ".yml", ".html", ".css", ".ps1"})
        forbidden = ("swiss", "editorial", "mono", "#b4472b", "#0f766e", "#1f9aaa", "4d6bfe", "render_html.py", "resume.css", "preset", "font_east_asia", "font_latin", "body_size", "photo_w", "footer_text")
        for path in roots:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8").lower()
            for token in forbidden:
                self.assertNotIn(token, text, f"{path.relative_to(ROOT)} still contains {token}")

    def test_only_docx_word_pdf_renderer_remains(self):
        self.assertTrue((ROOT / "scripts/render_docx.py").is_file())
        self.assertTrue((ROOT / "scripts/export_word.ps1").is_file())
        self.assertTrue((ROOT / "scripts/evidence.py").is_file())
        for relative in ("scripts/render.py", "scripts/render_html.py", "assets/resume.css"):
            self.assertFalse((ROOT / relative).exists(), relative)
        requirements = read("pyproject.toml").lower()
        self.assertNotIn("reportlab", requirements)

    def test_fixed_visual_contract_is_explicit_everywhere(self):
        for relative in ("SKILL.md", "README.md", "lite/文件版skill.md", "docs/index.html"):
            text = read(relative)
            self.assertIn("思源宋体", text, relative)
            self.assertIn("思源黑体", text, relative)
            self.assertIn("#2F5BEA", text, relative)
            self.assertIn("v3.2.0", text, relative)
        html = read("docs/index.html")
        self.assertNotIn("三种气质", html)
        self.assertNotIn("只有一个版本", html)
        self.assertNotIn("没有风格选择题", html)
        self.assertIn("个人主页、GitHub", html)
        self.assertIn("不是必配项", html)
        self.assertNotIn("三种版式", read("README.md"))

    def test_postmortem_turns_every_cluster_into_a_gate(self):
        text = read("docs/postmortem-2026-11-20-to-24.md")
        for index in range(1, 17):
            self.assertIn(f"P{index:02d}", text)
        for gate in ("D02", "E01", "E02", "E03", "A01", "A04", "Q01", "Q03", "Q04", "H01"):
            self.assertIn(gate, text)

    def test_v32_first_principles_cross_domain_and_opposition_are_versioned(self):
        design = read("docs/design-rationale-v3.2.0.md")
        for phrase in ("第一性原理", "跨领域", "最强反对者", "Humanizer", "48 张配图", "语义等价", "不是启动门槛", "AI 检测"):
            self.assertIn(phrase, design)
        matrix = read("docs/requirements-matrix-v3.2.0.md")
        for requirement in ("R12", "R23", "R24", "R27", "R30", "R33"):
            self.assertIn(requirement, matrix)
        for version in ("v3.0.0", "v3.1.0"):
            self.assertFalse((ROOT / f"docs/design-rationale-{version}.md").exists())
            self.assertFalse((ROOT / f"docs/requirements-matrix-{version}.md").exists())

    def test_writing_style_is_optional_audited_and_properly_licensed(self):
        style = read("references/writing-style.md")
        for phrase in ("KEEP", "CHANGE", "ADD", "不是启动门槛", "人工盲评", "人味百分比", "bullet.text"):
            self.assertIn(phrase, style)
        license_text = read("licenses/humanizer-LICENSE")
        self.assertIn("Copyright (c) 2025 Siqi Chen", license_text)
        self.assertIn("MIT License", license_text)

    def test_website_links_and_sample_metrics_match_current_artifacts(self):
        html = read("docs/index.html")
        for target in re.findall(r'(?:href|src)="([^"]+)"', html):
            if target.startswith(("https://", "http://", "#", "mailto:")):
                continue
            self.assertTrue((ROOT / "docs" / target).is_file(), f"missing website artifact: {target}")
        size = (ROOT / "docs/assets/sample-v3.pdf").stat().st_size
        self.assertIn(f"<b>{size:,}</b>", html)
        self.assertIn(f"{size} bytes", read("docs/assets/qa-v3.md"))

    def test_no_private_resume_data_enters_public_tree(self):
        forbidden = ("周锦全", "星尘智能", "2336097716", "18307097085", "gavinzhou@", "D:\\私人资料", "C:\\Users\\gavinzhou")
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts or "tests" in path.parts:
                continue
            if path.suffix.lower() not in {".py", ".md", ".yaml", ".yml", ".html", ".css", ".ps1", ".toml"}:
                continue
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, f"private token in {path.relative_to(ROOT)}")


if __name__ == "__main__":
    unittest.main()
