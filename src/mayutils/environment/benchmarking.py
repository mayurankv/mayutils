"""
Lightweight timing helpers for benchmarking code blocks.

Expose a small decorator, :func:`timing`, that measures the wall-clock
runtime of a target callable using :func:`time.perf_counter` and emits
the elapsed duration through the package-wide
:class:`~mayutils.environment.logging.Logger`. The module is designed
for ad-hoc profiling of functions and pipeline stages where a full
profiler such as :mod:`cProfile` would be overkill, and integrates with
:func:`~mayutils.objects.decorators.flexwrap` so the decorator can be
applied with or without parentheses. Unlike :func:`timeit.timeit`,
measurements here cover a single invocation inside production code paths
rather than tight repetition loops, so callers retain full control over
warmup passes and statistical aggregation.

See Also
--------
timeit.timeit : Repeat a snippet and report aggregate runtime statistics.
cProfile.Profile : Deterministic profiler for call-graph level analysis.
time.perf_counter : High-resolution monotonic clock used for sampling.
contextlib.contextmanager : Alternative API shape for scoped timing.
mayutils.objects.decorators.flexwrap : Adapter enabling bare-or-called decorator syntax.

Examples
--------
>>> from mayutils.environment.benchmarking import timing
>>> @timing
... def crunch() -> int:
...     return sum(range(10_000))
>>> crunch()
49995000
"""

import time
from collections.abc import Callable
from functools import wraps
from typing import cast

from mayutils.environment.logging import Logger
from mayutils.objects.decorators import flexwrap

logger = Logger.spawn()


@flexwrap
def timing[D: Callable[..., object]](
    func: D | None = None,
) -> D:
    """
    Measure and log the wall-clock runtime of a decorated callable.

    Wrap ``func`` so every invocation is sampled with
    :func:`time.perf_counter`, a high-resolution monotonic clock that is
    unaffected by wall-clock adjustments such as NTP corrections. The
    elapsed duration is reported through the module-level
    :class:`~mayutils.environment.logging.Logger` at ``INFO`` level, and
    because :func:`~mayutils.objects.decorators.flexwrap` adapts the
    binding, callers may use either the bare ``@timing`` form or the
    parenthesised ``@timing()`` form without re-importing. No warmup
    passes are performed and the decorator records a single observation
    per call, so downstream consumers are responsible for any
    statistical aggregation (mean, minimum, or standard deviation)
    across repeated invocations.

    Parameters
    ----------
    func
        Callable whose runtime is being instrumented. Python binds this
        automatically when the decorator is written as ``@timing`` with
        no parentheses; when the decorator is called explicitly it must
        still resolve to a non-``None`` target before the wrapper
        executes, otherwise a :class:`ValueError` is raised.

    Returns
    -------
        Wrapper around ``func`` that preserves its signature and return
        value while emitting a ``"<name> took X.XXXX seconds"`` entry
        through the module logger after each call completes.

    Raises
    ------
    ValueError
        Raised when the decorator is executed without a resolved target
        callable, which indicates it was invoked in an unsupported way
        (for example ``timing(func=None)``).

    See Also
    --------
    timeit.timeit : Repeat a snippet and report aggregate runtime statistics.
    cProfile.Profile : Deterministic profiler for call-graph level analysis.
    time.perf_counter : High-resolution monotonic clock used for sampling.
    contextlib.contextmanager : Alternative API shape for scoped timing.
    mayutils.objects.decorators.flexwrap : Adapter enabling bare-or-called decorator syntax.

    Examples
    --------
    >>> from mayutils.environment.benchmarking import timing
    >>> @timing
    ... def slow() -> int:
    ...     return sum(range(1000))
    >>> slow()
    499500
    >>> @timing()
    ... def greet(name: str) -> str:
    ...     return f"hello {name}"
    >>> greet("world")
    'hello world'
    """
    if func is None:
        msg = "No function provided"
        raise ValueError(msg)

    @wraps(wrapped=func)
    def wrapper(
        *args: object,
        **kwargs: object,
    ) -> object:
        """
        Execute the wrapped callable and report its wall-clock duration.

        Start a :func:`time.perf_counter` sample before delegating to the
        original ``func`` with the caller's arguments, then write the
        elapsed time to the module logger and return the original result
        unchanged. Only a single observation is captured per invocation
        and no warmup passes are performed, so the reported duration
        reflects the raw cost of that specific call including any JIT,
        caching, or import side effects incurred on the first run.
        Callers who need mean, minimum, or standard-deviation statistics
        across repeated runs should aggregate the logged samples
        externally or switch to :func:`timeit.repeat`.

        Parameters
        ----------
        *args
            Positional arguments forwarded verbatim to the wrapped
            callable, preserving its original calling convention so the
            decorator remains transparent to downstream consumers.
        **kwargs
            Keyword arguments forwarded verbatim to the wrapped
            callable, preserving its original calling convention so the
            decorator remains transparent to downstream consumers.

        Returns
        -------
            Whatever object the wrapped callable produced, passed
            through without modification so the decorator is fully
            transparent to downstream consumers.

        See Also
        --------
        timeit.timeit : Repeat a snippet and report aggregate runtime statistics.
        cProfile.Profile : Deterministic profiler for call-graph level analysis.
        time.perf_counter : High-resolution monotonic clock used for sampling.
        contextlib.contextmanager : Alternative API shape for scoped timing.
        timing : Parent decorator that constructs this wrapper.

        Examples
        --------
        >>> from mayutils.environment.benchmarking import timing
        >>> @timing
        ... def add(a: int, b: int) -> int:
        ...     return a + b
        >>> add(2, 3)
        5
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
