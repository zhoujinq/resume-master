import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class SkillContractTest(unittest.TestCase):
    def test_frontmatter_has_only_portable_fields(self):
        text = read("SKILL.md")
        frontmatter = text.split("---", 2)[1]
        keys = [line.split(":", 1)[0] for line in frontmatter.splitlines()
                if line and not line.startswith((" ", "\t", "-")) and ":" in line]
        self.assertEqual(["name", "description"], keys)

    def test_two_modes_are_explicit(self):
        text = read("SKILL.md")
        self.assertIn("仅简历", text)
        self.assertIn("简历 + JD", text)
        self.assertIn("没有 JD", text)

    def test_common_resume_inputs_are_supported(self):
        text = read("references/intake.md")
        for suffix in (".pdf", ".docx", ".md", ".txt", ".yaml"):
            self.assertIn(suffix, text)
        self.assertIn("扫描件", text)
        self.assertIn("低置信度", text)

    def test_missing_jd_does_not_block_default_flow(self):
        text = read("references/intake.md")
        self.assertIn("没有 JD 也能直接优化", text)
        self.assertIn("不追问目标岗位", text)
        self.assertIn("合并成一轮", text)

    def test_facts_require_traceability_and_confirmation(self):
        text = read("references/guardrails.md")
        self.assertIn("C 级", text)
        self.assertIn("集中确认", text)
        self.assertIn("用户能复述", text)
        self.assertIn("归属词", text)

    def test_emphasis_requires_a_proposal_and_negative_list(self):
        text = read("references/emphasis.md")
        for phrase in ("正常正文", "蓝色加粗", "先给清单", "不标蓝清单", "默认少标"):
            self.assertIn(phrase, text)

    def test_mechanical_writing_rules_are_removed(self):
        all_text = read("SKILL.md") + read("references/content-rules.md") + read("references/design-system.md")
        self.assertNotIn("禁忌词（出现即改）", all_text)
        self.assertNotIn("颜色一页最多 3 次", all_text)
        self.assertIn("用户确认的具体表述", all_text)

    def test_delivery_uses_single_source_and_real_rendering(self):
        text = read("references/delivery.md")
        for phrase in ("单一内容源", "真实渲染", "假失败", "不能为排版悄悄删字", "可编辑"):
            self.assertIn(phrase, text)

    def test_skill_links_resolve(self):
        text = read("SKILL.md")
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
            if "://" not in target and not target.startswith("#"):
                self.assertTrue((ROOT / target).exists(), target)

    def test_two_mode_examples_exist(self):
        self.assertTrue((ROOT / "examples/friend-resume.md").is_file())
        self.assertTrue((ROOT / "examples/target-jd.md").is_file())

    def test_no_original_users_private_resume_data(self):
        private_terms = (
            "周锦全", "星尘智能", "联洲国际", "新加坡电信", "Astribot", "TP-Link", "Singtel",
            "毫米波国家", "1500 万欧元", "350 万元", "350 万元、15 家客户", "36 家客户",
            "飞书 Token", "模型斩杀线", "Personal AI", "N1 备考教练",
        )
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts or path.suffix.lower() in {".pdf", ".webp", ".png", ".jpg"}:
                continue
            if path.resolve() == Path(__file__).resolve():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for term in private_terms:
                self.assertNotIn(term, text, f"{term} leaked in {path.relative_to(ROOT)}")

    def test_readme_is_friend_ready_and_versioned(self):
        text = read("README.md")
        self.assertIn("v2.0.0", text)
        self.assertIn("仅简历", text)
        self.assertIn("简历 + JD", text)
        self.assertIn("无简历", text)
        self.assertIn("结构线框", text)
        self.assertIn("朋友", text)


if __name__ == "__main__":
    unittest.main()
