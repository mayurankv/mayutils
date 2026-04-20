from numba.core.extending import intrinsic

"""
This file provides internal compiler utilities that support certain special
operations with numpy.
"""

@intrinsic
def empty_inferred(typingctx, shape):  # -> tuple[Any | Signature, Callable[..., Any]]:

    ...
@intrinsic
def to_fixed_tuple(typingctx, array, length):  # -> tuple[Any | Signature, Callable[..., Any]]:

    ...
