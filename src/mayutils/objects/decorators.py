"""Reusable function decorators for the mayutils library.

This module provides higher-order utilities used to author ergonomic
decorators. In particular, :func:`flexwrap` is a meta-decorator that
adapts a decorator factory so it can be applied either bare
(``@my_deco``) or parameterised (``@my_deco(option=value)``) without
requiring the author to hand-write the dispatch boilerplate. The
adapted decorators preserve the wrapped callable's metadata via
:func:`functools.update_wrapper`, so introspection tools continue to
see the original signature, name and docstring.
"""

from collections.abc import Callable
from functools import update_wrapper, wraps
from typing import Any, cast


def flexwrap[D: Callable[..., Any]](
    deco: D,
) -> D:
    """Adapt a decorator factory so it supports bare and parameterised forms.

    Converts ``deco`` into a decorator that can be invoked either as
    ``@deco`` (passing the target callable as the sole positional
    argument) or as ``@deco(**kwargs)`` (returning a decorator that is
    then applied to the target callable). The returned object inspects
    its call shape at runtime: a single callable positional with no
    keyword arguments is treated as the bare form, while any other
    combination is treated as a parameterised invocation whose
    arguments are forwarded to ``deco`` alongside the target function.
    Metadata on the wrapped callable is preserved via
    :func:`functools.update_wrapper`.

    Parameters
    ----------
    deco : Callable[..., Any]
        Decorator factory to adapt. Its first positional parameter must
        be the function being decorated; any additional parameters must
        be keyword-only configuration options, because the parameterised
        form rejects extra positional arguments.

    Returns
    -------
    Callable[..., Any]
        A callable sharing ``deco``'s type that dispatches to the bare
        or parameterised code path based on how it is invoked. When
        called bare, it returns the wrapped function directly; when
        called with keyword arguments, it returns a secondary decorator
        bound to those arguments.

    Raises
    ------
    TypeError
        If the adapted decorator is invoked with positional arguments
        other than a single callable. Only keyword configuration
        arguments are permitted in the parameterised form.

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

    Notes
    -----
    The bare-form heuristic ``len(args) == 1 and callable(args[0]) and
    not kwargs`` means a decorator whose only configuration argument is
    itself a callable cannot be detected automatically; such
    decorators must always be invoked with keyword arguments.
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
            """Apply the parameterised decorator to a target callable.

            Invokes the outer ``deco`` factory with the captured
            configuration keyword arguments and the supplied ``func``,
            then transfers ``func``'s metadata onto the resulting
            wrapper so attributes such as ``__name__``, ``__doc__`` and
            ``__wrapped__`` behave as if the function had been wrapped
            directly.

            Parameters
            ----------
            func : Callable[..., Any]
                Target callable to decorate. Its signature must be
                compatible with whatever call contract ``deco``
                establishes for its wrapped functions.

            Returns
            -------
            Callable[..., Any]
                The wrapper produced by ``deco(func, **kwargs)`` with
                ``func``'s metadata copied onto it, cast back to
                ``func``'s declared type so downstream type inference
                is preserved.
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
