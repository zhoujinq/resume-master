import importlib.util
import unittest
from pathlib import Path

from v3_helpers import mutated, valid_data

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("resume_content_audit", ROOT / "scripts" / "content_audit.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class V3ContentAuditTest(unittest.TestCase):
    def test_valid_content_has_no_fail_and_discloses_jd_gap(self):
        checks = audit.audit_content(valid_data())
        self.assertFalse(any(check["status"] == "FAIL" for check in checks))
        self.assertTrue(any(check["code"] == "JD_GAP" and check["status"] == "WARN" for check in checks))

    def test_duplicate_bullet_is_blocked(self):
        def duplicate(data):
            bullet = data["sections"][0]["items"][0]["bullets"][0]
            data["sections"][0]["items"][0]["bullets"].append(dict(bullet))
        checks = audit.audit_content(mutated(duplicate))
        self.assertTrue(any(check["code"] == "DUPLICATE" and check["status"] == "FAIL" for check in checks))

    def test_vague_words_long_lines_and_excessive_emphasis_are_visible(self):
        def weaken(data):
            data["sections"][0]["items"][0]["bullets"][0]["text"] = "热爱工作并通过赋能闭环抓手深耕致力于提升结果，" * 6
            data["sections"][0]["items"][0]["bullets"][0]["facts"] = ["F003"]
            data["sections"][0]["items"][0]["bullets"][1]["text"] = "**协助** **团队** **完成** [[2 次]] **虚构** **复盘** **整理**。"
        checks = audit.audit_content(mutated(weaken))
        codes = {check["code"] for check in checks if check["status"] == "WARN"}
        self.assertIn("VAGUE", codes)
        self.assertIn("LONG_BULLET", codes)
        self.assertIn("EMPHASIS", codes)


if __name__ == "__main__":
    unittest.main()
