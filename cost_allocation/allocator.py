"""分摊编排：输入校验、封闭回流组检测、方程组装、统一取整。"""

from __future__ import annotations

from fractions import Fraction
from typing import Dict, List, Set

from .models import AllocationError, AllocationResult, RuleSnapshot
from .solver import solve_linear

_WEIGHT_BASE = 10000


def _validate_snapshot(snapshot: RuleSnapshot) -> None:
    centers: Set[str] = set(snapshot.transit_rules)
    for source, rules in snapshot.transit_rules.items():
        _check_center_id(source)
        if not rules:
            raise AllocationError(f"中转中心 {source!r} 没有分摊去向")
        total = 0
        for rule in rules:
            _check_center_id(rule.target)
            if not isinstance(rule.weight, int) or isinstance(rule.weight, bool) or rule.weight <= 0:
                raise AllocationError(f"中心 {source!r} 的出向权重必须为正整数: {rule.weight!r}")
            total += rule.weight
            centers.add(rule.target)
        if total != _WEIGHT_BASE:
            raise AllocationError(f"中心 {source!r} 的出向权重合计须为 10000，实际为 {total}")
    for center in centers:
        if center in snapshot.transit_rules and not snapshot.transit_rules[center]:
            raise AllocationError(f"中转中心 {center!r} 没有分摊去向")


def _check_center_id(center: str) -> None:
    if not isinstance(center, str) or not center or not center.isascii():
        raise AllocationError(f"中心标识必须为非空 ASCII 字符串: {center!r}")


def _validate_costs(initial_costs: Dict[str, int], known: Set[str]) -> None:
    for center, amount in initial_costs.items():
        _check_center_id(center)
        if center not in known:
            raise AllocationError(f"初始成本指向未知中心: {center!r}")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
            raise AllocationError(f"中心 {center!r} 的初始成本必须为非负整数分: {amount!r}")


def _transit_reachable_from(initial_costs: Dict[str, int], snapshot: RuleSnapshot) -> Set[str]:
    """从所有正成本中心出发，沿分摊关系可达的中转中心集合。"""
    adjacency = {s: [r.target for r in rules] for s, rules in snapshot.transit_rules.items()}
    seen: Set[str] = set()
    stack: List[str] = [c for c, amt in initial_costs.items() if amt > 0]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency.get(node, ()))
    return seen


def _check_closed_loops(snapshot: RuleSnapshot, initial_costs: Dict[str, int]) -> None:
    """正成本可达的中转中心必须存在通向最终承接中心的路径。"""
    # 反向可达：能到达任一最终承接中心的中心集合。
    reverse: Dict[str, List[str]] = {}
    for source, rules in snapshot.transit_rules.items():
        for rule in rules:
            reverse.setdefault(rule.target, []).append(source)
    finals = reverse.keys() - snapshot.transit_rules.keys()
    good: Set[str] = set(finals)
    stack = list(finals)
    while stack:
        node = stack.pop()
        for prev in reverse.get(node, ()):
            if prev not in good:
                good.add(prev)
                stack.append(prev)

    reachable = _transit_reachable_from(initial_costs, snapshot)
    trapped = (reachable & snapshot.transit_rules.keys()) - good
    if trapped:
        raise AllocationError(
            "正成本进入没有路径通向最终承接中心的封闭回流组: " + ", ".join(sorted(trapped))
        )


def _round_to_cents(exact: Dict[str, Fraction], total: int) -> Dict[str, int]:
    """统一取整：先取整数部分，再按小数余量降序（同余量按标识字典序）逐分补齐。"""
    floors = {c: v.numerator // v.denominator for c, v in exact.items()}
    gap = total - sum(floors.values())
    order = sorted(
        exact,
        key=lambda c: (-(exact[c] - floors[c]), c),
    )
    result = dict(floors)
    for center in order[:gap]:
        result[center] += 1
    return result


def allocate(snapshot: RuleSnapshot, initial_costs: Dict[str, int]) -> AllocationResult:
    """执行一次月结成本分摊试算，返回各最终承接中心的整数分金额。"""
    _validate_snapshot(snapshot)
    known: Set[str] = set(snapshot.transit_rules)
    for rules in snapshot.transit_rules.values():
        known.update(r.target for r in rules)
    _validate_costs(initial_costs, known)
    _check_closed_loops(snapshot, initial_costs)

    # 仅对正成本可达的中转中心建方程；不可达的中转中心精确金额为零，
    # 从而无成本可达的封闭回流组不会造成奇异方程组。
    active = _transit_reachable_from(initial_costs, snapshot) & snapshot.transit_rules.keys()
    transit = sorted(active)
    index = {c: i for i, c in enumerate(transit)}
    n = len(transit)

    # x_i = initial_i + sum_j x_j * w(j->i) / 10000
    matrix = [[Fraction(int(i == j)) for j in range(n)] for i in range(n)]
    rhs = [Fraction(initial_costs.get(c, 0)) for c in transit]
    for source, rules in snapshot.transit_rules.items():
        for rule in rules:
            if rule.target in index:
                matrix[index[rule.target]][index[source]] -= Fraction(rule.weight, _WEIGHT_BASE)
    solved = solve_linear(matrix, rhs) if n else []
    exact_transit = {c: Fraction(0) for c in snapshot.transit_rules}
    exact_transit.update(zip(transit, solved))

    exact_final: Dict[str, Fraction] = {}
    for center in known - snapshot.transit_rules.keys():
        exact_final[center] = Fraction(initial_costs.get(center, 0))
    for source, rules in snapshot.transit_rules.items():
        for rule in rules:
            if rule.target in exact_final:
                exact_final[rule.target] += exact_transit[source] * rule.weight / _WEIGHT_BASE

    total = sum(initial_costs.values())
    amounts = _round_to_cents(exact_final, total)
    if sum(amounts.values()) != total:
        raise AllocationError("取整后金额之和不等于输入总成本")
    return AllocationResult(amounts=amounts)
