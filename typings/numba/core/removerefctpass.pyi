from llvmlite.ir.transforms import CallVisitor

"""
Implement a rewrite pass on a LLVM module to remove unnecessary
refcount operations.
"""

class _MarkNrtCallVisitor(CallVisitor):
    def __init__(self) -> None: ...
    def visit_Call(self, instr):  # -> None:
        ...

_accepted_nrtfns = ...

def remove_unnecessary_nrt_usage(function, context, fndesc):  # -> bool:

    ...
