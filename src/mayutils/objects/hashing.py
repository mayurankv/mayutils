"""
Provide deterministic hashing utilities for JSON-serialisable inputs.

This module produces stable, reproducible digest strings from arbitrary
combinations of positional and keyword arguments. The digests are intended
for use as cache keys, where two invocations with the same logical inputs
must yield identical identifiers across processes and interpreter sessions.
Unlike Python's builtin :func:`hash`, which is perturbed by ``PYTHONHASHSEED``
for strings, bytes and other types from Python 3.3 onwards, SHA-256 digests
are deterministic regardless of interpreter version or environment. Datetime-
like values (``datetime``, ``pendulum.DateTime`` and
``mayutils.objects.datetime.DateTime``) are normalised to their ISO-8601
representation prior to hashing so they can participate in the keyspace
without triggering JSON encoder errors.

See Also
--------
hashlib : Standard library module used to compute the underlying SHA-256 digest.
pickle : Alternative (non-deterministic) approach unsuitable for cross-session keys.
mayutils.environment.memoisation : Consumer of these digests for on-disk caching.

Examples
--------
>>> from mayutils.objects.hashing import hash_inputs
>>> hash_inputs(1, name="alice") == hash_inputs(1, name="alice")
True
>>> len(hash_inputs("seed"))
64
"""

from __future__ import annotations

import json
from datetime import datetime
from hashlib import sha256
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pendulum import DateTime as PendulumDateTime

    from mayutils.objects.datetime import DateTime


def serialise(
    obj: DateTime | PendulumDateTime | datetime | object,
    /,
) -> str:
    """
    Convert datetime-like objects to ISO-8601 strings for JSON encoding.

    Acts as the ``default`` callback for :func:`json.dumps`, converting any
    of the supported datetime-like types into their ISO-8601 textual
    representation so they can be embedded inside a JSON payload used to
    compute a deterministic cache key. Producing an ISO-8601 string rather
    than a POSIX timestamp preserves timezone information and sub-second
    precision, which means two semantically identical datetimes in different
    offsets will collide only when they refer to the exact same wall-clock
    moment. The function deliberately raises :class:`TypeError` for
    unsupported inputs so that silent, non-reproducible coercions do not
    pollute the keyspace.

    Parameters
    ----------
    obj
        The value the JSON encoder could not natively serialise. Only
        instances of :class:`mayutils.objects.datetime.DateTime`,
        :class:`pendulum.DateTime` and :class:`datetime.datetime` are
        handled; any other input type triggers an error.

    Returns
    -------
        The ISO-8601 formatted timestamp produced by calling
        ``obj.isoformat()`` on the input datetime-like value.

    Raises
    ------
    TypeError
        Raised when ``obj`` is not an instance of one of the supported
        datetime-like types, indicating that the value cannot be
        serialised to JSON through this hook.

    See Also
    --------
    hash_inputs : Sibling helper that invokes this function via ``default``.
    json.dumps : Standard library encoder that dispatches to this hook.
    hashlib.sha256 : Digest algorithm fed by the JSON payload.
    mayutils.environment.memoisation : Downstream cache consumer.

    Examples
    --------
    >>> from datetime import datetime
    >>> serialise(datetime(2026, 4, 22, 12, 0, 0))
    '2026-04-22T12:00:00'
    >>> import json
    >>> json.dumps({"timestamp": datetime(2026, 4, 22)}, default=serialise)
    '{"timestamp": "2026-04-22T00:00:00"}'
    """
    if isinstance(obj, datetime):
        return obj.isoformat()

    msg = f"Type {type(obj)} not serialisable"
    raise TypeError(msg)


def hash_inputs(
    *args: object,
    **kwargs: object,
) -> str:
    """
    Compute a deterministic SHA-256 digest of the supplied arguments.

    Bundles the positional and keyword arguments into a single JSON document,
    encodes that document to UTF-8 bytes, and returns the hexadecimal SHA-256
    digest. Keyword argument keys are sorted prior to encoding so that two
    invocations differing only by kwarg ordering yield the same digest, making
    the result safe to use as a cache fingerprint. SHA-256 is preferred over
    the builtin :func:`hash` because the latter is randomised per interpreter
    session via ``PYTHONHASHSEED`` for strings, bytes and certain other types,
    whereas SHA-256 is stable across Python versions, processes and machines.
    Collision probability is cryptographically negligible (roughly ``2**-128``
    for a birthday attack), so digests can be relied upon as unique identifiers
    for any realistic cache population.

    Parameters
    ----------
    *args
        Positional values to incorporate into the digest. Each value must be
        JSON-serialisable directly or be one of the datetime types handled by
        :func:`serialise`.
    **kwargs
        Keyword values to incorporate into the digest. Keys are sorted
        alphabetically before the payload is encoded so that reordering of
        keyword arguments at the call site does not alter the resulting hash.

    Returns
    -------
        A 64-character lowercase hexadecimal string representing the SHA-256
        digest of the JSON-encoded ``{"args": args, "kwargs": kwargs}`` payload.

        A :class:`TypeError` may be propagated from :func:`json.dumps` (via
        :func:`serialise`) when any argument is neither JSON-serialisable nor
        a supported datetime-like type.

    See Also
    --------
    serialise : Sibling helper used as the JSON ``default`` callback.
    hashlib.sha256 : Underlying digest algorithm.
    json.dumps : JSON encoder used to produce the canonical payload.
    mayutils.environment.memoisation : Cache layer that keys entries on this digest.

    Examples
    --------
    Build a stable cache key from a function's arguments:

    >>> key = hash_inputs("report", year=2026, region="uk")
    >>> len(key)
    64
    >>> key == hash_inputs("report", region="uk", year=2026)
    True

    Fingerprint a datetime-bearing payload:

    >>> from datetime import datetime
    >>> digest = hash_inputs(asof=datetime(2026, 4, 22))
    >>> len(digest)
    64
    >>> digest == hash_inputs(asof=datetime(2026, 4, 22))
    True
    """
    return sha256(
        string=json.dumps(
            obj={
                "args": args,
                "kwargs": kwargs,
            },
            sort_keys=True,
            default=serialise,
        ).encode()
    ).hexdigest()
