"""Deterministic hashing utilities for JSON-serialisable inputs.

This module provides helpers for producing stable, reproducible digest
strings from arbitrary combinations of positional and keyword arguments.
The digests are intended for use as cache keys, where two invocations
with the same logical inputs must yield identical identifiers across
processes and interpreter sessions. Datetime-like values (``datetime``,
``pendulum.DateTime`` and ``mayutils.objects.datetime.DateTime``) are
normalised to their ISO-8601 representation prior to hashing so that
they can participate in the keyspace without triggering JSON encoder
errors.
"""

import json
from datetime import datetime
from hashlib import sha256
from typing import Any

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from pendulum import DateTime as PendulumDateTime

    from mayutils.objects.datetime import DateTime


def serialise(
    obj: DateTime | PendulumDateTime | datetime | object,
    /,
) -> str:
    """Convert datetime-like objects to ISO-8601 strings for JSON encoding.

    Acts as the ``default`` callback for :func:`json.dumps`, converting
    any of the supported datetime-like types into their ISO-8601 textual
    representation so that they can be embedded inside a JSON payload
    used to compute a deterministic cache key.

    Parameters
    ----------
    obj : DateTime or PendulumDateTime or datetime or object
        The value the JSON encoder could not natively serialise. Only
        instances of :class:`mayutils.objects.datetime.DateTime`,
        :class:`pendulum.DateTime` and :class:`datetime.datetime` are
        handled; any other input type triggers an error.

    Returns
    -------
    str
        The ISO-8601 formatted timestamp produced by calling
        ``obj.isoformat()`` on the input datetime-like value.

    Raises
    ------
    TypeError
        Raised when ``obj`` is not an instance of one of the supported
        datetime-like types, indicating that the value cannot be
        serialised to JSON through this hook.
    """
    if isinstance(obj, (DateTime, PendulumDateTime, datetime)):
        return obj.isoformat()

    msg = f"Type {type(obj)} not serialisable"
    raise TypeError(msg)


def hash_inputs(
    *args: Any,  # noqa: ANN401
    **kwargs: Any,  # noqa: ANN401
) -> str:
    """Compute a deterministic SHA-256 digest of the supplied arguments.

    Bundles the positional and keyword arguments into a single JSON
    document, encodes that document to UTF-8 bytes, and returns the
    hexadecimal SHA-256 digest. Keyword argument keys are sorted prior
    to encoding so that two invocations that differ only by kwarg
    ordering produce the same digest, making the result suitable as a
    cache key.

    Parameters
    ----------
    *args : Any
        Positional values to incorporate into the digest. Each value
        must be JSON-serialisable directly or be one of the datetime
        types handled by :func:`serialise`.
    **kwargs : Any
        Keyword values to incorporate into the digest. Keys are sorted
        alphabetically before the payload is encoded so that reordering
        of keyword arguments at the call site does not alter the
        resulting hash.

    Returns
    -------
    str
        A 64-character lowercase hexadecimal string representing the
        SHA-256 digest of the JSON-encoded ``{"args": args, "kwargs":
        kwargs}`` payload.

    Raises
    ------
    TypeError
        Propagated from :func:`json.dumps` (via :func:`serialise`) when
        any argument is neither JSON-serialisable nor a supported
        datetime-like type.
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
