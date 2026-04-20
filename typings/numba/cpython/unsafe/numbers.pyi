from numba.core.extending import intrinsic

""" This module provides the unsafe things for targets/numbers.py
"""

@intrinsic
def viewer(tyctx, val, viewty):  # -> tuple[Any | Signature, Callable[..., Any]]:

    ...
@intrinsic
def trailing_zeros(typeingctx, src):  # -> tuple[Any | Signature, Callable[..., Any]]:

    ...
@intrinsic
def leading_zeros(typeingctx, src):  # -> tuple[Any | Signature, Callable[..., Any]]:

    ...
