"""
Provide filesystem-backed memoisation decorators with optional TTL semantics.

Three decorator classes are exposed. :class:`lru_cache` is the fast
path: a flexwrap-wrapped layer over :func:`functools.lru_cache` with
mayutils-consistent ``cache_info`` / ``cache_clear`` / ``cache=False``
plumbing. :class:`cache` is the general-purpose memoiser — OrderedDict
backed, supporting :class:`~mayutils.objects.datetime.Duration`-typed
TTLs and optional pickle-file persistence. :class:`cache_df` is a
DataFrame-specialised variant that routes reads and writes through the
:class:`~mayutils.interfaces.filetypes.DataFile` registry, so any
tabular file format registered there can back the cache. TTLs are
accepted as any :class:`datetime.timedelta` so pendulum's
:class:`~pendulum.Duration` (a ``timedelta`` subclass) works natively
and is the preferred form inside ``mayutils``. Cache keys are derived
from the wrapped callable's name together with the call's positional
and keyword arguments via :func:`mayutils.objects.hashing.hash_inputs`.

See Also
--------
functools.lru_cache : Standard-library in-memory LRU decorator.
functools.cache : Unbounded in-memory cache decorator.
diskcache : Third-party disk-backed cache library offering similar
    persistence semantics.
mayutils.environment.logging : Sibling environment helper providing
    structured logging primitives.

Examples
--------
>>> from datetime import timedelta
>>> from mayutils.environment.memoisation import cache, cache_df
>>> @cache(ttl=timedelta(minutes=5), maxsize=128)
... def fetch_rate(currency: str) -> float:
...     return 1.23
>>> fetch_rate("GBP")
1.23
"""

from __future__ import annotations

import contextlib
import functools
import importlib
import pickle
from collections import OrderedDict
from functools import _CacheInfo as CacheInfo  # pyright: ignore[reportPrivateUsage]
from functools import _lru_cache_wrapper as LRUCacheWrapper  # noqa: N812
from functools import update_wrapper
from pathlib import Path
from typing import TYPE_CHECKING

from mayutils.data import CACHE_FOLDER
from mayutils.environment.filesystem import is_file_stale
from mayutils.interfaces.filetypes import DataFile
from mayutils.objects.datetime import DateTime
from mayutils.objects.decorators import flexwrap
from mayutils.objects.hashing import hash_inputs

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from mayutils.objects.dataframes import DataframeBackends, DataFrames
    from mayutils.objects.datetime import Duration


def register_datafile(
    suffix: str,
    /,
) -> None:
    """
    Ensure the :class:`DataFile` subclass matching ``suffix`` is loaded.

    The suffix-indexed registry on
    :class:`~mayutils.interfaces.filetypes.DataFile` is populated via
    :meth:`object.__init_subclass__`, which only fires once the subclass
    module has been imported. This helper imports the sibling submodule
    of :mod:`mayutils.interfaces.filetypes` whose name matches ``suffix``
    (``".parquet"`` resolves to :mod:`mayutils.interfaces.filetypes.parquet`),
    triggering registration so subsequent :meth:`DataFile.from_path`
    lookups succeed. Callers supplying a non-default suffix backed by a
    custom subclass are responsible for importing it themselves before
    calling the cache entry points.

    Parameters
    ----------
    suffix
        File extension identifying the cache format. Accepted with
        or without a leading ``"."``; case-insensitive.

    See Also
    --------
    cache_df : DataFrame memoisation decorator that invokes this
        helper before any :meth:`DataFile.from_path` dispatch.
    functools.lru_cache : Comparable in-memory memoisation decorator
        without filesystem registration concerns.
    functools.cache : Unbounded in-memory cache decorator for
        contrast with the filesystem-backed behaviour here.
    diskcache : Alternative disk-backed cache library.
    mayutils.environment.logging : Sibling environment helper for
        structured logging.

    Examples
    --------
    >>> from mayutils.environment.memoisation import register_datafile
    >>> register_datafile("parquet")
    >>> register_datafile(".csv")
    """
    key = suffix.lstrip(".").lower()
    if f".{key}" in DataFile._registry:  # noqa: SLF001
        return
    with contextlib.suppress(ImportError):
        importlib.import_module(name=f"mayutils.interfaces.filetypes.{key}")


def make_cache_key(
    func_name: str,
    /,
    *,
    args: tuple[object, ...],
    kwargs: Mapping[str, object],
) -> str:
    """
    Build a deterministic cache key for a call signature.

    Combines the wrapped callable's ``__name__`` with the call's
    positional and keyword arguments via
    :func:`mayutils.objects.hashing.hash_inputs`, yielding a
    hexadecimal digest stable across interpreter sessions. The result
    can be used directly as a filename stem for on-disk caches or as
    a dictionary key for in-memory stores. Because the digest includes
    the function name, two callables with the same argument shape
    produce distinct keys.

    Parameters
    ----------
    func_name
        Identifier of the wrapped callable. Usually ``func.__name__``;
        collisions between callables sharing a short name are the
        caller's responsibility to avoid (for instance by giving each
        decorator a distinct cache location).
    args
        Positional arguments supplied to the call.
    kwargs
        Keyword arguments supplied to the call.

    Returns
    -------
        Lowercase hexadecimal SHA-256 digest of the serialised
        ``{func, args, kwargs}`` bundle, suitable as a cache key.

    See Also
    --------
    cache : Generic memoisation decorator that uses this helper to
        compute its in-memory dictionary keys.
    cache_df : DataFrame memoisation decorator that uses this helper
        to derive cache filenames.
    functools.lru_cache : Standard-library decorator with its own
        opaque hashing scheme.
    functools.cache : Unbounded analogue of ``lru_cache``.
    diskcache : Third-party library whose keys are produced by its
        own pickle-based hasher.
    mayutils.environment.logging : Sibling environment helper.

    Examples
    --------
    >>> from mayutils.environment.memoisation import make_cache_key
    >>> key = make_cache_key("fetch_rate", args=("GBP",), kwargs={})
    >>> isinstance(key, str)
    True
    """
    return hash_inputs(
        func=func_name,
        args=list(args),
        kwargs=dict(kwargs),
    )


