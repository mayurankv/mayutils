"""Lightweight timing helpers for benchmarking code blocks.

This module exposes a small decorator, :func:`timing`, that measures the
wall-clock runtime of a target callable using :func:`time.perf_counter`
and emits the elapsed duration through the package-wide
:class:`~mayutils.environment.logging.Logger`. It is designed for ad-hoc
profiling of functions and pipeline stages where a full profiler would
be overkill, and integrates with :func:`~mayutils.objects.decorators.flexwrap`
so the decorator can be applied with or without parentheses.
"""

import time
from collections.abc import Callable
from functools import wraps
from typing import Any, cast

from mayutils.environment.logging import Logger
from mayutils.objects.decorators import flexwrap

logger = Logger.spawn()


@flexwrap
def timing[D: Callable[..., Any]](
    func: D | None = None,
) -> D:
    """Measure and log the wall-clock runtime of a decorated callable.

    Wraps ``func`` so that each invocation is timed with
    :func:`time.perf_counter` and the elapsed duration is reported
    through the module-level :class:`Logger`. Thanks to
    :func:`flexwrap`, this decorator accepts both the bare
    ``@timing`` and parametrised ``@timing(show=False)`` forms,
    letting callers toggle stdout visibility without re-importing.

    Parameters
    ----------
    func : Callable, optional
        Callable whose runtime is being instrumented. Python binds
        this automatically when the decorator is written as
        ``@timing`` with no parentheses; when the decorator is called
        explicitly it must still resolve to a non-``None`` target
        before the wrapper executes.
    show : bool, default True
        Controls whether the timing line is echoed to stdout in
        addition to being written to the logger. When ``False`` the
        duration is only recorded through the logging handlers, which
        is useful in quiet batch contexts.

    Returns
    -------
    Callable
        A wrapper around ``func`` that preserves its signature and
        return value while emitting a ``"<name> took X.XXXX seconds"``
        entry after each call completes.

    Raises
    ------
    ValueError
        Raised when the decorator is executed without a resolved
        target callable, which indicates it was invoked in an
        unsupported way (for example ``timing(show=True)()``).

    Examples
    --------
    >>> @timing
    ... def slow() -> int:
    ...     return sum(range(1000))
    >>> slow()
    499500
    """
    if func is None:
        msg = "No function provided"
        raise ValueError(msg)

    @wraps(wrapped=func)
    def wrapper(
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        """Execute the wrapped callable and report its wall-clock duration.

        Starts a :func:`time.perf_counter` sample, delegates to the
        original ``func`` with the caller's arguments, and writes the
        elapsed time to the module logger before returning the original
        result unchanged.

        Parameters
        ----------
        *args : Any
            Positional arguments forwarded verbatim to the wrapped
            callable, preserving its original calling convention.
        **kwargs : Any
            Keyword arguments forwarded verbatim to the wrapped
            callable, preserving its original calling convention.

        Returns
        -------
        Any
            Whatever object the wrapped callable produced, passed
            through without modification so the decorator is fully
            transparent to downstream consumers.
        """
        start = time.perf_counter()

        result = func(
            *args,
            **kwargs,
        )

        end = time.perf_counter()

        length = end - start

        msg = f"{func.__name__} took {length:.4f} seconds"
        logger.info(msg)

        return result

    return cast("D", wrapper)
