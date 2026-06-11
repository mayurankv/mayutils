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

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BeforeValidator, PlainSerializer

from mayutils.core.extras import may_require_extras

if TYPE_CHECKING:
    from datetime import date, datetime

with may_require_extras():
    import numpy as np


def coerce_datetime64(
    v: np.datetime64 | datetime | date | str | int | bytes,
) -> np.datetime64:
    """
    Coerce any datetime-like value to ``np.datetime64[us]``.

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
    """
    if isinstance(v, np.datetime64):
        return v.astype("datetime64[us]")

    return np.datetime64(v, "us")


NpDatetime64 = Annotated[
    Any,
    BeforeValidator(coerce_datetime64),
    PlainSerializer(str, return_type=str),
]
