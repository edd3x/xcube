import warnings
from typing import Callable, Dict, Optional


from .info import OpInfo


class OpRegistry:
    def __init__(self):
        self._ops: Dict[str, Callable] = {}

    @property
    def ops(self) -> Dict[str, Callable]:
        return self._ops.copy()

    def get_op(self, op_id: str) -> Optional[Callable]:
        return self._ops.get(op_id)

    def register_op(self, function: Callable) -> OpInfo:
        op_name = function.__name__
        prev_op = self._ops.get(op_name)
        if prev_op is None or prev_op is not function:
            op_info = OpInfo.new_op_info(function)
            op = op_info.make_op(function)
            self._ops[op_name] = op
        else:
            op_info = OpInfo.get_op_info(function)
        return op_info


# Default operation registry
OP_REGISTRY = OpRegistry()
