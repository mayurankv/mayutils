from numba.core.extending import intrinsic

"""
This file provides internal compiler utilities that support certain special
operations with tuple and workarounds for limitations enforced in userland.
"""

@intrinsic
def tuple_setitem(typingctx, tup, idx, val):  # -> tuple[Any, Callable[..., Any]]:

    ...
@intrinsic
def build_full_slice_tuple(tyctx, sz):  # -> tuple[Any | Signature, Callable[..., Any]]:

    ...
@intrinsic
def unpack_single_tuple(tyctx, tup):  # -> tuple[Any | Signature, Callable[..., Any]]:

    ...
