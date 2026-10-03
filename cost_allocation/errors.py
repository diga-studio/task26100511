"""异常定义。"""


class AllocationError(Exception):
    """试算失败的基类。"""


class ValidationError(AllocationError):
    """输入快照不合法（权重、标识、成本等）。"""


class ClosedLoopError(AllocationError):
    """正成本进入没有任何路径通向最终承接中心的回流组。"""
