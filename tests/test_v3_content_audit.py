import importlib.util
import unittest
from pathlib import Path

from v3_helpers import clone, mutated, valid_data

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
    def test_structural_tells_explain_the_pattern_without_a_score(self):
        def weaken(data):
            data["sections"][0]["items"][0]["bullets"][0]["text"] = "不仅独立拓展 [[12 家]]虚构客户，更确认回款 **30 万元**，打造行业标杆。"
        checks = audit.audit_content(mutated(weaken))
        contrast = next(check for check in checks if check["code"] == "STAGED_CONTRAST")
        inflated = next(check for check in checks if check["code"] == "INFLATED_SIGNIFICANCE")
        self.assertEqual("WARN", contrast["status"])
        self.assertIn("直接", contrast["action"])
        self.assertEqual("WARN", inflated["status"])
        self.assertFalse(any("score" in check or "probability" in check for check in checks))

    def test_chat_residue_document_narration_and_guessing_are_blocked(self):
        expectations = {
            "独立拓展 12 家客户，确认回款 30 万元。希望这份简历对你有帮助。": "CHAT_RESIDUE",
            "本简历旨在展示本人独立拓展 12 家客户并确认回款 30 万元。": "DOCUMENT_NARRATION",
            "大概参与拓展 12 家客户，确认回款 30 万元。": "UNCONFIRMED_FACT",
        }
        for text, code in expectations.items():
            with self.subTest(code=code):
                def weaken(data):
                    data["sections"][0]["items"][0]["bullets"][0]["text"] = text
                checks = audit.audit_content(mutated(weaken))
                self.assertTrue(any(check["code"] == code and check["status"] == "FAIL" for check in checks))

    def test_abstract_triad_does_not_flag_three_real_items(self):
        def abstract(data):
            data["sections"][0]["items"][0]["bullets"][0]["text"] = "通过 12 家客户与 30 万元回款，提升专业性、逻辑性、执行力。"
        checks = audit.audit_content(mutated(abstract))
        self.assertTrue(any(check["code"] == "ABSTRACT_TRIAD" and check["status"] == "WARN" for check in checks))

        def concrete(data):
            data["sections"][0]["items"][0]["bullets"][0]["text"] = "整理北京、上海、深圳 3 个区域的 12 家客户反馈，确认回款 30 万元。"
        checks = audit.audit_content(mutated(concrete))
        self.assertFalse(any(check["code"] == "ABSTRACT_TRIAD" for check in checks))

    def test_dash_overuse_does_not_treat_date_ranges_as_ai_tells(self):
        self.assertFalse(any(check["code"] == "DASH_OVERUSE" for check in audit.audit_content(valid_data())))

        def weaken(data):
            data["sections"][0]["items"][0]["bullets"][0]["text"] = "独立拓展 12 家客户——覆盖虚构区域——确认回款 30 万元——保留口径记录。"
        checks = audit.audit_content(mutated(weaken))
        self.assertTrue(any(check["code"] == "DASH_OVERUSE" and check["status"] == "WARN" for check in checks))

    def test_stacked_qualifiers_are_only_advisory(self):
        def weaken(data):
            data["sections"][0]["items"][0]["bullets"][0]["text"] = "较为全面地独立拓展 12 家客户，基本上确认回款 30 万元，并一定程度上保留口径。"
        checks = audit.audit_content(mutated(weaken))
        self.assertTrue(any(check["code"] == "STACKED_QUALIFIERS" and check["status"] == "WARN" for check in checks))
        self.assertFalse(any(check["code"] == "STACKED_QUALIFIERS" and check["status"] == "FAIL" for check in checks))

    def test_baseline_allows_prose_only_but_keeps_semantic_review(self):
        before = valid_data()
        after = clone(before)
        after["sections"][0]["items"][0]["bullets"][0]["text"] = "独立拓展 [[12 家]]虚构客户，并确认回款 **30 万元**。"
        checks = audit.audit_content(after, baseline=before)
        self.assertFalse(any(check["status"] == "FAIL" for check in checks))
        self.assertTrue(any(check["code"] == "MECHANICAL_FACTS" and check["status"] == "PASS" for check in checks))
        self.assertTrue(any(check["code"] == "SEMANTIC_REVIEW" and check["status"] == "WARN" for check in checks))

    def test_same_numbers_do_not_prove_semantic_equivalence(self):
        before = valid_data()
        after = clone(before)
        after["sections"][0]["items"][0]["bullets"][0]["text"] = "协助拓展 [[12 家]]虚构客户，确认回款 **30 万元**。"
        checks = audit.audit_content(after, baseline=before)
        self.assertFalse(any(check["code"] == "NUMBER_CHANGED" for check in checks))
        self.assertTrue(any(check["code"] == "MECHANICAL_FACTS" and check["status"] == "PASS" for check in checks))
        semantic = next(check for check in checks if check["code"] == "SEMANTIC_REVIEW")
        self.assertEqual("WARN", semantic["status"])
        self.assertIn("人工", semantic["detail"])

    def test_baseline_number_addition_or_loss_is_blocked(self):
        for replacement in ("独立拓展 [[12 家]]虚构客户，确认相应回款。", "独立拓展 [[12 家]]虚构客户，确认回款 **30 万元**并新增 2 项记录。"):
            with self.subTest(replacement=replacement):
                before = valid_data()
                after = clone(before)
                after["sections"][0]["items"][0]["bullets"][0]["text"] = replacement
                checks = audit.audit_content(after, baseline=before)
                self.assertTrue(any(check["code"] == "NUMBER_CHANGED" and check["status"] == "FAIL" for check in checks))

    def test_baseline_non_prose_changes_are_blocked(self):
        before = valid_data()
        after = clone(before)
        after["facts"][0]["statement"] = "篡改后的事实。"
        checks = audit.audit_content(after, baseline=before)
        self.assertTrue(any(check["code"] == "NON_PROSE_CHANGED" and check["status"] == "FAIL" for check in checks))

        after = clone(before)
        after["sections"][1]["items"][0]["url"] = "https://example.com/changed"
        checks = audit.audit_content(after, baseline=before)
        self.assertTrue(any(check["code"] == "NON_PROSE_CHANGED" and check["status"] == "FAIL" for check in checks))

        before["meta"]["text"] = "非 bullet 的同名字段"
        after = clone(before)
        after["meta"]["text"] = "不得被当成正文豁免"
        checks = audit.audit_content(after, baseline=before)
        self.assertTrue(any(check["code"] == "NON_PROSE_CHANGED" and check["status"] == "FAIL" for check in checks))


if __name__ == "__main__":
    unittest.main()
