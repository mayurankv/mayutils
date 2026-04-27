"""
Provide reusable function decorators for the mayutils library.

This module collects higher-order utilities used to author ergonomic
decorators. In particular, :func:`flexwrap` is a meta-decorator that
adapts a decorator factory so it can be applied either bare
(``@my_deco``) or parameterised (``@my_deco(option=value)``) without
requiring the author to hand-write the dispatch boilerplate. The
adapted decorators preserve the wrapped callable's metadata via
:func:`functools.update_wrapper`, so introspection tools continue to
see the original signature, name and docstring.

See Also
--------
functools.wraps : Copy wrapped-callable metadata onto a wrapper.
functools.update_wrapper : Lower-level metadata transfer primitive.
contextlib.contextmanager : Decorator factory that turns a generator
    into a context manager using similar metadata preservation.

Examples
--------
>>> from mayutils.objects.decorators import flexwrap
>>> @flexwrap
... def trace(fn, *, prefix="trace"):
...     def wrapper(*args, **kwargs):
...         return fn(*args, **kwargs)
...
...     return wrapper
>>> @trace
... def bare(x):
...     return x
>>> bare(1)
1
"""

from collections.abc import Callable
from functools import update_wrapper, wraps
from typing import cast


def flexwrap[D: Callable[..., object]](
    deco: D,
) -> D:
    """
    Adapt a decorator factory so it supports bare and parameterised forms.

    Convert ``deco`` into a decorator that can be invoked either as
    ``@deco`` (passing the target callable as the sole positional
    argument) or as ``@deco(**kwargs)`` (returning a decorator that is
    then applied to the target callable). The returned object inspects
    its call shape at runtime: a single callable positional with no
    keyword arguments is treated as the bare form, while any other
    combination is treated as a parameterised invocation whose
    arguments are forwarded to ``deco`` alongside the target function.
    Metadata on the wrapped callable is preserved via
    :func:`functools.update_wrapper`, so ``__name__``, ``__doc__`` and
    ``__wrapped__`` continue to reflect the original function.

    Parameters
    ----------
    deco
        Decorator factory to adapt. Its first positional parameter must
        be the function being decorated; any additional parameters must
        be keyword-only configuration options, because the parameterised
        form rejects extra positional arguments.

    Returns
    -------
        A callable sharing ``deco``'s type that dispatches to the bare
        or parameterised code path based on how it is invoked. When
        called bare, it returns the wrapped function directly; when
        called with keyword arguments, it returns a secondary decorator
        bound to those arguments.

    See Also
    --------
    functools.wraps : Decorator used internally to propagate ``deco``'s
        metadata onto the dispatch wrapper returned by this function.
    functools.update_wrapper : Lower-level primitive used by the bare
        and parameterised branches to transfer metadata onto the final
        wrapper.
    functools.cache : Example of a decorator factory that benefits from
        ``flexwrap``-style dual-invocation ergonomics.
    contextlib.contextmanager : Sibling pattern that wraps callables
        while preserving their introspection surface.

    Notes
    -----
    The bare-form heuristic ``len(args) == 1 and callable(args[0]) and
    not kwargs`` means a decorator whose only configuration argument is
    itself a callable cannot be detected automatically; such
    decorators must always be invoked with keyword arguments.

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
        *args: object,
        **kwargs: object,
    ) -> object:
        """
        Dispatch between bare and parameterised invocation of ``deco``.

        Inspect the supplied ``args`` and ``kwargs`` to decide whether
        the enclosing decorator is being applied directly to a target
        callable or being configured with keyword options. A single
        callable positional with no keywords triggers the bare path,
        which immediately wraps the function; any other call shape
        builds a secondary decorator bound to the captured ``kwargs``.
        Metadata on the wrapped callable is propagated via
        :func:`functools.update_wrapper` in both branches.

        Parameters
        ----------
        *args
            Positional arguments forwarded from the decorator call
            site. In the supported usage this is either empty or a
            single callable; any other shape raises ``TypeError``.
        **kwargs
            Keyword configuration options forwarded to ``deco`` when
            the parameterised form is used.

        Returns
        -------
            Either the wrapped target callable (bare form) or a nested
            decorator that, when applied to a callable, returns the
            final wrapper produced by ``deco``.

        Raises
        ------
        TypeError
            If positional arguments other than a single callable are
            supplied, signalling misuse of the parameterised form.

        See Also
        --------
        flexwrap : Outer meta-decorator that installs this dispatcher.
        functools.wraps : Applied to this function to copy ``deco``'s
            metadata onto the dispatcher itself.
        functools.update_wrapper : Transfers metadata from the target
            callable onto the wrapper produced by ``deco``.

        Examples
        --------
        >>> @flexwrap
        ... def tag(func, label="t"):
        ...     def wrapper(*a, **k):
        ...         return (label, func(*a, **k))
        ...
        ...     return wrapper
        >>> @tag
        ... def bare():
        ...     return 1
        >>> @tag(label="x")
        ... def parameterised():
        ...     return 2
        >>> bare(), parameterised()
        (('t', 1), ('x', 2))
        """
        if len(args) == 1 and callable(args[0]) and not kwargs:
            func = args[0]

            return update_wrapper(
                wrapped=func,
                wrapper=deco(func),
            )

        if args:
            msg = "This decorator only supports keyword arguments."
            raise TypeError(msg)

        def true_deco[T: Callable[..., object]](
            func: T,
        ) -> T:
            """
            Apply the parameterised decorator to a target callable.

            Invoke the outer ``deco`` factory with the captured
            configuration keyword arguments and the supplied ``func``,
            then transfer ``func``'s metadata onto the resulting
            wrapper so attributes such as ``__name__``, ``__doc__``
            and ``__wrapped__`` behave as if the function had been
            wrapped directly. The resulting wrapper is cast back to
            ``func``'s declared type to preserve static type inference
            at call sites.

            Parameters
            ----------
            func
                Target callable to decorate. Its signature must be
                compatible with whatever call contract ``deco``
                establishes for its wrapped functions.

            Returns
            -------
                The wrapper produced by ``deco(func, **kwargs)`` with
                ``func``'s metadata copied onto it, cast back to
                ``func``'s declared type so downstream type inference
                is preserved.

            See Also
            --------
            flexwrap : Outer meta-decorator that creates this closure.
            functools.wraps : Decorator-style convenience wrapper
                around :func:`functools.update_wrapper`.
            functools.update_wrapper : Primitive used here to copy
                metadata from ``func`` onto the ``deco``-produced
                wrapper.

            Examples
            --------
            >>> @flexwrap
            ... def prefix(func, token="*"):
            ...     def wrapper(*a, **k):
            ...         return token + func(*a, **k)
            ...
            ...     return wrapper
            >>> @prefix(token="#")
            ... def greet() -> str:
            ...     return "hi"
            >>> greet()
            '#hi'
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
