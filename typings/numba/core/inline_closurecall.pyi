from numba.core import rewrites
from numba.core.extending import intrinsic

enable_inline_arraycall = ...

def callee_ir_validator(func_ir):  # -> None:

    ...

class InlineClosureCallPass:
    def __init__(self, func_ir, parallel_options, swapped=..., typed=...) -> None: ...
    def run(self):  # -> None:

        ...

def check_reduce_func(func_ir, func_var): ...

class InlineWorker:
    def __init__(
        self, typingctx=..., targetctx=..., locals=..., pipeline=..., flags=..., validator=..., typemap=..., calltypes=...
    ) -> None: ...
    def inline_ir(
        self, caller_ir, block, i, callee_ir, callee_freevars, arg_typs=...
    ):  # -> tuple[Any, dict[Any, Any], dict[Any, Any], list[Any]]:

        ...
    def inline_function(self, caller_ir, block, i, function, arg_typs=...):  # -> tuple[Any, dict[Any, Any], dict[Any, Any], list[Any]]:

        ...
    def run_untyped_passes(self, func, enable_ssa=...):  # -> None:

        ...
    def update_type_and_call_maps(self, callee_ir, arg_typs):  # -> None:

        ...

def inline_closure_call(
    func_ir,
    glbls,
    block,
    i,
    callee,
    typingctx=...,
    targetctx=...,
    arg_typs=...,
    typemap=...,
    calltypes=...,
    work_list=...,
    callee_validator=...,
    replace_freevars=...,
):  # -> tuple[dict[Any, Any], dict[Any, Any]]:

    ...
@intrinsic
def length_of_iterator(typingctx, val):  # -> tuple[Signature, Callable[..., Any]]:

    ...

@rewrites.register_rewrite("after-inference")
class RewriteArrayOfConsts(rewrites.Rewrite):
    def __init__(self, state, *args, **kws) -> None: ...
    def match(self, func_ir, block, typemap, calltypes):  # -> bool:
        ...
    def apply(self): ...
