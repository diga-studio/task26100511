"""类型定义：规则快照与试算结果。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class AllocationRule:
    """一条分摊去向：目标中心标识 + 正整数万分比权重。"""

    target: str
    weight: int


@dataclass(frozen=True)
class RuleSnapshot:
    """一次完整规则快照。

    transit_rules: 中转中心标识 -> 分摊去向列表（出向权重合计须为 10000）。
    不在 transit_rules 中的中心视为最终承接中心。
    """

    transit_rules: Dict[str, Tuple[AllocationRule, ...]]


@dataclass(frozen=True)
class AllocationResult:
    """试算结果：最终承接中心标识 -> 整数分金额。"""

    amounts: Dict[str, int]


class AllocationError(Exception):
    """规则非法或正成本进入无出路的封闭回流组时抛出。"""
