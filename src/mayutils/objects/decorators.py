"""Reusable decorators, including :func:`flexwrap` for decorators with optional arguments."""

from collections.abc import Callable
from functools import update_wrapper, wraps
from typing import Any, cast


def flexwrap[D: Callable[..., Any]](
    deco: D,
) -> D:
    """Meta-decorator that lets a decorator be used both with and without arguments.

    The decorated factory may be applied either as ``@my_deco`` (no
    parentheses, single positional argument = the target function) or
    as ``@my_deco(...)`` (parentheses + configuration arguments). The
    meta-decorator inspects the call shape at runtime and dispatches
    accordingly.

    Parameters
    ----------
    deco : Callable[..., Any]
        The decorator factory to adapt. It must accept the target
        function as its first positional argument, optionally followed
        by configuration arguments.

    Returns
    -------
    Callable[..., Any]
        A wrapped decorator that works in both call shapes.

    Examples
    --------
    >>> @flexwrap
    ... def shout(func, prefix="!"):
    ...     def wrapper(*a, **k):
    ...         return prefix + func(*a, **k).upper()
    ...
    ...     return wrapper
    >>> @shout
    ... def hello() -> str:
    ...     return "hi"
    >>> @shout(prefix=">>> ")
    ... def hey() -> str:
    ...     return "hey"
    >>> hello(), hey()
    ('!HI', '>>> HEY')
    """

    @wraps(wrapped=deco)
    def deco_wrapper(
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        if len(args) == 1 and callable(args[0]) and not kwargs:
            func = args[0]

            return update_wrapper(
                wrapped=func,
                wrapper=deco(func),
            )

        if args:
            msg = "This decorator only supports keyword arguments."
            raise TypeError(msg)

        def true_deco[T: Callable[..., Any]](
            func: T,
        ) -> T:
            """Apply the parameterised decorator to ``func``.

            Parameters
            ----------
            func : T
                Func.

            Returns
            -------
            T
                The return value.
            """
            return cast(
                "T",
                update_wrapper(
                    wrapped=func,
                    wrapper=deco(
                        func,
                        *args,
                        **kwargs,
                    ),
                ),
            )

        return update_wrapper(
            wrapped=deco,
            wrapper=true_deco,
        )

    return cast("D", deco_wrapper)
