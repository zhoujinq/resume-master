import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from v3_helpers import mutated, valid_data

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("resume_evidence", ROOT / "scripts" / "evidence.py")
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


class V3EvidenceTest(unittest.TestCase):
    def assertBlocked(self, data, phrase):
        errors = evidence.validate_resume(data)
        self.assertTrue(errors, "invalid evidence unexpectedly passed")
        self.assertIn(phrase, "\n".join(errors))

    def test_valid_ledger_and_jd_mapping_pass(self):
        self.assertEqual([], evidence.validate_resume(valid_data()))

    def test_every_bullet_requires_traceable_facts(self):
        data = mutated(lambda d: d["sections"][0]["items"][0]["bullets"][0].update(facts=[]))
        self.assertBlocked(data, "facts")

    def test_provisional_fact_blocks_final_render(self):
        data = mutated(lambda d: d["facts"][0].update(status="provisional"))
        self.assertBlocked(data, "provisional")

    def test_missing_source_or_unknown_status_blocks(self):
        data = mutated(lambda d: d["facts"][0].update(source=""))
        self.assertBlocked(data, "source")
        data = mutated(lambda d: d["facts"][0].update(status="agent_verified"))
        self.assertBlocked(data, "status")

    def test_changed_number_without_source_blocks(self):
        def change(d):
            d["sections"][0]["items"][0]["bullets"][0]["text"] = "独立拓展 13 家虚构客户，确认回款 30 万元。"
        self.assertBlocked(mutated(change), "13")

    def test_assisted_team_work_cannot_become_independent_claim(self):
        data = mutated(lambda d: d["sections"][0]["items"][0]["bullets"][1].update(text="独立主导 2 次虚构复盘。", facts=["F002"]))
        self.assertBlocked(data, "ownership")

    def test_mixed_personal_and_assisted_bullet_uses_two_traceable_facts(self):
        data = valid_data()
        data["sections"][0]["items"][0]["bullets"][0].update(
            text="独立拓展 12 家虚构客户，确认回款 30 万元；协助团队完成 2 次虚构复盘。",
            facts=["F001", "F002"],
        )
        self.assertEqual([], evidence.validate_resume(data))

    def test_demo_fact_must_remain_labeled_as_demo(self):
        data = valid_data()
        data["facts"][0]["ownership"] = "demo"
        data["sections"][0]["items"][0]["bullets"][0]["text"] = "独立拓展 12 家客户，确认回款 30 万元。"
        self.assertBlocked(data, "demo")

    def test_unknown_fact_and_unmapped_jd_requirement_block(self):
        data = mutated(lambda d: d["sections"][0]["items"][0]["bullets"][0].update(facts=["F999"]))
        self.assertBlocked(data, "F999")
        data = mutated(lambda d: d["jd"]["requirements"][0].update(evidence=["F999"]))
        self.assertBlocked(data, "F999")
        data = mutated(lambda d: d["jd"]["requirements"][0].update(evidence=[], gap=False))
        self.assertBlocked(data, "gap")

    def test_fork_preserves_fact_status_ownership_and_source_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "master.yaml"
            target = Path(tmp) / "role.yaml"
            original = yaml.safe_dump(valid_data(), allow_unicode=True, sort_keys=False)
            source.write_text(original, encoding="utf-8")
            before = source.read_bytes()
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/fork.py"), str(source), str(target), "--target", "新岗位"],
                capture_output=True, text=True, encoding="utf-8", timeout=30,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(before, source.read_bytes())
            derived = yaml.safe_load(target.read_text(encoding="utf-8"))
            self.assertEqual(valid_data()["facts"], derived["facts"])
            self.assertEqual("confirmed", derived["facts"][0]["status"])
            second = subprocess.run(
                [sys.executable, str(ROOT / "scripts/fork.py"), str(source), str(target), "--target", "覆盖"],
                capture_output=True, text=True, encoding="utf-8", timeout=30,
            )
            self.assertNotEqual(0, second.returncode)
            self.assertEqual(derived, yaml.safe_load(target.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
