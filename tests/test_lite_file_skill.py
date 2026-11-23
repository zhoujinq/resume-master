import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LITE = ROOT / "lite" / "文件版skill.md"


class LiteFileSkillTest(unittest.TestCase):
    def test_lite_file_exists_and_is_self_contained(self):
        self.assertTrue(LITE.is_file())
        text = LITE.read_text(encoding="utf-8")
        self.assertIn("完全自包含", text)
        self.assertIn("不读取任何外部引用", text)
        self.assertNotRegex(text, r"\[[^]]+\]\((?:references|scripts|assets)/")

    def test_lite_preserves_two_modes_and_input_rules(self):
        text = LITE.read_text(encoding="utf-8")
        for phrase in ("仅简历", "简历 + JD", "没有 JD", "PDF", "DOCX", "低置信度", "不追问目标岗位"):
            self.assertIn(phrase, text)

    def test_lite_preserves_fact_and_delivery_guardrails(self):
        text = LITE.read_text(encoding="utf-8")
        for phrase in ("用户能复述", "归属词", "集中确认", "不标蓝清单", "真实渲染", "不能为排版悄悄删字", "修改说明"):
            self.assertIn(phrase, text)

    def test_lite_does_not_fake_pro_renderer(self):
        text = LITE.read_text(encoding="utf-8")
        self.assertIn("不承诺 Pro 版的固定版式", text)
        self.assertIn("未做", text)

    def test_lite_has_copyable_prompt(self):
        text = LITE.read_text(encoding="utf-8")
        self.assertIn("请先完整阅读本文件", text)
        self.assertIn("朋友", text)


if __name__ == "__main__":
    unittest.main()
