# 月结成本分摊库

将共享服务部门（中转中心）的本期成本按权重比例分摊到最终承担费用的业务部门
（最终承接中心）。中转中心之间允许互相分摊（含回流与自身），库内以精确有理数
联立线性方程一次算清全部回流关系，规则、初始成本与试算结果均保存在进程内存，
由上层代码直接调用，无接口层、无外部服务依赖。

## 环境

- Python 3.10+，仅使用标准库（`fractions`、`dataclasses`）。
- 运行测试需要 `pytest`。

## 快速开始

```python
from cost_allocation import allocate, AllocationRule, RuleSnapshot

snapshot = RuleSnapshot(transit_rules={
    # 中转中心 A：50% 分给中转中心 B，50% 分给最终承接中心 X
    "A": (AllocationRule("B", 5000), AllocationRule("X", 5000)),
    # 中转中心 B：50% 回流给 A，50% 分给最终承接中心 Y
    "B": (AllocationRule("A", 5000), AllocationRule("Y", 5000)),
})

result = allocate(snapshot, {"A": 100})   # 初始成本单位：分，非负整数
print(result.amounts)                     # {'X': 67, 'Y': 33}
```

## 规则说明

- `RuleSnapshot.transit_rules` 中出现的中转中心必须有非空去向列表，每条
  `AllocationRule` 的 `weight` 为正整数万分比，同一中心出向权重合计必须为
  10000；去向可以是任意中心（包括自身）。未出现在 `transit_rules` 中的中心
  视为最终承接中心，没有出向关系。
- 中心标识为非空 ASCII 字符串；初始成本为非负整数分，两类中心都可以有初始成本。
- 每个中转中心分出的总额 = 自身初始成本 + 其他中心分给它的金额，各去向按权重
  分配；所有关系同时成立（精确数学解），与中心和关系的排列顺序无关。
- 最终承接中心所得 = 自身初始成本 + 全部收到的金额。

## 封闭回流组

- 只要有正成本能够沿分摊关系进入一个没有任何路径通向最终承接中心的回流组，
  `allocate` 抛出 `AllocationError`，整次试算不产出结果。
- 完全没有正成本可达的封闭回流组不影响试算，不会仅因规则中存在环而失败。

## 取整规则

金额只在最终承接中心汇总完成后统一取整：先取各中心精确金额的整数部分，再把与
输入总成本之间的差额逐分补齐——按精确小数余量从大到小，每个中心最多补 1 分；
余量相同按中心标识的 ASCII 字典序优先。最终金额之和严格等于输入总成本。

## 运行测试

```bash
python3 -m pytest tests -q
```

## 文件结构

- `cost_allocation/models.py` — 类型定义（规则快照、结果、异常）
- `cost_allocation/solver.py` — Fraction 高斯消元精确求解
- `cost_allocation/allocator.py` — 校验、封闭回流组检测、方程组装、统一取整
- `tests/test_allocation.py` — 自动化测试
