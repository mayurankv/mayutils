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
    from collections.abc import Callable

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


def hash_callable(
    call: Callable,  # pyright: ignore[reportMissingTypeArgument, reportUnknownParameterType]
    /,
) -> str:
    """
    Compute a SHA-256 fingerprint of a callable's code object and bound values.

    For plain :class:`types.FunctionType` instances the fingerprint covers the
    code object's bytecode, constants, names, variable counts, and closure
    structure, combined with the function's default argument values and the
    current cell contents of any closure. This guards against the common case
    where two lambdas or inner functions share identical bytecode but capture
    different values — without the bound-value payload such callables would
    produce the same digest and return stale cached results. For all other
    callables (``functools.partial``, callable objects, built-ins) the
    fingerprint falls back to a digest of the callable's ``repr``, which is
    stable for builtins and partials whose arguments are simple types but
    identity-based for arbitrary objects. In all cases the returned digest is a
    stable 64-character hexadecimal string suitable for use as a cache key.

    Parameters
    ----------
    call
        The callable whose identity should be fingerprinted. Must be either a
        plain Python function (:class:`types.FunctionType`) or any callable with
        a stable :func:`repr`. Closures over unmarshallable objects fall back to
        per-object identity hashing.

    Returns
    -------
        A 64-character lowercase hexadecimal SHA-256 digest uniquely identifying
        the callable's code and captured state for the lifetime of the
        interpreter session.

    See Also
    --------
    hash_inputs : Sibling helper producing digests from argument values rather than callables.
    hashlib.sha256 : Underlying digest algorithm.
    marshal : Used to serialise the code tuple and bound-value payload.
    mayutils.environment.memoisation : Cache layer that uses this digest to key callable-based entries.

    Examples
    --------
    >>> from mayutils.objects.hashing import hash_callable
    >>> def add(x, y):
    ...     return x + y
    >>> digest = hash_callable(add)
    >>> len(digest)
    64
    >>> digest == hash_callable(add)
    True
    """
    import hashlib
    import marshal
    from types import FunctionType

    if isinstance(call, FunctionType):
        code = call.__code__
        code_identity = (
            code.co_code,
            code.co_consts,
            code.co_names,
            code.co_varnames,
            code.co_freevars,
            code.co_argcount,
            code.co_posonlyargcount,
            code.co_kwonlyargcount,
        )

        # Values that change behaviour but live outside the bytecode: default arguments
        # and closure cell contents (e.g. the `col` captured by `lambda d: d[col]` when
        # built in a loop). Without these, two lambdas with identical bytecode but
        # different captures collide and return wrong cached results.
        bound_values = (
            call.__defaults__,
            call.__kwdefaults__,
            tuple(cell.cell_contents for cell in (call.__closure__ or ())),
        )

        try:
            bound_payload = marshal.dumps(bound_values)
        except (ValueError, TypeError):
            # Unmarshalable captures (arbitrary objects): fall back to per-object identity,
            # which is stable for the lifetime of the in-memory cache and collision-free
            # (at the cost of not deduplicating equal-but-distinct captured objects).
            bound_payload = repr([id(value) for value in bound_values]).encode()

        return hashlib.sha256(marshal.dumps(code_identity) + bound_payload).hexdigest()

    # functools.partial, callable instances, builtins, etc. have no __code__ to
    # fingerprint. Fall back to a digest of the repr: stable for builtins and
    # partials of simple args, identity-tinged otherwise — acceptable for an
    # in-process cache because it avoids collisions between distinct callables.
    return hashlib.sha256(repr(call).encode()).hexdigest()  # pyright: ignore[reportUnknownArgumentType]