def is_expired(
    expires_at: DateTime | None,
    /,
) -> bool:
    """
    Evaluate whether a cached entry's expiry has passed.

    Used by :class:`cache` during lookup so stale entries can be
    evicted lazily on the next access rather than via a sweeper
    thread. Treats ``None`` as an "immortal" marker so callers that
    do not configure a TTL bypass the comparison entirely. The
    comparison uses :meth:`DateTime.now` so it honours whatever
    timezone semantics are baked into the :class:`DateTime` subclass.

    Parameters
    ----------
    expires_at
        Absolute expiry timestamp. ``None`` means "no expiry"; the
        entry is always considered fresh.

    Returns
    -------
        ``True`` when ``expires_at`` is non-``None`` and already in
        the past; ``False`` otherwise.

    See Also
    --------
    expiry : Companion helper that produces the ``expires_at``
        timestamp from a relative TTL.
    cache : Generic memoisation decorator invoking this helper during
        lookup.
    functools.lru_cache : Standard-library cache without TTL support.
    functools.cache : Unbounded in-memory cache without TTL support.
    diskcache : Alternative disk-backed cache that exposes TTLs
        through a different API.
    mayutils.environment.logging : Sibling environment helper.

    Examples
    --------
    >>> from datetime import timedelta
    >>> from mayutils.environment.memoisation import expiry, is_expired
    >>> is_expired(None)
    False
    >>> future = expiry(timedelta(hours=1))
    >>> is_expired(future)
    False
    """
    return expires_at is not None and expires_at <= DateTime.now()


def expiry(
    ttl: Duration | None,
    /,
) -> DateTime | None:
    """
    Compute an absolute expiry timestamp from a relative TTL.

    Turns a caller-supplied ``timedelta`` into an absolute
    :class:`DateTime` pinned to the current instant, suitable for
    storage alongside a cache entry. Propagating ``None`` unchanged
    means callers can pass ``ttl=None`` to disable expiry without
    introducing a separate code path. Because the addition uses
    :meth:`DateTime.now`, the timezone of the returned timestamp
    matches whatever convention :class:`DateTime` enforces.

    Parameters
    ----------
    ttl
        Relative lifetime. ``None`` disables expiry and propagates
        through as ``None``.

    Returns
    -------
        ``DateTime.now() + ttl`` when ``ttl`` is supplied; ``None``
        otherwise (meaning the entry never expires).

    See Also
    --------
    is_expired : Companion helper that compares ``expires_at`` against
        the current instant.
    cache : Generic memoisation decorator that stamps each entry via
        this helper.
    functools.lru_cache : Standard-library cache without TTL support.
    functools.cache : Unbounded in-memory cache without TTL support.
    diskcache : Alternative disk-backed cache with its own TTL API.
    mayutils.environment.logging : Sibling environment helper.

    Examples
    --------
    >>> from datetime import timedelta
    >>> from mayutils.environment.memoisation import expiry
    >>> expiry(None) is None
    True
    >>> stamp = expiry(timedelta(minutes=10))
    >>> stamp is not None
    True
    """
    if ttl is None:
        return None
    return DateTime.now() + ttl


