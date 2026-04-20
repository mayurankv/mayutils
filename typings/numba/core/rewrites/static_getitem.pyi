from numba.core.rewrites import Rewrite, register_rewrite

@register_rewrite("before-inference")
class RewriteConstGetitems(Rewrite):
    def match(self, func_ir, block, typemap, calltypes):  # -> bool:
        ...
    def apply(self): ...

@register_rewrite("after-inference")
class RewriteStringLiteralGetitems(Rewrite):
    def match(self, func_ir, block, typemap, calltypes):  # -> bool:

        ...
    def apply(self):  # -> Block:

        ...

@register_rewrite("after-inference")
class RewriteStringLiteralSetitems(Rewrite):
    def match(self, func_ir, block, typemap, calltypes):  # -> bool:

        ...
    def apply(self):  # -> Block:

        ...

@register_rewrite("before-inference")
class RewriteConstSetitems(Rewrite):
    def match(self, func_ir, block, typemap, calltypes):  # -> bool:
        ...
    def apply(self): ...
