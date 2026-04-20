from llvmlite import ir

"""
LLVM pass that converts intrinsic into other math calls
"""

class _DivmodFixer(ir.Visitor):
    def visit_Instruction(self, instr):  # -> None:
        ...

def fix_divmod(mod):  # -> None:

    ...

INTR_TO_CMATH = ...
OTHER_CMATHS = ...
INTR_MATH = ...