@flexwrap
class lru_cache:  # noqa: N801
    """
    Decorate a callable with a fast in-process LRU cache.

    Thin flexwrap-wrapped layer over :func:`functools.lru_cache` that
    keeps the hot-path behaviour — argument hashing in C, LRU
    eviction, bounded ``maxsize`` — while adding the mayutils
    decorator conventions. In particular, every call site can pass
    ``cache=False`` as a trailing keyword to bypass the cache for a
    single invocation without having to reach for
    :meth:`cache_clear`; and :meth:`cache_info`/:meth:`cache_clear`
    stay callable from the decorator instance itself. Use this when
    the goal is purely in-memory memoisation with no TTL and no
    persistence, where the C-accelerated path is worth the simpler
    contract. Reach for :class:`cache` when TTL eviction or a
    pickle-backed persistent tier is needed.

    Parameters
    ----------
    func
        The wrapped callable. Supplied automatically by
        :func:`flexwrap` when the decorator is applied; callers do
        not pass it directly.
    maxsize
        Upper bound on the number of retained entries. ``None``
        disables the bound, matching :func:`functools.lru_cache`'s
        ``maxsize=None`` semantics (unbounded cache). Defaults to
        ``128``, matching the stdlib default.
    typed
        When ``True``, arguments that compare equal but differ in
        type are cached under separate keys. Mirrors
        :func:`functools.lru_cache`'s ``typed`` argument exactly.

    Attributes
    ----------
    func
        The wrapped callable.
    maxsize
        Configured bound on live entries.
    typed
        Whether arguments are keyed by type as well as value.

    See Also
    --------
    cache : TTL-aware, optionally-persistent sibling that wraps an
        :class:`~collections.OrderedDict` directly.
    cache_df : DataFrame-specialised sibling that persists results
        through the :class:`~mayutils.interfaces.filetypes.DataFile`
        registry.
    functools.lru_cache : Standard-library primitive this decorator
        delegates to for the hot path.
    functools.cache : Unbounded stdlib analogue (equivalent to
        ``lru_cache(maxsize=None)``).

    Examples
    --------
    >>> from mayutils.environment.memoisation import lru_cache
    >>> @lru_cache
    ... def square(n: int) -> int:
    ...     return n * n
    >>> square(3), square(3)
    (9, 9)
    >>> square.cache_info().hits
    1
    >>> @lru_cache(maxsize=256, typed=True)
    ... def add(a, b):
    ...     return a + b
    >>> add(1, 2)
    3
    >>> add(1, 2, cache=False)  # bypass the cache for this call
    3
    """

    def __init__(
        self,
        func: Callable[..., object] | None = None,
        /,
        *,
        maxsize: int | None = 128,
        typed: bool = False,
    ) -> None:
        """
        Bind the wrapped callable behind a :func:`functools.lru_cache`.

        Stores the wrapped callable, the caching knobs, and a
        memoised view produced by :func:`functools.lru_cache`. The
        wrapper metadata is then copied from ``func`` so the
        decorated object mirrors the original's ``__name__``,
        ``__doc__`` and ``__wrapped__`` attributes.

        Parameters
        ----------
        func
            The callable whose return values should be memoised. Set
            automatically by :func:`flexwrap`.
        maxsize
            LRU bound forwarded to :func:`functools.lru_cache`.
            ``None`` disables the bound.
        typed
            Forwarded to :func:`functools.lru_cache` to control
            whether equal-but-differently-typed arguments are
            distinguished by the cache key.

        Raises
        ------
        ValueError
            When ``func`` is ``None``, meaning the decorator was
            invoked without a target callable.

        See Also
        --------
        functools.lru_cache : Underlying cache engine wrapped here.
        cache_info : Inspect hit/miss statistics.

        Examples
        --------
        >>> from mayutils.environment.memoisation import lru_cache
        >>> @lru_cache(maxsize=4)
        ... def add(a, b):
        ...     return a + b
        >>> add(1, 2)
        3
        """
        if func is None:
            msg = "No function provided"
            raise ValueError(msg)
        self.func: Callable[..., object] = func
        self.maxsize = maxsize
        self.typed = typed
        self._cached: LRUCacheWrapper[object] = functools.lru_cache(  # pyright: ignore[reportPrivateUsage]
            maxsize=maxsize,
            typed=typed,
        )(func)

        update_wrapper(wrapper=self, wrapped=func)

    def cache_info(
        self,
    ) -> CacheInfo:
        """
        Report accumulated hit/miss statistics for the underlying LRU.

        Delegates to the :class:`functools._CacheInfo` surface
        exposed by :func:`functools.lru_cache`, so callers see the
        same ``(hits, misses, maxsize, currsize)`` quadruple they
        would from an un-decorated stdlib LRU.

        Returns
        -------
            Named tuple as returned by
            :meth:`functools.lru_cache.cache_info`.

        See Also
        --------
        functools.lru_cache : Stdlib cache whose statistics are forwarded.
        cache_clear : Reset the counters by clearing the cache.

        Examples
        --------
        >>> from mayutils.environment.memoisation import lru_cache
        >>> @lru_cache
        ... def square(n):
        ...     return n * n
        >>> _ = square(2)
        >>> square.cache_info().misses
        1
        """
        return self._cached.cache_info()

    def cache_clear(
        self,
    ) -> None:
        """
        Evict every entry from the underlying LRU cache.

        Delegates directly to :meth:`functools.lru_cache.cache_clear`,
        resetting the hit/miss counters in the process.

        See Also
        --------
        functools.lru_cache : Stdlib cache whose ``cache_clear`` is forwarded.
        cache_info : Inspect hit/miss statistics after clearing.

        Examples
        --------
        >>> from mayutils.environment.memoisation import lru_cache
        >>> @lru_cache
        ... def square(n):
        ...     return n * n
        >>> _ = square(2)
        >>> square.cache_clear()
        >>> square.cache_info().hits
        0
        """
        self._cached.cache_clear()

    def __call__(
        self,
        *args: object,
        cache: bool = True,
        **kwargs: object,
    ) -> object:
        """
        Dispatch the call through the LRU cache, honouring ``cache=False``.

        Routes through :func:`functools.lru_cache` when ``cache`` is
        truthy and otherwise calls the wrapped function directly so
        side-effecting code paths (live queries, randomised
        computations) can skip caching on demand without needing a
        separate API.

        Parameters
        ----------
        *args
            Positional arguments forwarded to the wrapped callable
            and included in the LRU cache key.
        cache
            Master switch for caching on this single call. ``True``
            consults and updates the LRU; ``False`` bypasses it and
            invokes the wrapped callable directly, leaving the cache
            untouched.
        **kwargs
            Keyword arguments forwarded to the wrapped callable and
            included in the LRU cache key.

        Returns
        -------
            The value produced by the wrapped callable, either served
            from the cache or freshly computed.

        See Also
        --------
        functools.lru_cache : Stdlib cache that services hits.
        cache_info : Inspect hit/miss statistics post-call.

        Examples
        --------
        >>> from mayutils.environment.memoisation import lru_cache
        >>> @lru_cache
        ... def square(n):
        ...     return n * n
        >>> square(3)
        9
        >>> square(3, cache=False)
        9
        """
        if not cache:
            return self.func(*args, **kwargs)

        return self._cached(*args, **kwargs)


