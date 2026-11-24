# 证据台账与派生规则

## 每条 bullet 都是一项主张

终稿 YAML 由 `meta`、`facts`、可选 `jd` 和 `sections` 构成。每条 bullet 必须是对象：

```yaml
facts:
  - id: F001
    statement: 独立拓展 12 家示例客户，确认回款 30 万元。
    status: confirmed
    ownership: personal
    source: 用户确认的示例事实
    note: 能解释客户口径、回款口径和时间范围。
sections:
  - title: 工作经历
    items:
      - org: 示例公司
        role: 产品运营
        date: 2024.01–2025.01
        bullets:
          - text: 独立拓展 [[12 家]]示例客户，确认回款 **30 万元**。
            facts: [F001]
```

- `confirmed`：用户已确认事实与口径。
- `authorized`：用户授权在该事实上调整表达，不代表可以发明新事实。
- `provisional`：暂定或待确认，不能进入终稿。
- `personal`：个人独立或可明确归属的动作与结果。
- `team`：团队结果，必须保留团队口径。
- `assisted`：协助、参与，不能升级为独立或主导。
- `demo`：演示或示例结果，必须保留演示／示例标识。

每条 bullet 至少引用一个事实 ID。bullet 中的数字必须在所引用事实的 `statement` 中出现；这只能证明数字可追溯，不能自动证明其真实。最终仍需用户确认，并检查“能否在面试中解释”。

## JD 映射不是打分

```yaml
jd:
  requirements:
    - requirement: 客户拓展
      evidence: [F001]
    - requirement: 尚待补齐的外语成绩
      evidence: []
      gap: true
```

每项 JD 要求只能有证据或明确缺口，不能虚构匹配率、通过率或录用概率。缺口可以触发补充提问，也可以在不重要的要求上省略，但不能隐藏。

## 派生不降级、不串改

使用 `scripts/fork.py` 从事实基线派生岗位版本。派生必须完整保留事实 ID、确认状态、归属、来源和备注；改变目标岗位不等于重新降低事实确认状态。脚本默认拒绝覆盖，原始文件保持不变。

修改某个项目时，记录其输入与输出哈希；其他文件不应被重写。事实需要跨岗位更新时，先形成新的事实基线，再重新派生，不在多个版本间偷偷漂移。
