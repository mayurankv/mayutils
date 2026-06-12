"""
Provide filesystem-metadata queries used by the caching layer.

This submodule hosts small helpers that inspect file metadata
(``stat`` fields, modification times) without loading the underlying
contents. The canonical entry point is :func:`is_file_stale`, which
compares a file's ``mtime`` against a TTL to decide whether a cached
artifact on disk is fresh enough to serve. Keeping the helper here —
rather than duplicating it across every cache decorator — means the
"how do we decide staleness" policy is defined in one place and
reused by both :class:`~mayutils.environment.memoisation.cache_df`
and :func:`~mayutils.data.read.read_query`.

See Also
--------
mayutils.environment.memoisation.cache_df : DataFrame cache that
    consults :func:`is_file_stale` before serving a hit.
mayutils.data.read.read_query : Query cache that consults
    :func:`is_file_stale` on its persistent tier.
mayutils.environment.filesystem.reading : Sibling submodule covering
    text-file reads on the paths inspected here.

Examples
--------
>>> import tempfile
>>> from datetime import timedelta
>>> from pathlib import Path
>>> from mayutils.environment.filesystem.metadata import is_file_stale
>>> with tempfile.TemporaryDirectory() as tmp:
...     p = Path(tmp) / "x.txt"
...     _ = p.write_text("hi", encoding="utf-8")
...     is_file_stale(p, ttl=timedelta(seconds=3600))
False
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from mayutils.objects.datetime import Duration


def is_file_stale(
    path: Path,
    /,
    *,
    ttl: Duration | None,
) -> bool:
    """
    Return whether ``path``'s mtime falls outside the supplied TTL.

    Freshness is derived from :attr:`pathlib.Path.stat.st_mtime`
    rather than an embedded sentinel, which lets file-backed caches
    survive process restarts without having to re-parse each file.
    Returns ``False`` unconditionally when no TTL is configured, so
    callers that opt out of expiry see the cache behave as
    "immortal" in that mode. The path must exist — callers are
    expected to check :meth:`pathlib.Path.is_file` before dispatch,
    since :meth:`pathlib.Path.stat` raises
    :class:`FileNotFoundError` on missing entries.

    Parameters
    ----------
    path
        File whose last-modified timestamp is being inspected.
    ttl
        Maximum allowed age. ``None`` disables the check, matching
        the "no expiry" contract on the caching decorators. Any
        :class:`datetime.timedelta` is also accepted since pendulum's
        :class:`~pendulum.Duration` subclasses it.

    Returns
    -------
        ``True`` when ``ttl`` is set and the file's age exceeds it;
        ``False`` otherwise.

    See Also
    --------
    mayutils.environment.memoisation.cache_df : Consumes this check
        before deciding to serve a cached DataFrame file.
    mayutils.data.read.read_query : Consumes this check on the
        persistent cache tier of the query reader.
    mayutils.environment.memoisation.is_expired : In-memory analogue
        that compares an absolute ``expires_at`` timestamp rather
        than a file mtime.
    pathlib.Path.stat : Underlying stdlib primitive used to read
        file modification times.

    Examples
    --------
    >>> import tempfile
    >>> from datetime import timedelta
    >>> from pathlib import Path
    >>> from mayutils.environment.filesystem import is_file_stale
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     p = Path(tmp) / "x.txt"
    ...     _ = p.write_text("hi", encoding="utf-8")
    ...     is_file_stale(p, ttl=timedelta(seconds=3600))
    False
    """
    if ttl is None:
        return False

    from mayutils.objects.datetime import DateTime

    mtime = DateTime.from_timestamp(path.stat().st_mtime)
    return (DateTime.now() - mtime) > ttl


__all__ = [
    "is_file_stale",
]
