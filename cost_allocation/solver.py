"""线性方程组精确求解（有理数）。"""

from __future__ import annotations

from fractions import Fraction

from .errors import AllocationError


def solve_linear(matrix: list[list[Fraction]], rhs: list[Fraction]) -> list[Fraction]:
    """用高斯消元精确求解 matrix * x = rhs。

    矩阵必须可逆，否则抛出 AllocationError。
    """
    n = len(matrix)
    aug = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]

    for col in range(n):
        pivot = next((r for r in range(col, n) if aug[r][col] != 0), None)
        if pivot is None:
            raise AllocationError("分摊方程组无唯一解")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        pivot_val = aug[col][col]
        for row in range(n):
            if row != col and aug[row][col] != 0:
                factor = aug[row][col] / pivot_val
                for k in range(col, n + 1):
                    aug[row][k] -= factor * aug[col][k]

    return [aug[i][n] / aug[i][i] for i in range(n)]
