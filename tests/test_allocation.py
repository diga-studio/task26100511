"""分摊库自动化测试。"""

import pytest

from cost_allocation import (
    AllocationError,
    AllocationRule,
    RuleSnapshot,
    allocate,
)


def _basic_snapshot():
    return RuleSnapshot(transit_rules={
        "A": (AllocationRule("B", 5000), AllocationRule("X", 5000)),
        "B": (AllocationRule("A", 5000), AllocationRule("Y", 5000)),
    })


def test_mutual_allocation_settles_simultaneously():
    """A 有 100 分，A/B 互相回流，X 得 67、Y 得 33。"""
    result = allocate(_basic_snapshot(), {"A": 100})
    assert result.amounts == {"X": 67, "Y": 33}


def test_input_order_does_not_change_result():
    """中心与关系的排列顺序不影响结果。"""
    snap = RuleSnapshot(transit_rules={
        "B": (AllocationRule("Y", 5000), AllocationRule("A", 5000)),
        "A": (AllocationRule("X", 5000), AllocationRule("B", 5000)),
    })
    assert allocate(snap, {"A": 100}).amounts == {"X": 67, "Y": 33}


def test_unreachable_closed_loop_is_ignored():
    """无成本可达的封闭回流组不改变结果。"""
    snap = RuleSnapshot(transit_rules={
        "A": (AllocationRule("B", 5000), AllocationRule("X", 5000)),
        "B": (AllocationRule("A", 5000), AllocationRule("Y", 5000)),
        "P": (AllocationRule("Q", 10000),),
        "Q": (AllocationRule("P", 10000),),
    })
    assert allocate(snap, {"A": 100}).amounts == {"X": 67, "Y": 33}


def test_funded_closed_loop_fails_entire_run():
    """向封闭回流组投入 1 分后整次试算失败。"""
    snap = RuleSnapshot(transit_rules={
        "A": (AllocationRule("B", 5000), AllocationRule("X", 5000)),
        "B": (AllocationRule("A", 5000), AllocationRule("Y", 5000)),
        "P": (AllocationRule("Q", 10000),),
        "Q": (AllocationRule("P", 10000),),
    })
    with pytest.raises(AllocationError):
        allocate(snap, {"A": 100, "P": 1})


def test_cost_flowing_into_closed_loop_fails():
    """成本沿分摊关系间接进入封闭回流组同样失败。"""
    snap = RuleSnapshot(transit_rules={
        "A": (AllocationRule("X", 5000), AllocationRule("P", 5000)),
        "P": (AllocationRule("Q", 10000),),
        "Q": (AllocationRule("P", 10000),),
    })
    with pytest.raises(AllocationError):
        allocate(snap, {"A": 100})


def test_rounding_tie_broken_by_ascii_order():
    """余量相同按中心标识 ASCII 字典序优先补分。"""
    snap = RuleSnapshot(transit_rules={
        "A": (AllocationRule("b", 5000), AllocationRule("a", 5000)),
    })
    # 1 分对半分：两边余量都是 0.5，"a" 字典序优先得补分。
    assert allocate(snap, {"A": 1}).amounts == {"a": 1, "b": 0}


def test_final_center_keeps_own_initial_cost():
    """最终承接中心的自身初始成本计入结果。"""
    result = allocate(_basic_snapshot(), {"A": 100, "X": 5})
    assert result.amounts == {"X": 72, "Y": 33}
    assert sum(result.amounts.values()) == 105


def test_transit_center_own_initial_cost():
    """中转中心自身初始成本参与分摊。"""
    result = allocate(_basic_snapshot(), {"A": 100, "B": 100})
    # A、B 各结算 200，X、Y 各得 100。
    assert result.amounts == {"X": 100, "Y": 100}


def test_self_loop_transit():
    """去向可以是自身。"""
    snap = RuleSnapshot(transit_rules={
        "A": (AllocationRule("A", 5000), AllocationRule("X", 5000)),
    })
    assert allocate(snap, {"A": 100}).amounts == {"X": 100}


def test_zero_total_cost():
    """全部零成本时结果为零。"""
    result = allocate(_basic_snapshot(), {"A": 0})
    assert result.amounts == {"X": 0, "Y": 0}


def test_invalid_weight_sum_rejected():
    snap = RuleSnapshot(transit_rules={
        "A": (AllocationRule("X", 5000),),
    })
    with pytest.raises(AllocationError):
        allocate(snap, {"A": 100})


def test_negative_cost_rejected():
    with pytest.raises(AllocationError):
        allocate(_basic_snapshot(), {"A": -1})


def test_unknown_cost_center_rejected():
    with pytest.raises(AllocationError):
        allocate(_basic_snapshot(), {"Z": 1})


def test_non_ascii_center_rejected():
    snap = RuleSnapshot(transit_rules={
        "甲": (AllocationRule("X", 10000),),
    })
    with pytest.raises(AllocationError):
        allocate(snap, {"甲": 1})
