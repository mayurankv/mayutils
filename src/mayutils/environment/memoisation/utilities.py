"""
Provide cache-key generation and TTL helpers.

These pure utilities are used by memoisation decorators, the query
cache, and the clearing module. They have no filesystem side effects.

See Also
--------
mayutils.environment.memoisation : Parent package re-exporting these
    utilities.
mayutils.environment.memoisation.files : Filesystem-level cache helpers
    (DataFile registration, cache stem naming).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mayutils.objects.datetime import DateTime
from mayutils.objects.hashing import hash_inputs

if TYPE_CHECKING:
    from collections.abc import Mapping

    from mayutils.objects.datetime import Duration


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
    mayutils.objects.hashing.hash_inputs : Underlying hasher.
    is_expired : Companion TTL helper.
    expiry : Companion TTL helper.

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

    Treats ``None`` as an "immortal" marker so callers that do not
    configure a TTL bypass the comparison entirely.

    Parameters
    ----------
    expires_at
        Absolute expiry timestamp. ``None`` means "no expiry".

    Returns
    -------
        ``True`` when ``expires_at`` is non-``None`` and already in
        the past; ``False`` otherwise.

    See Also
    --------
    expiry : Companion helper that produces the ``expires_at``
        timestamp from a relative TTL.

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

    Adds *ttl* to :meth:`DateTime.now` to produce an absolute deadline,
    or passes ``None`` through unchanged when no TTL is configured.

    Parameters
    ----------
    ttl
        Relative lifetime. ``None`` disables expiry and propagates
        through as ``None``.

    Returns
    -------
        ``DateTime.now() + ttl`` when ``ttl`` is supplied; ``None``
        otherwise.

    See Also
    --------
    is_expired : Companion helper that compares ``expires_at`` against
        the current instant.

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


def format_ttl(
    ttl: Duration,
    /,
) -> str:
    """
    Format a TTL as a compact human-readable label.

    Converts *ttl* into the largest whole unit (days, hours, minutes,
    or seconds) and returns a prefixed string like ``ttl_6h``.

    Parameters
    ----------
    ttl
        Duration to format.

    Returns
    -------
    str
        Compact label like ``ttl_6h``, ``ttl_30m``, ``ttl_2d``.

    See Also
    --------
    expiry : Compute an absolute expiry from a relative TTL.
    is_expired : Check whether an absolute expiry has passed.

    Examples
    --------
    >>> from datetime import timedelta
    >>> from mayutils.environment.memoisation.utilities import format_ttl
    >>> format_ttl(timedelta(hours=6))
    'ttl_6h'
    >>> format_ttl(timedelta(minutes=30))
    'ttl_30m'
    """
    total_seconds = int(ttl.total_seconds())
    if total_seconds >= 86400:  # noqa: PLR2004
        return f"ttl_{total_seconds // 86400}d"
    if total_seconds >= 3600:  # noqa: PLR2004
        return f"ttl_{total_seconds // 3600}h"
    if total_seconds >= 60:  # noqa: PLR2004
        return f"ttl_{total_seconds // 60}m"
    return f"ttl_{total_seconds}s"


__all__ = [
    "expiry",
    "format_ttl",
    "is_expired",
    "make_cache_key",
]
