# 月结成本分摊库（cost_allocation）

把共享服务部门（中转中心）的成本按万分比规则分摊到最终承接中心。
中转中心之间允许互相分摊（含自环），库内一次性求解全部回流关系的精确数学解，
并在最终承接中心汇总后统一取整到分。规则、初始成本和试算结果均保存在进程内存，
由上层直接调用，无接口层、无外部服务依赖。

## 快速开始

```python
from cost_allocation import allocate, AllocationRule, Snapshot

snapshot = Snapshot(
    rules=(
        AllocationRule("A", "B", 5000),  # A 的 50% 分给 B
        AllocationRule("A", "X", 5000),  # A 的 50% 分给 X
        AllocationRule("B", "A", 5000),  # B 的 50% 回流给 A
        AllocationRule("B", "Y", 5000),  # B 的 50% 分给 Y
    ),
    initial_costs={"A": 100},  # 单位：分，非负整数
)

allocate(snapshot)  # {'X': 67, 'Y': 33}
```

## 输入约定

- `Snapshot.rules`：完整规则快照。`AllocationRule(from_center, to_center, weight)`，
  `weight` 为正整数万分比；同一中转中心的出向权重合计必须恰好为 10000。
  有出向关系的中心即中转中心，其余为最终承接中心；两类中心都可以有初始成本。
- `Snapshot.initial_costs`：各成本中心本期初始成本（非负整数分），中心标识为非空 ASCII 字符串。
- 返回值：`dict[str, int]`，各最终承接中心本次应承担的金额（分），总和严格等于输入总成本。

## 计算语义

- 每个中转中心应分出的总额 = 自身初始成本 + 其他中心分给它的金额，
  各去向按权重分配；所有关系同时成立（联立线性方程组的有理数精确解），
  与中心和关系的排列顺序无关。
- 金额只在最终承接中心汇总完成后统一取整：先取各中心精确金额的整数部分，
  差额按精确小数余量从大到小逐分补齐（每个中心最多补 1 分），
  余量相同按中心标识 ASCII 字典序优先。
- 完全没有成本可达的封闭回流组不影响试算；但只要正成本能够沿分摊关系
  进入一个没有任何路径通向最终承接中心的回流组，整次试算失败。

## 异常

- `ValidationError`：输入不合法（负成本、非正权重、出向权重合计不为 10000、非法标识）。
- `ClosedLoopError`：正成本进入无出路的回流组。
- `AllocationError`：上述两者的基类，可统一捕获。

## 运行测试

```bash
python3 -m unittest discover -s tests -v
```
