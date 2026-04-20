from numba import cuda, types
from numba.core.extending import overload_attribute
from numba.cuda.extending import intrinsic

@intrinsic
def grid(typingctx, ndim):  # -> tuple[Signature, Callable[..., Any | list[Any] | Constant | None]]:

    ...
@intrinsic
def gridsize(typingctx, ndim):  # -> tuple[Signature, Callable[..., Any | Constant | None]]:

    ...
@overload_attribute(types.Module(cuda), "warpsize", target="cuda")
def cuda_warpsize(mod):  # -> Callable[..., tuple[Signature, Callable[..., Any]]]:

    ...
@intrinsic
def syncthreads(typingctx):  # -> tuple[Signature, Callable[..., Any]]:

    ...
@intrinsic
def syncthreads_count(typingctx, predicate):  # -> tuple[Signature, Callable[..., Any]] | None:

    ...
@intrinsic
def syncthreads_and(typingctx, predicate):  # -> tuple[Signature, Callable[..., Any]] | None:

    ...
@intrinsic
def syncthreads_or(typingctx, predicate):  # -> tuple[Signature, Callable[..., Any]] | None:

    ...