@flexwrap
class cache:  # noqa: N801
    """
    Decorate a callable with an LRU cache and optional pickle persistence.

    Wraps a callable so repeat invocations with identical arguments
    return the stored result instead of re-executing the body. The
    cache is held in an :class:`~collections.OrderedDict` whose keys
    are produced by :func:`make_cache_key` and whose values are
    ``(expires_at, value)`` pairs. When ``path`` is supplied, the same
    mapping is flushed to a pickle file after every miss so the cache
    survives process restarts. Entries are evicted lazily: expired
    values are discarded when their key is next looked up, and the
    least-recently-used entry is popped when ``maxsize`` is exceeded.

    Parameters
    ----------
    func
        The wrapped callable. Supplied automatically by
        :func:`flexwrap` when the decorator is applied; callers
        normally do not pass it directly.
    path
        Filesystem location of the pickle file backing the cache.
        ``None`` keeps the cache in-memory only.
    ttl
        Lifetime of each cached entry. ``None`` disables expiry.
        Expired entries are evicted lazily on the next lookup.
    maxsize
        Upper bound on the number of retained entries. When the cache
        grows beyond the bound after a miss, the least-recently-used
        entry is evicted. ``None`` leaves the cache unbounded.

    Attributes
    ----------
    func
        The wrapped callable.
    path
        Pickle file backing the persistent tier, or ``None``.
    ttl
        Configured TTL.
    maxsize
        Configured bound.
    store
        Ordered mapping of hashed key to ``(expires_at, value)``
        tuples, maintained in LRU order.
    hits
        Number of lookups satisfied from the cache.
    misses
        Number of lookups that fell through to ``func``.

    See Also
    --------
    cache_df : DataFrame-specialised sibling that writes each entry
        to its own file via :class:`DataFile`.
    functools.lru_cache : Standard-library in-memory LRU decorator
        without TTL or persistence support.
    functools.cache : Unbounded analogue of ``lru_cache``.
    diskcache : Alternative third-party disk-backed cache library.
    mayutils.environment.logging : Sibling environment helper for
        structured logging.

    Notes
    -----
    Call sites may pass ``cache=False`` as a trailing keyword to
    bypass the cache entirely for that invocation; the wrapped
    callable is then invoked directly and the cache is neither read
    nor written.

    Examples
    --------
    >>> from datetime import timedelta
    >>> from mayutils.environment.memoisation import cache
    >>> @cache(ttl=timedelta(minutes=5), maxsize=128)
    ... def square(x: int) -> int:
    ...     return x * x
    >>> square(3)
    9
    >>> square(3, cache=False)
    9
    """

    def __init__(
        self,
        func: Callable[..., object] | None = None,
        /,
        *,
        path: Path | str | None = None,
        ttl: Duration | None = None,
        maxsize: int | None = None,
    ) -> None:
        """
        Bind the wrapped callable and load any existing persistent store.

        Initialises hit and miss counters to zero, resolves ``path``
        into a :class:`pathlib.Path` when supplied, and reads the
        stored :class:`collections.OrderedDict` from disk so that a
        warm start recovers entries from previous sessions. Copies
        metadata from the wrapped callable via
        :func:`functools.update_wrapper` so introspection tools see
        the original name and documentation. Raises immediately when
        ``func`` is missing because :func:`flexwrap` only omits it
        when the decorator was mis-applied.

        Parameters
        ----------
        func
            The callable whose return values should be memoised. Set
            automatically by :func:`flexwrap`.
        path
            Filesystem location of the pickle file backing the cache.
            When a path to an existing file is given, its contents
            become the starting cache.
        ttl
            Lifetime of each cached entry. ``None`` disables expiry.
        maxsize
            LRU bound. ``None`` disables the bound.

        Raises
        ------
        ValueError
            When ``func`` is ``None``, meaning the decorator was
            invoked without a target callable.

        See Also
        --------
        cache.__call__ : Performs lookups against the populated store.
        cache.cache_clear : Empties the store and removes the pickle file.
        functools.lru_cache : Standard-library analogue without
            persistence.
        functools.cache : Unbounded standard-library analogue.
        diskcache : Alternative disk-backed cache library.
        mayutils.environment.logging : Sibling environment helper.

        Examples
        --------
        >>> from mayutils.environment.memoisation import cache
        >>> @cache
        ... def double(x: int) -> int:
        ...     return 2 * x
        >>> double(21)
        42
        """
        if func is None:
            msg = "No function provided"
            raise ValueError(msg)
        self.func: Callable[..., object] = func
        self.path = Path(path) if path is not None else None
        self.ttl = ttl
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0

        if self.path is not None and self.path.is_file():
            with self.path.open(mode="rb") as file:
                self.store: OrderedDict[str, tuple[DateTime | None, object]] = pickle.load(file=file)  # noqa: S301
        else:
            self.store = OrderedDict()

        update_wrapper(wrapper=self, wrapped=func)

    def cache_info(
        self,
    ) -> CacheInfo:
        """
        Report accumulated hit and miss statistics for this decorator.

        Mirrors the :meth:`functools.lru_cache.cache_info` API so
        existing profiling code paths work unchanged. ``currsize``
        reflects the current length of :attr:`store`, accounting for
        lazy expiry only at the point of last observation. The
        counters are the cumulative totals since the decorator was
        instantiated or :meth:`cache_clear` was last called.

        Returns
        -------
            Named tuple ``(hits, misses, maxsize, currsize)`` where
            ``currsize`` is the number of live entries in
            :attr:`store`.

        See Also
        --------
        cache.cache_clear : Reset the store and counters.
        functools.lru_cache : Standard-library decorator exposing the
            same ``cache_info`` API.
        functools.cache : Unbounded standard-library analogue.
        diskcache : Alternative disk-backed cache library with its
            own stats surface.
        mayutils.environment.logging : Sibling environment helper.

        Examples
        --------
        >>> from mayutils.environment.memoisation import cache
        >>> @cache
        ... def triple(x: int) -> int:
        ...     return 3 * x
        >>> triple(1)
        ... triple(1)
        3
        3
        >>> triple.cache_info().hits
        1
        """
        return CacheInfo(
            hits=self.hits,
            misses=self.misses,
            maxsize=self.maxsize,
            currsize=len(self.store),
        )

    def cache_clear(
        self,
    ) -> None:
        """
        Evict every entry from the cache and reset the counters.

        Empties :attr:`store`, resets :attr:`hits` and :attr:`misses`
        to zero, and when a persistent :attr:`path` is configured
        unlinks the pickle file on disk so the next cold start does
        not re-load stale entries. Call sites typically trigger this
        to invalidate the cache after an upstream data schema change
        or between test cases.

        See Also
        --------
        cache.cache_info : Observe the counters this method resets.
        cache.__call__ : Populates the store that this method drains.
        functools.lru_cache : Standard-library decorator exposing the
            same ``cache_clear`` API.
        functools.cache : Unbounded standard-library analogue.
        diskcache : Alternative disk-backed cache library.
        mayutils.environment.logging : Sibling environment helper.

        Examples
        --------
        >>> from mayutils.environment.memoisation import cache
        >>> @cache
        ... def double(x: int) -> int:
        ...     return 2 * x
        >>> _ = double(2)
        >>> double.cache_clear()
        >>> double.cache_info().currsize
        0
        """
        self.store.clear()
        self.hits = 0
        self.misses = 0
        if self.path is not None and self.path.is_file():
            self.path.unlink()

    def _persist(
        self,
    ) -> None:
        """
        Flush the in-memory store to the pickle file when one is configured.

        Creates any missing parent directories under :attr:`path`
        before writing, so callers can point the cache at a nested
        location without having to mkdir manually. Uses
        :mod:`pickle` in binary mode so arbitrary Python objects can
        round-trip, matching the load path configured in
        :meth:`__init__`. No-op when :attr:`path` is ``None``, which
        keeps the decorator strictly in-memory.

        See Also
        --------
        cache.__init__ : Reads the pickle file written by this helper
            on start-up.
        cache.__call__ : Invokes this helper after every miss so the
            persistent tier stays in sync with ``store``.
        functools.lru_cache : Standard-library analogue without any
            persistence hook.
        functools.cache : Unbounded standard-library analogue.
        diskcache : Alternative disk-backed cache library.
        mayutils.environment.logging : Sibling environment helper.

        Examples
        --------
        >>> from pathlib import Path
        >>> from mayutils.environment.memoisation import cache
        >>> @cache(path=Path("/tmp/example.pkl"))
        ... def square(x: int) -> int:
        ...     return x * x
        >>> square(4)
        16
        """
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open(mode="wb") as file:
            pickle.dump(obj=self.store, file=file)

    def __call__(
        self,
        *args: object,
        cache: bool = True,
        **kwargs: object,
    ) -> object:
        """
        Dispatch the call through the configured cache tier.

        When ``cache`` is ``True`` the hashed key is looked up in
        :attr:`store`. A hit moves the entry to the most-recently-used
        position and returns its value, while a miss evaluates the
        wrapped callable, stores the result with an expiry derived
        from :attr:`ttl`, evicts the oldest entry if :attr:`maxsize`
        has been reached, and flushes the mapping to disk when a
        persistent path is configured. ``cache=False`` skips the
        cache entirely for this invocation so callers can bypass
        stale data without mutating the decorator state.

        Parameters
        ----------
        *args
            Positional arguments forwarded to the wrapped callable
            and included in the cache key.
        cache
            Master switch for caching behaviour on this call.
            ``True`` consults and updates the store; ``False``
            bypasses it.
        **kwargs
            Keyword arguments forwarded to the wrapped callable and
            included in the cache key.

        Returns
        -------
            The value produced by the wrapped callable, either served
            from the cache or freshly computed.

        See Also
        --------
        cache.cache_info : Inspect the hit and miss counters this
            method mutates.
        cache.cache_clear : Drop every entry populated by this method.
        functools.lru_cache : Standard-library LRU decorator without
            persistence or TTL support.
        functools.cache : Unbounded standard-library analogue.
        diskcache : Alternative disk-backed cache library.
        mayutils.environment.logging : Sibling environment helper.

        Examples
        --------
        >>> from mayutils.environment.memoisation import cache
        >>> @cache(maxsize=2)
        ... def slow_add(a: int, b: int) -> int:
        ...     return a + b
        >>> slow_add(1, 2)
        3
        >>> slow_add(1, 2, cache=False)
        3
        """
        if not cache:
            return self.func(*args, **kwargs)

        key = make_cache_key(
            getattr(self.func, "__name__", type(self.func).__name__),
            args=args,
            kwargs=kwargs,
        )

        entry = self.store.get(key)
        if entry is not None:
            expires_at, value = entry
            if not is_expired(expires_at):
                self.store.move_to_end(key=key)
                self.hits += 1
                return value
            del self.store[key]

        result = self.func(*args, **kwargs)
        self.misses += 1

        self.store[key] = (expiry(self.ttl), result)
        if self.maxsize is not None:
            while len(self.store) > self.maxsize:
                self.store.popitem(last=False)

        self._persist()

        return result


