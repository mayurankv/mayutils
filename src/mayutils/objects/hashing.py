"""Deterministic hashing of JSON-serialisable inputs via MD5 — used for cache keys."""

import json
from datetime import datetime
from hashlib import sha256
from typing import Any

from mayutils.core.extras import requires_extras

with requires_extras("datetime"):
    from pendulum import DateTime as PendulumDateTime

    from mayutils.objects.datetime import DateTime


def serialise(
    obj: DateTime | PendulumDateTime | datetime | object,
    /,
) -> str:
    """JSON ``default`` hook that serialises datetime-like values via :meth:`isoformat`.

    Passed to :func:`json.dumps` so that cache keys generated from
    function arguments can include pendulum or stdlib datetimes without
    tripping ``TypeError``.

    Parameters
    ----------
    obj : Any
        The value being serialised. Only datetime-like instances
        (``mayutils.objects.datetime.DateTime``, ``pendulum.DateTime``,
        ``datetime.datetime``) are handled.

    Returns
    -------
    str
        The ISO-8601 representation of ``obj``.

    Raises
    ------
    TypeError
        If ``obj`` is not a recognised datetime-like type.

    Examples
    --------
    >>> from datetime import datetime
    >>> serialise(datetime(2026, 1, 1))
    '2026-01-01T00:00:00'
    """
    if isinstance(obj, (DateTime, PendulumDateTime, datetime)):
        return obj.isoformat()

    msg = f"Type {type(obj)} not serialisable"
    raise TypeError(msg)


def hash_inputs(
    *args: Any,  # noqa: ANN401
    **kwargs: Any,  # noqa: ANN401
) -> str:
    """Return a SHA-256 hex digest of the JSON-encoded ``(args, kwargs)``.

    Produces a deterministic, 64-character hexadecimal string suitable
    for use as a cache-file name. Arguments must be JSON-serialisable
    (datetimes handled automatically by :func:`serialise`).

    Parameters
    ----------
    *args
        Positional arguments to include in the hash.
    **kwargs
        Keyword arguments to include in the hash. Keys are sorted
        before hashing so reordering does not change the digest.

    Returns
    -------
    str
        The 64-character hexadecimal SHA-256 digest.

    Raises
    ------
    TypeError
        If any argument isn't JSON-serialisable or a recognised
        datetime-like type (see :func:`serialise`).

    Examples
    --------
    >>> hash_inputs(1, 2)
    '1d7d98a02a1e2c74d1d61e4e1f7b25f3'  # doctest: +SKIP
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
