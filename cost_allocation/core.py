"""试算编排：校验、求解、取整。"""

from __future__ import annotations

from collections import defaultdict
from fractions import Fraction

from .errors import ClosedLoopError, ValidationError
from .solver import solve_linear
from .types import Snapshot

_WEIGHT_TOTAL = 10000


def _validate(snapshot: Snapshot) -> None:
    for center, cost in snapshot.initial_costs.items():
        if not center.isascii() or not center:
            raise ValidationError(f"成本中心标识必须为非空 ASCII：{center!r}")
        if not isinstance(cost, int) or cost < 0:
            raise ValidationError(f"初始成本必须为非负整数分：{center}={cost!r}")
    outgoing: dict[str, int] = defaultdict(int)
    for rule in snapshot.rules:
        for center in (rule.from_center, rule.to_center):
            if not center.isascii() or not center:
                raise ValidationError(f"成本中心标识必须为非空 ASCII：{center!r}")
        if not isinstance(rule.weight, int) or rule.weight <= 0:
            raise ValidationError(f"权重必须为正整数万分比：{rule!r}")
        outgoing[rule.from_center] += rule.weight
    for center, total in outgoing.items():
        if total != _WEIGHT_TOTAL:
            raise ValidationError(
                f"中转中心 {center} 的出向权重合计必须为 10000，实际为 {total}"
            )


def _check_closed_loops(
    transfer_centers: set[str],
    edges: dict[str, list[str]],
    initial_costs: dict[str, int],
) -> None:
    """正成本若可达无任何路径通向最终承接中心的节点，则整次试算失败。"""
    # 反向图：从每个最终承接中心反向可达的节点集合 = 有路径通向最终中心的节点
    reverse: dict[str, list[str]] = defaultdict(list)
    for src, dsts in edges.items():
        for dst in dsts:
            reverse[dst].append(src)
    all_centers = set(initial_costs) | set(edges) | set(reverse)
    final_centers = all_centers - transfer_centers

    can_reach_final: set[str] = set(final_centers)
    stack = list(final_centers)
    while stack:
        node = stack.pop()
        for prev in reverse.get(node, ()):
            if prev not in can_reach_final:
                can_reach_final.add(prev)
                stack.append(prev)

    # 从正成本节点正向可达的节点
    reachable: set[str] = set()
    stack = [c for c in all_centers if initial_costs.get(c, 0) > 0]
    while stack:
        node = stack.pop()
        if node in reachable:
            continue
        reachable.add(node)
        stack.extend(edges.get(node, ()))

    trapped = reachable - can_reach_final
    if trapped:
        raise ClosedLoopError(
            "正成本进入没有路径通向最终承接中心的回流组："
            + ", ".join(sorted(trapped))
        )


def allocate(snapshot: Snapshot) -> dict[str, int]:
    """执行月结成本分摊试算，返回各最终承接中心的金额（整数分）。

    结果等同于比例关系的精确数学解，与输入排列顺序无关。
    """
    _validate(snapshot)

    edges: dict[str, list[str]] = defaultdict(list)
    weighted: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for rule in snapshot.rules:
        edges[rule.from_center].append(rule.to_center)
        weighted[rule.from_center].append((rule.to_center, rule.weight))

    transfer_centers = set(edges)
    all_centers = set(snapshot.initial_costs) | transfer_centers
    for dsts in edges.values():
        all_centers |= set(dsts)
    final_centers = sorted(all_centers - transfer_centers)

    _check_closed_loops(transfer_centers, edges, snapshot.initial_costs)

    # 对中转中心建立方程：x_i = initial_i + sum_j x_j * w(j->i) / 10000
    # 只需求解正成本可达的中转中心；不可达者精确流出恒为 0（且可能是奇异回流组）
    reachable: set[str] = set()
    stack = [c for c in all_centers if snapshot.initial_costs.get(c, 0) > 0]
    while stack:
        node = stack.pop()
        if node in reachable:
            continue
        reachable.add(node)
        stack.extend(edges.get(node, ()))
    unknowns = sorted(transfer_centers & reachable)
    index = {c: i for i, c in enumerate(unknowns)}
    n = len(unknowns)
    matrix = [[Fraction(int(i == j)) for j in range(n)] for i in range(n)]
    rhs = [Fraction(snapshot.initial_costs.get(c, 0)) for c in unknowns]
    for src, dsts in weighted.items():
        for dst, weight in dsts:
            if dst in index:
                matrix[index[dst]][index[src]] -= Fraction(weight, _WEIGHT_TOTAL)
    solved = dict(zip(unknowns, solve_linear(matrix, rhs))) if n else {}

    # 最终承接中心精确金额：自身初始成本 + 所有收到的金额
    exact: dict[str, Fraction] = {
        c: Fraction(snapshot.initial_costs.get(c, 0)) for c in final_centers
    }
    for src, dsts in weighted.items():
        for dst, weight in dsts:
            if dst in exact:
                exact[dst] += solved.get(src, Fraction(0)) * weight / _WEIGHT_TOTAL

    # 统一取整：先取整数部分，差额按小数余量从大到小逐分补齐（每中心最多 1 分），
    # 余量相同按中心标识 ASCII 字典序优先。
    total = sum(snapshot.initial_costs.values())
    floors = {c: v.numerator // v.denominator for c, v in exact.items()}
    gap = total - sum(floors.values())
    order = sorted(exact, key=lambda c: (-(exact[c] - floors[c]), c))
    result = dict(floors)
    for center in order[:gap]:
        result[center] += 1
    return result
