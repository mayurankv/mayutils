from numba.core.extending import intrinsic

"""
Exception handling intrinsics.
"""

@intrinsic
def exception_check(typingctx):  # -> tuple[Any | Signature, Callable[..., Any]]:

    ...
@intrinsic
def mark_try_block(typingctx):  # -> tuple[Any | Signature, Callable[..., Any]]:

    ...
@intrinsic
def end_try_block(typingctx):  # -> tuple[Any | Signature, Callable[..., Any]]:

    ...
@intrinsic
def exception_match(typingctx, exc_value, exc_class):  # -> tuple[Any | Signature, Callable[..., Constant | Any]]:

    ...
