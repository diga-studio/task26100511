"""精确线性方程求解：Fraction 高斯消元，保证精确数学解。"""

from __future__ import annotations

from fractions import Fraction
from typing import List

from .models import AllocationError


def solve_linear(matrix: List[List[Fraction]], rhs: List[Fraction]) -> List[Fraction]:
    """求解 matrix * x = rhs，返回精确有理解。

    系数矩阵必须非奇异；奇异矩阵说明存在无法结算的回流关系，
    调用方应在校验阶段排除，这里抛出 AllocationError 兜底。
    """
    n = len(matrix)
    aug = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]

    for col in range(n):
        pivot = None
        for row in range(col, n):
            if aug[row][col] != 0:
                pivot = row
                break
        if pivot is None:
            raise AllocationError("分摊关系构成的方程组无唯一解")
        aug[col], aug[pivot] = aug[pivot], aug[col]

        pivot_val = aug[col][col]
        aug[col] = [v / pivot_val for v in aug[col]]
        for row in range(n):
            if row != col and aug[row][col] != 0:
                factor = aug[row][col]
                aug[row] = [v - factor * p for v, p in zip(aug[row], aug[col])]

    return [aug[i][n] for i in range(n)]
