"""
Provide numpy ``datetime64`` coercion and a Pydantic-compatible annotated type.

Bridge Python-native temporal types (:class:`datetime.datetime`,
:class:`datetime.date`, ISO strings) and :class:`numpy.datetime64` at a
fixed microsecond resolution, plus :data:`NpDatetime64` — an
``Annotated`` alias that lets Pydantic models carry ``datetime64``
fields with validation on input and string serialisation on output.
Unlike most numpy-using modules in :mod:`mayutils`, numpy is imported
at module level here: the annotated alias requires the runtime
``np.datetime64`` type object when Pydantic builds a model class.

See Also
--------
numpy.datetime64 : Target dtype for all coercions in this module.
pydantic.BeforeValidator : Mechanism running the coercion on input.
mayutils.objects.datetime : Pendulum-backed temporal toolkit; this
    module covers only the numpy interop corner.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import BeforeValidator, GetPydanticSchema, PlainSerializer
from pydantic_core import core_schema

from mayutils.core.extras import may_require_extras

with may_require_extras():
    import numpy as np

if TYPE_CHECKING:
    from datetime import date, datetime


def coerce_datetime64(
    v: np.datetime64 | datetime | date | str | int | bytes,
    /,
) -> np.datetime64:
    """
    Coerce any datetime-like value to ``np.datetime64[us]``.

    Normalises heterogeneous temporal inputs — Python ``datetime``
    and ``date`` objects, ISO strings, integers, bytes, and already-typed
    ``datetime64`` values — to a single microsecond-resolution
    ``np.datetime64`` so downstream array operations work at a consistent
    unit.

    Parameters
    ----------
    v : np.datetime64 | datetime | date | str | int | bytes
        Value to coerce. Existing ``datetime64`` values are cast to
        microsecond resolution; everything else goes through the
        ``np.datetime64`` constructor.

    Returns
    -------
    np.datetime64
        Microsecond-resolution timestamp.

    See Also
    --------
    numpy.datetime64 : Target dtype for all coercions in this function.

    Notes
    -----
    Three non-obvious coercion behaviours worth knowing:

    * **None → NaT**: passing ``None`` does not raise; numpy silently
      produces ``NaT``.  A non-optional Pydantic field using
      :data:`NpDatetime64` will therefore accept ``None`` and store
      ``NaT`` without any validation error.
    * **int → microsecond epoch offset**: an integer input is interpreted
      by numpy as a number of microseconds since the Unix epoch
      (1970-01-01T00:00:00 UTC), matching the ``"us"`` unit passed to
      the constructor.
    * **higher-resolution datetime64 truncated**: a ``datetime64[ns]``
      (or finer) value is cast to ``datetime64[us]``, discarding
      sub-microsecond precision without warning.

    Examples
    --------
    >>> import numpy as np
    >>> from mayutils.objects.datetime.numpy import coerce_datetime64
    >>> coerce_datetime64("2026-01-15")
    np.datetime64('2026-01-15T00:00:00.000000')
    """
    if isinstance(v, np.datetime64):
        return v.astype("datetime64[us]")

    return np.datetime64(v, "us")


NpDatetime64 = Annotated[
    np.datetime64,
    GetPydanticSchema(lambda _source, _handler: core_schema.any_schema()),
    BeforeValidator(coerce_datetime64),
    PlainSerializer(str, return_type=str),
]
