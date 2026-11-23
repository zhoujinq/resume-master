import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("resume_qa", ROOT / "scripts" / "qa.py")
qa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qa)


class FakeDoc:
    def __init__(self, text):
        self.text = text

    def __iter__(self):
        return iter([self])

    def get_text(self):
        return self.text


class QaAllowWordsTest(unittest.TestCase):
    def setUp(self):
        qa.results.clear()

    def test_repeated_empty_words_still_block(self):
        qa.check_text(FakeDoc("热爱团队，赋能业务。" * 6))
        self.assertTrue(any(level == "❌" and item == "禁忌词" for level, item, _ in qa.results))

    def test_user_confirmed_term_can_be_explicitly_allowed(self):
        qa.check_text(FakeDoc("使用 Agent 赋能销售。" * 6), allowed_words={"赋能"})
        self.assertFalse(any(level == "❌" and item == "禁忌词" for level, item, _ in qa.results))
        self.assertTrue(any("已豁免" in detail for _, _, detail in qa.results))


if __name__ == "__main__":
    unittest.main()