@flexwrap
class cache_df:  # noqa: N801
    """
    Decorate a DataFrame factory with filesystem-backed memoisation.

    Wraps a callable returning a pandas or polars DataFrame and
    persists each distinct result to its own file under
    ``cache_folder / func_name / <hash>.<suffix>``. Reads and writes
    go through :meth:`DataFile.from_path`, so any registered tabular
    file format (parquet, csv, feather, xlsx, and so on) backs the
    cache without a bespoke code path per format. Staleness is
    evaluated from the cache file's modification time rather than a
    stored sentinel, which keeps the on-disk layout portable across
    processes that did not share an in-memory state.

    Parameters
    ----------
    func
        The DataFrame-returning callable. Supplied automatically by
        :func:`flexwrap`.
    cache_folder
        Directory under which the per-function cache subfolder lives.
        Defaults to :data:`mayutils.data.CACHE_FOLDER`.
    suffix
        File extension identifying the cache format. May be supplied
        with or without the leading ``"."``. Defaults to
        ``"parquet"``.
    ttl
        Lifetime of each cached file. Staleness is computed from the
        file's modification time. ``None`` disables expiry.
    dataframe_backend
        DataFrame library used for reads and writes through
        :class:`DataFile`. Defaults to ``"pandas"``.

    Attributes
    ----------
    func
        The wrapped callable.
    cache_folder
        Root of the per-function cache subfolder.
    suffix
        Normalised file extension including the leading ``"."``.
    ttl
        Configured TTL.
    dataframe_backend
        Backend used for :class:`DataFile` read and write calls.
    hits
        Number of calls served from an existing cache file.
    misses
        Number of calls that executed the wrapped callable.

    See Also
    --------
    cache : Generic sibling decorator for non-DataFrame return
        types, backed by a single pickle file.
    functools.lru_cache : Standard-library in-memory LRU decorator
        without filesystem persistence.
    functools.cache : Unbounded standard-library analogue.
    diskcache : Third-party disk-backed cache library.
    mayutils.environment.logging : Sibling environment helper for
        structured logging.

    Notes
    -----
    Call sites may pass ``refresh=True`` as a trailing keyword to
    force a recomputation that also overwrites the cached file. The
    cache is always written on a miss, regardless of ``refresh``.

    Examples
    --------
    >>> import pandas as pd
    >>> from datetime import timedelta
    >>> from mayutils.environment.memoisation import cache_df
    >>> @cache_df(suffix="parquet", ttl=timedelta(hours=1))
    ... def build_frame() -> DataFrame:
    ...     return DataFrame({"value": [1, 2, 3]})
    >>> build_frame.misses
    0
    """

    def __init__(
        self,
        func: Callable[..., DataFrames] | None = None,
        /,
        *,
        cache_folder: Path | str = CACHE_FOLDER,
        suffix: str = "parquet",
        ttl: Duration | None = None,
        dataframe_backend: DataframeBackends = "pandas",
    ) -> None:
        """
        Bind the DataFrame-returning callable and configure the on-disk cache.

        Normalises ``suffix`` so that a leading dot is always present,
        coerces ``cache_folder`` into a :class:`pathlib.Path`, and
        resets the hit and miss counters to zero. Copies metadata
        from the wrapped callable via :func:`functools.update_wrapper`
        so introspection tools continue to report the original name
        and docstring. Raises immediately when ``func`` is missing
        because :func:`flexwrap` only omits it when the decorator
        was mis-applied.

        Parameters
        ----------
        func
            The DataFrame-returning callable whose outputs should be
            persisted. Populated automatically by :func:`flexwrap`.
        cache_folder
            Directory under which the per-function cache subfolder is
            created. Defaults to :data:`CACHE_FOLDER`.
        suffix
            File extension that selects the backing format; with or
            without a leading ``"."``. Defaults to ``"parquet"``.
        ttl
            Lifetime of each cached file, measured from its last
            write via ``mtime``. ``None`` disables expiry.
        dataframe_backend
            DataFrame library for reads and writes. Defaults to
            ``"pandas"``.

        Raises
        ------
        ValueError
            When ``func`` is ``None``, meaning the decorator was
            invoked without a target callable.

        See Also
        --------
        cache_df.__call__ : Entry point that reads from and writes
            to the directory initialised here.
        cache_df.cache_clear : Drops every cache file for this
            decorator.
        functools.lru_cache : Standard-library in-memory analogue.
        functools.cache : Unbounded standard-library analogue.
        diskcache : Alternative disk-backed cache library.
        mayutils.environment.logging : Sibling environment helper.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.environment.memoisation import cache_df
        >>> @cache_df
        ... def build_frame() -> DataFrame:
        ...     return DataFrame({"value": [1]})
        >>> build_frame.suffix
        '.parquet'
        """
        if func is None:
            msg = "No function provided"
            raise ValueError(msg)
        self.func: Callable[..., DataFrames] = func
        self.cache_folder = Path(cache_folder)
        self.suffix = suffix if suffix.startswith(".") else f".{suffix}"
        self.ttl = ttl
        self.dataframe_backend: DataframeBackends = dataframe_backend
        self.hits = 0
        self.misses = 0

        update_wrapper(wrapper=self, wrapped=func)

    @property
    def function_folder(
        self,
    ) -> Path:
        """
        Return the per-function cache subfolder path for this decorator.

        Joins :attr:`cache_folder` with the wrapped callable's
        ``__name__`` so every decorator gets an isolated namespace,
        making it safe to share a single root directory across many
        memoised functions. The folder itself is created lazily by
        :meth:`__call__` when a miss triggers a write, so merely
        reading the property has no filesystem side effects.

        Returns
        -------
            ``cache_folder / func.__name__``. Created on demand by
            :meth:`__call__` when a cache write is performed.

        See Also
        --------
        cache_df.get_path : Derives individual cache file paths
            inside this folder.
        cache_df.cache_clear : Deletes every file within this folder
            that matches the configured suffix.
        functools.lru_cache : Standard-library analogue without any
            filesystem namespace.
        functools.cache : Unbounded standard-library analogue.
        diskcache : Alternative disk-backed cache library.
        mayutils.environment.logging : Sibling environment helper.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.environment.memoisation import cache_df
        >>> @cache_df
        ... def build_frame() -> DataFrame:
        ...     return DataFrame({"value": [1]})
        >>> build_frame.function_folder.name
        'build_frame'
        """
        return self.cache_folder / getattr(self.func, "__name__", type(self.func).__name__)

    def get_path(
        self,
        *args: object,
        refresh: bool = False,
        **kwargs: object,
    ) -> Path:
        """
        Compute the cache file path for a given call signature.

        Hashes the positional and keyword arguments together with the
        wrapped callable's name via :func:`make_cache_key`, then
        appends the configured suffix so every distinct input maps
        deterministically to a unique file. Accepting ``refresh`` as
        a named argument lets callers forward ``**kwargs`` verbatim
        from :meth:`__call__` or :meth:`delete_cache` without having
        to strip it out first. The path itself is returned even when
        no file exists, so callers can use it for subsequent writes.

        Parameters
        ----------
        *args
            Positional arguments that identify this call; folded
            into the cache key alongside the wrapped callable's name.
        refresh
            Accepted for signature parity with :meth:`__call__` so
            that callers can pass ``refresh`` through from a wrapper
            call. Consumed here to keep it out of the cache-key
            kwargs; the value has no effect on the returned path.
        **kwargs
            Keyword arguments that identify this call.

        Returns
        -------
            ``cache_folder / func_name / <hash>.<suffix>`` at which
            the cached DataFrame for the given inputs lives or will
            be written.

        See Also
        --------
        cache_df.__call__ : Uses this helper to resolve the read and
            write targets on every invocation.
        cache_df.delete_cache : Uses this helper to locate the file
            to unlink.
        make_cache_key : Underlying hashing routine.
        functools.lru_cache : Standard-library analogue without a
            file-based key surface.
        functools.cache : Unbounded standard-library analogue.
        diskcache : Alternative disk-backed cache library.
        mayutils.environment.logging : Sibling environment helper.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.environment.memoisation import cache_df
        >>> @cache_df
        ... def build_frame(flag: bool = False) -> DataFrame:
        ...     return DataFrame({"flag": [flag]})
        >>> path = build_frame.get_path(flag=True)
        >>> path.suffix
        '.parquet'
        """
        _ = refresh
        key = make_cache_key(
            getattr(self.func, "__name__", type(self.func).__name__),
            args=args,
            kwargs=kwargs,
        )

        return self.function_folder / f"{key}{self.suffix}"

    def is_stale(
        self,
        path: Path,
        /,
    ) -> bool:
        """
        Check whether ``path``'s modification time exceeds the TTL.

        Thin wrapper around
        :func:`mayutils.environment.filesystem.is_file_stale` that
        passes :attr:`ttl` as the TTL bound. Kept as an instance
        method so callers can probe freshness ergonomically from a
        live ``cache_df`` instance without reaching for the
        underlying helper. The shared implementation is the
        authoritative staleness policy for every file-backed cache
        in the library, so new caching decorators can adopt the
        same semantics without reimplementing the mtime comparison.

        Parameters
        ----------
        path
            Location of a cache file whose freshness is being
            checked.

        Returns
        -------
            ``True`` when :attr:`ttl` is set and the time elapsed
            since ``path`` was last modified exceeds it; ``False``
            otherwise.

        See Also
        --------
        mayutils.environment.filesystem.is_file_stale : Shared
            implementation this method delegates to.
        cache_df.__call__ : Consumes this check before deciding to
            serve a cache file.
        is_expired : Sibling helper used by :class:`cache` for
            in-memory TTL comparisons.
        functools.lru_cache : Standard-library decorator without any
            TTL concept.
        functools.cache : Unbounded standard-library analogue.
        diskcache : Alternative disk-backed cache library with its
            own staleness rules.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from datetime import timedelta
        >>> import pandas as pd
        >>> from mayutils.environment.memoisation import cache_df
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...
        ...     @cache_df(cache_folder=tmp, ttl=timedelta(days=365))
        ...     def build_frame() -> pd.DataFrame:
        ...         return pd.DataFrame({"value": [1]})
        ...
        ...     fresh = Path(tmp) / "fresh.parquet"
        ...     _ = fresh.write_bytes(b"")
        ...     build_frame.is_stale(fresh)
        False
        """
        return is_file_stale(path, ttl=self.ttl)

    def cache_info(
        self,
    ) -> CacheInfo:
        """
        Report accumulated hit and miss statistics for this decorator.

        Mirrors the :meth:`functools.lru_cache.cache_info` surface so
        profiling code written against the standard library works
        unchanged. ``currsize`` is derived from the number of files
        currently present in :attr:`function_folder` with the
        configured suffix, so it reflects on-disk state rather than
        any in-memory bookkeeping. ``maxsize`` is always ``None``
        because file-backed caches are unbounded by design.

        Returns
        -------
            Named tuple ``(hits, misses, maxsize, currsize)``.
            ``maxsize`` is always ``None``, reflecting that
            file-backed caches are unbounded.

        See Also
        --------
        cache_df.cache_clear : Reset the store and counters.
        cache_df.__call__ : Mutates the counters observed here.
        functools.lru_cache : Standard-library decorator exposing the
            same ``cache_info`` API.
        functools.cache : Unbounded standard-library analogue.
        diskcache : Alternative disk-backed cache library with its
            own stats API.
        mayutils.environment.logging : Sibling environment helper.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.environment.memoisation import cache_df
        >>> @cache_df
        ... def build_frame() -> DataFrame:
        ...     return DataFrame({"value": [1]})
        >>> build_frame.cache_info().maxsize is None
        True
        """
        currsize = sum(1 for _ in self.function_folder.glob(pattern=f"*{self.suffix}")) if self.function_folder.is_dir() else 0

        return CacheInfo(
            hits=self.hits,
            misses=self.misses,
            maxsize=None,
            currsize=currsize,
        )

    def cache_clear(
        self,
    ) -> None:
        """
        Remove every cache file belonging to this decorator.

        Globs the per-function subfolder for files matching the
        configured suffix and unlinks each in turn, then resets the
        hit and miss counters to zero so subsequent stats reflect a
        fresh state. Only files under :attr:`function_folder` with
        the configured extension are deleted, so caches belonging to
        other decorators sharing :attr:`cache_folder` are left
        intact. The containing folder itself is kept so later writes
        do not pay the cost of recreating it.

        See Also
        --------
        cache_df.cache_info : Observe the counters this method
            resets.
        cache_df.delete_cache : Remove a single cache entry rather
            than the full folder.
        functools.lru_cache : Standard-library decorator exposing the
            same ``cache_clear`` API.
        functools.cache : Unbounded standard-library analogue.
        diskcache : Alternative disk-backed cache library.
        mayutils.environment.logging : Sibling environment helper.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.environment.memoisation import cache_df
        >>> @cache_df
        ... def build_frame() -> DataFrame:
        ...     return DataFrame({"value": [1]})
        >>> build_frame.cache_clear()
        >>> build_frame.cache_info().currsize
        0
        """
        if self.function_folder.is_dir():
            for file in self.function_folder.glob(pattern=f"*{self.suffix}"):
                file.unlink()
        self.hits = 0
        self.misses = 0

    def delete_cache(
        self,
        *args: object,
        refresh: bool = False,
        **kwargs: object,
    ) -> bool:
        """
        Remove the cache file for a specific call signature.

        Delegates to :meth:`get_path` to locate the cache file and
        then unlinks it, giving callers a surgical invalidation tool
        when only a subset of cached inputs needs regenerating.
        Accepting ``refresh`` as a named argument keeps the call
        signature compatible with :meth:`__call__` so wrappers can
        forward ``**kwargs`` verbatim. A return value is produced so
        callers can distinguish a no-op from a successful deletion.

        Parameters
        ----------
        *args
            Positional arguments identifying the cache entry.
        refresh
            Accepted for signature parity with :meth:`__call__`; the
            value has no effect on which entry is deleted.
        **kwargs
            Keyword arguments identifying the cache entry.

        Returns
        -------
            ``True`` when a cache file was located and unlinked;
            ``False`` when no cache file existed for the signature.

        See Also
        --------
        cache_df.cache_clear : Remove every cache file for this
            decorator in one step.
        cache_df.get_path : Underlying helper used to resolve the
            cache file path.
        functools.lru_cache : Standard-library decorator without a
            targeted invalidation API.
        functools.cache : Unbounded standard-library analogue.
        diskcache : Alternative disk-backed cache library with its
            own invalidation primitives.
        mayutils.environment.logging : Sibling environment helper.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.environment.memoisation import cache_df
        >>> @cache_df
        ... def build_frame(flag: bool = False) -> DataFrame:
        ...     return DataFrame({"flag": [flag]})
        >>> build_frame.delete_cache(flag=True)
        False
        """
        path = self.get_path(
            *args,
            refresh=refresh,
            **kwargs,
        )
        if path.is_file():
            path.unlink()
            return True

        return False

    def update(
        self,
        *args: object,
        **kwargs: object,
    ) -> DataFrames:
        """
        Force the cached entry for this signature to be rebuilt.

        Convenience wrapper around ``self(*args, refresh=True,
        **kwargs)`` that reads better at call sites where the intent
        is explicitly "overwrite the cache file". The wrapped
        callable is executed, its DataFrame is written through
        :class:`DataFile`, and the fresh value is returned. Useful
        for scheduled refreshers that want to update a cache without
        depending on TTL-driven staleness.

        Parameters
        ----------
        *args
            Positional arguments forwarded to the wrapped callable.
        **kwargs
            Keyword arguments forwarded to the wrapped callable.

        Returns
        -------
            The freshly computed DataFrame, also persisted to disk.

        See Also
        --------
        cache_df.__call__ : The underlying dispatch invoked with
            ``refresh=True``.
        cache_df.delete_cache : Remove a cache entry without
            regenerating it.
        functools.lru_cache : Standard-library decorator without a
            forced-refresh API.
        functools.cache : Unbounded standard-library analogue.
        diskcache : Alternative disk-backed cache library.
        mayutils.environment.logging : Sibling environment helper.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from mayutils.environment.memoisation import cache_df
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...
        ...     @cache_df(cache_folder=tmp)
        ...     def build_frame() -> pd.DataFrame:
        ...         return pd.DataFrame({"value": [1]})
        ...
        ...     frame = build_frame.update()
        ...     frame.shape
        (1, 1)
        """
        return self.__call__(
            *args,
            refresh=True,
            **kwargs,
        )

    def __call__(
        self,
        *args: object,
        refresh: bool = False,
        **kwargs: object,
    ) -> DataFrames:
        """
        Serve the wrapped callable's result from disk when possible.

        Resolves the cache path for the call signature via
        :meth:`get_path`, ensuring the :class:`DataFile` subclass for
        the configured suffix is registered through
        :func:`register_datafile`. A hit (file exists, not stale,
        ``refresh=False``) loads the DataFrame via
        :meth:`DataFile.from_path`, while a miss executes the wrapped
        callable, writes the result through the same handle, and
        returns it. The containing folder is created on demand so
        first-time writes succeed without manual mkdir calls.

        Parameters
        ----------
        *args
            Positional arguments forwarded to the wrapped callable
            and folded into the cache key.
        refresh
            When ``True``, ignore any existing cache file and force
            the wrapped callable to be re-executed. The freshly
            computed DataFrame is still written to disk.
        **kwargs
            Keyword arguments forwarded to the wrapped callable and
            folded into the cache key.

        Returns
        -------
            DataFrame for the given call signature, either loaded
            from the cache file or freshly computed and persisted.

        See Also
        --------
        cache_df.update : Shortcut for invoking this method with
            ``refresh=True``.
        cache_df.delete_cache : Drop a specific cache entry before
            re-invoking.
        functools.lru_cache : Standard-library analogue without
            filesystem persistence.
        functools.cache : Unbounded standard-library analogue.
        diskcache : Alternative disk-backed cache library.
        mayutils.environment.logging : Sibling environment helper.

        Examples
        --------
        >>> import tempfile
        >>> import pandas as pd
        >>> from mayutils.environment.memoisation import cache_df
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...
        ...     @cache_df(cache_folder=tmp)
        ...     def build_frame() -> pd.DataFrame:
        ...         return pd.DataFrame({"value": [1]})
        ...
        ...     frame = build_frame()
        ...     frame.shape
        (1, 1)
        """
        path = self.get_path(*args, **kwargs)
        register_datafile(self.suffix)

        if not refresh and path.is_file() and not self.is_stale(path):
            self.hits += 1
            return DataFile.from_path(
                path,
                backend=self.dataframe_backend,
            ).read()

        df = self.func(*args, **kwargs)
        self.misses += 1

        path.parent.mkdir(parents=True, exist_ok=True)
        DataFile.from_path(
            path,
            backend=self.dataframe_backend,
        ).write(df)

        return df


__all__ = [
    "cache",
    "cache_df",
    "expiry",
    "is_expired",
    "lru_cache",
    "make_cache_key",
    "register_datafile",
]
