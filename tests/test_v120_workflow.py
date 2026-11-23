import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class V120WorkflowTest(unittest.TestCase):
    def test_all_entry_shapes_are_supported(self):
        text = read("SKILL.md") + read("references/intake.md")
        for phrase in ("已有简历", "无简历", "只有 JD", "个人主页", "GitHub", "作品集", "零散经历", "没有任何材料"):
            self.assertIn(phrase, text)

    def test_blank_user_gets_one_friendly_questionnaire(self):
        text = read("references/questionnaire.md")
        for phrase in ("一轮集中问卷", "知道多少写多少", "不知道", "没有", "少量缺失", "集中补问"):
            self.assertIn(phrase, text)
        for topic in ("求职方向", "教育", "工作", "项目", "技能", "联系方式"):
            self.assertIn(topic, text)

    def test_placeholder_draft_is_not_a_substitute_for_answers(self):
        text = read("SKILL.md") + read("references/intake.md") + read("references/guardrails.md")
        self.assertIn("不生成带", text)
        self.assertIn("【待补】", text)
        self.assertNotIn("可先交付标有", text)
        self.assertNotIn("可先给带", text)
        self.assertNotIn("写占位符 `【待补】`", text)

    def test_two_confirmations_have_separate_deliverables(self):
        text = read("SKILL.md") + read("references/operating-discipline.md")
        for phrase in ("确认 1", "结构线框", "确认 2", "全文文字稿", "终排"):
            self.assertIn(phrase, text)
        wireframe = read("references/wireframe.md")
        for phrase in ("章节顺序", "页面配比", "阅读顺序", "重点", "确认后再写全文"):
            self.assertIn(phrase, wireframe)

    def test_final_layout_rechecks_expanded_content(self):
        text = read("references/delivery.md") + read("references/design-system.md")
        for phrase in ("内容定稿后", "重新评估", "内容膨胀", "分页", "语义变化"):
            self.assertIn(phrase, text)

    def test_anonymized_case_library_covers_real_failure_modes(self):
        text = read("references/case-studies.md")
        for phrase in ("虚构", "统计周期", "个人贡献", "团队成果", "自用 MVP", "公开演示", "合成数据", "目标岗位", "时间"):
            self.assertIn(phrase, text)

    def test_lite_keeps_the_same_workflow(self):
        text = read("lite/文件版skill.md")
        for phrase in ("无简历", "只有 JD", "个人主页", "一轮集中问卷", "结构线框", "确认 1", "确认 2", "终排", "不生成带"):
            self.assertIn(phrase, text)

    def test_requirement_matrix_exists(self):
        text = read("docs/requirements-matrix-v1.2.0.md")
        self.assertIn("先红后绿", text)
        self.assertIn("R12", text)


if __name__ == "__main__":
    unittest.main()
