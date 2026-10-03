"""月结成本分摊库的自动化测试。"""

import unittest

from cost_allocation import (
    AllocationRule as R,
    ClosedLoopError,
    Snapshot,
    ValidationError,
    allocate,
)


def base_snapshot(extra_rules=(), extra_costs=None):
    rules = [
        R("A", "B", 5000),
        R("A", "X", 5000),
        R("B", "A", 5000),
        R("B", "Y", 5000),
        *extra_rules,
    ]
    costs = {"A": 100}
    costs.update(extra_costs or {})
    return Snapshot(rules=tuple(rules), initial_costs=costs)


class CircularAllocationTest(unittest.TestCase):
    def test_two_way_circular_flow(self):
        # A=100，A↔B 各 50% 互分，A→X、B→Y 各 50%
        # 精确解：X = 100/1.5/2 = 200/3 ≈ 66.67，Y = 100/3 ≈ 33.33
        result = allocate(base_snapshot())
        self.assertEqual(result, {"X": 67, "Y": 33})
        self.assertEqual(sum(result.values()), 100)

    def test_unreachable_closed_loop_is_ignored(self):
        # C↔D 封闭回流组，无任何成本可达，不影响结果
        snap = base_snapshot(
            extra_rules=[R("C", "D", 5000), R("C", "C", 5000), R("D", "C", 10000)],
            extra_costs={"C": 0},
        )
        self.assertEqual(allocate(snap), {"X": 67, "Y": 33})

    def test_funded_closed_loop_fails(self):
        # 向封闭回流组投入 1 分，整次试算必须失败
        snap = base_snapshot(
            extra_rules=[R("C", "D", 5000), R("C", "C", 5000), R("D", "C", 10000)],
            extra_costs={"C": 1},
        )
        with self.assertRaises(ClosedLoopError):
            allocate(snap)

    def test_cost_flowing_into_closed_loop_fails(self):
        # 成本经中转中心间接流入封闭回流组，同样失败
        snap = base_snapshot(
            extra_rules=[R("C", "D", 10000), R("D", "C", 10000)],
            extra_costs={"C": 0},
        )
        # 让 B 的一条去向指向 C（替换 B→Y）
        rules = [r for r in snap.rules if not (r.from_center == "B" and r.to_center == "Y")]
        rules.append(R("B", "C", 5000))
        snap = Snapshot(rules=tuple(rules), initial_costs=snap.initial_costs)
        with self.assertRaises(ClosedLoopError):
            allocate(snap)


class RoundingTest(unittest.TestCase):
    def test_sum_always_equals_total(self):
        # 三个最终中心均分 100 分：33.33... × 3，余量相同按 ASCII 序补分
        snap = Snapshot(
            rules=(R("A", "X", 3334), R("A", "Y", 3333), R("A", "Z", 3333)),
            initial_costs={"A": 100},
        )
        result = allocate(snap)
        self.assertEqual(sum(result.values()), 100)
        self.assertEqual(result, {"X": 34, "Y": 33, "Z": 33})

    def test_tie_break_by_ascii_order(self):
        snap = Snapshot(
            rules=(R("A", "B", 5000), R("A", "C", 5000)),
            initial_costs={"A": 1},
        )
        # 各 0.5 分，差 1 分补给字典序靠前的 B
        self.assertEqual(allocate(snap), {"B": 1, "C": 0})

    def test_final_center_keeps_own_initial_cost(self):
        snap = Snapshot(
            rules=(R("A", "X", 10000),),
            initial_costs={"A": 40, "X": 7},
        )
        self.assertEqual(allocate(snap), {"X": 47})

    def test_permutation_invariance(self):
        # 同一输入无论中心和关系如何排列，结果相同
        snap1 = base_snapshot()
        snap2 = Snapshot(
            rules=tuple(reversed(base_snapshot().rules)),
            initial_costs={"A": 100},
        )
        self.assertEqual(allocate(snap1), allocate(snap2))

    def test_self_loop(self):
        # A 自留 25%，其余 75% 给 X：A 总额 = 100 / 0.75 = 133.33，X = 100
        snap = Snapshot(
            rules=(R("A", "A", 2500), R("A", "X", 7500)),
            initial_costs={"A": 100},
        )
        self.assertEqual(allocate(snap), {"X": 100})


class ValidationTest(unittest.TestCase):
    def test_weight_total_must_be_10000(self):
        snap = Snapshot(rules=(R("A", "X", 9999),), initial_costs={"A": 1})
        with self.assertRaises(ValidationError):
            allocate(snap)

    def test_negative_cost_rejected(self):
        snap = Snapshot(rules=(), initial_costs={"X": -1})
        with self.assertRaises(ValidationError):
            allocate(snap)

    def test_non_positive_weight_rejected(self):
        snap = Snapshot(rules=(R("A", "X", 0),), initial_costs={"A": 1})
        with self.assertRaises(ValidationError):
            allocate(snap)

    def test_no_rules(self):
        self.assertEqual(allocate(Snapshot(rules=(), initial_costs={"X": 5})), {"X": 5})


if __name__ == "__main__":
    unittest.main()

class ZeroCostBranchTest(unittest.TestCase):
    def test_zero_cost_transfer_to_final_contributes_nothing(self):
        # 无成本的中转中心 C 指向最终中心 Z，C 流出为 0，不影响结果
        snap = Snapshot(
            rules=(
                R("A", "X", 10000),
                R("C", "Z", 10000),
            ),
            initial_costs={"A": 50, "C": 0},
        )
        self.assertEqual(allocate(snap), {"X": 50, "Z": 0})
