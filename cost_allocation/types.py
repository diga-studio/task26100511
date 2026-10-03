"""类型定义：规则快照与初始成本。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AllocationRule:
    """一条分摊去向：从 from_center 按 weight（万分比）分给 to_center。"""

    from_center: str
    to_center: str
    weight: int


@dataclass(frozen=True)
class Snapshot:
    """一次试算的完整输入：规则快照 + 各成本中心本期初始成本（非负整数分）。"""

    rules: tuple[AllocationRule, ...] = ()
    initial_costs: dict[str, int] = field(default_factory=dict)
