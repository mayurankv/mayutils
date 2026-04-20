from numba.core.rewrites import Rewrite, register_rewrite

@register_rewrite("before-inference")
class RewriteConstRaises(Rewrite):
    def match(self, func_ir, block, typemap, calltypes):  # -> bool:
        ...
    def apply(self): ...
