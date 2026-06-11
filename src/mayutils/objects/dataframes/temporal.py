"""
Detect temporal string columns and dispatch their conversion by backend.

This is a leaf module holding ISO-style regex patterns, the
sample-based :func:`detect_temporal_kind` classifier, and the
:func:`parse_temporal_columns` dispatcher. Conversion implementations
live in the backend-specific modules
(:mod:`mayutils.objects.dataframes.pandas.dataframes` and
:mod:`mayutils.objects.dataframes.polars.dataframes`) and are imported
lazily by the dispatcher. This keeps the module import-light and
cycle-free: those backend modules import :func:`detect_temporal_kind`
from here at their own top level, so a reverse top-level import in this
file would create a circular dependency.

Each call to :func:`parse_temporal_columns` inspects up to
:data:`TEMPORAL_SAMPLE_SIZE` leading non-null string values per column.
Columns whose samples do not uniformly match any single temporal pattern
are left unchanged by the backend implementations.

See Also
--------
mayutils.objects.dataframes.backends : Backend token and DataFrames union.
mayutils.objects.dataframes.pandas.dataframes : Pandas conversion target.
mayutils.objects.dataframes.polars.dataframes : Polars conversion target.

Examples
--------
>>> from mayutils.objects.dataframes.temporal import detect_temporal_kind
>>> detect_temporal_kind(("2026-01-01",))
'date'
>>> detect_temporal_kind(("not-a-date",)) is None
True
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal, cast

from mayutils.objects.dataframes.backends import Backend, DataFrames

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pandas as pd
    import polars as pl


type DatetimeKind = Literal["datetime", "date", "time"]
"""Temporal flavour of a column; shared by
:mod:`mayutils.objects.dataframes.pandas.dataframes` (which re-exports it)
and its ``map_dtypes`` accessor method.

Each literal maps to a distinct parsing pathway in the backend
implementations:

- ``"datetime"`` parses full ISO datetimes to a datetime type.
- ``"date"`` parses calendar dates only.
- ``"time"`` parses bare clock times only.
"""

DATE_PATTERN: re.Pattern[str] = re.compile(pattern=r"^\d{4}-\d{2}-\d{2}$")
"""Matches ISO calendar dates (``YYYY-MM-DD``)."""

TIME_PATTERN: re.Pattern[str] = re.compile(pattern=r"^\d{1,2}:\d{2}(:\d{2}(\.\d{1,9})?)?$")
"""Matches bare clock times (``HH:MM[:SS[.fff]]``).

Hours may be one or two digits (``H`` or ``HH``) and range validity is
*not* enforced: strings such as ``"99:99"`` match here and only fail
downstream at conversion time, where the backends leave the column
unchanged.
"""

DATETIME_PATTERN: re.Pattern[str] = re.compile(
    pattern=r"^\d{4}-\d{2}-\d{2}[T ]\d{1,2}:\d{2}(:\d{2}(\.\d{1,9})?)?(Z|[+-]\d{2}:?\d{2})?$",
)
"""Matches ISO datetimes with optional fractional seconds and UTC offset.

The offset's numeric range is *not* validated: strings such as
``"2026-01-01T10:00+99:00"`` match here and only fail downstream at
conversion time, where the backends leave the column unchanged.
"""

TEMPORAL_SAMPLE_SIZE: int = 100
"""Number of leading non-null values inspected per column by the backends."""


def detect_temporal_kind(
    values: Sequence[object],
    /,
) -> DatetimeKind | None:
    """
    Classify a sequence of strings as a single temporal kind, or return ``None``.

    Checks the supplied values against each of the three ISO-style patterns in
    priority order: date, datetime, time. The first pattern that matches *all*
    values wins and its kind is returned. If no pattern matches all values
    uniformly, or if the sequence is empty, ``None`` is returned. The check
    short-circuits on the first non-matching value for each pattern.

    Parameters
    ----------
    values
        Sequence of candidate values to classify, typically a raw
        object-dtype sample. Any non-``str`` element (or an empty
        sequence) yields ``None`` without raising.

    Returns
    -------
        ``"date"`` when all values match ``YYYY-MM-DD``.
        ``"datetime"`` when all values match the ISO datetime pattern.
        ``"time"`` when all values match the bare clock pattern.
        ``None`` when no single kind matches every value or the sequence
        is empty.

    See Also
    --------
    DATE_PATTERN : Regex matched against values for the ``"date"`` kind.
    DATETIME_PATTERN : Regex matched for the ``"datetime"`` kind.
    TIME_PATTERN : Regex matched for the ``"time"`` kind.
    parse_temporal_columns : Dispatcher that calls this classifier per column.

    Examples
    --------
    >>> from mayutils.objects.dataframes.temporal import detect_temporal_kind
    >>> detect_temporal_kind(("2026-01-01", "2026-06-11"))
    'date'
    >>> detect_temporal_kind(("2026-01-01T10:00:00", "2026-06-11 23:59:59.123+00:00"))
    'datetime'
    >>> detect_temporal_kind(("09:30", "23:59:59.5"))
    'time'
    >>> detect_temporal_kind(("2026-01-01", "10:00:00")) is None
    True
    >>> detect_temporal_kind((20260101,)) is None
    True
    >>> detect_temporal_kind(()) is None
    True
    """
    strings = tuple(value for value in values if isinstance(value, str))
    if not strings or len(strings) != len(values):
        return None

    for kind, pattern in (
        ("date", DATE_PATTERN),
        ("datetime", DATETIME_PATTERN),
        ("time", TIME_PATTERN),
    ):
        if all(pattern.match(string=value) for value in strings):
            return cast("DatetimeKind", kind)

    return None


def parse_temporal_columns[DataFrameType: DataFrames](
    frame: DataFrameType,
    /,
    *,
    backend: Backend[DataFrameType] | None = None,
    sample_size: int = TEMPORAL_SAMPLE_SIZE,
) -> DataFrameType:
    """
    Convert temporal string columns in *frame* to native date/time types.

    Dispatches to the backend-specific implementation based on the
    ``backend.name`` string. Each backend inspects up to ``sample_size``
    leading non-null values per string column, calls
    :func:`detect_temporal_kind` on the sample, and coerces columns whose
    samples match uniformly. Columns that cannot be classified are left
    unchanged.

    When ``backend`` is ``None``, the backend is inferred from the runtime
    type of *frame* via :meth:`Backend.infer`.

    Parameters
    ----------
    frame
        Source DataFrame to process. The returned value is a new frame
        with temporal columns converted; the original is not mutated.
    backend
        Backend token controlling dispatch. ``None`` causes the backend
        to be inferred from *frame*.
    sample_size
        Maximum number of leading non-null values inspected per column.
        Defaults to :data:`TEMPORAL_SAMPLE_SIZE`.

    Returns
    -------
        DataFrame of the same type as *frame* with temporal string
        columns converted to their native types. Non-convertible columns
        are returned as-is.

    Raises
    ------
    ValueError
        Raised when the resolved ``backend.name`` is not ``"pandas"`` or
        ``"polars"``.

    See Also
    --------
    detect_temporal_kind : Column-level classifier called by each backend.
    mayutils.objects.dataframes.backends.Backend : Token used for dispatch.
    TEMPORAL_SAMPLE_SIZE : Default ``sample_size`` constant.

    Examples
    --------
    >>> from mayutils.objects.dataframes.backends import Backend
    >>> from mayutils.objects.dataframes.temporal import parse_temporal_columns
    >>> parse_temporal_columns(None, backend=Backend(type(None)))
    Traceback (most recent call last):
        ...
    ValueError: Unsupported backend: builtins
    """
    backend = backend if backend is not None else Backend.infer(frame)

    if backend.name == "pandas":
        from mayutils.objects.dataframes.pandas.dataframes import (  # noqa: PLC0415
            parse_temporal_columns as parse_temporal_columns_pandas,
        )

        return cast("DataFrameType", parse_temporal_columns_pandas(cast("pd.DataFrame", frame), sample_size=sample_size))
    if backend.name == "polars":
        from mayutils.objects.dataframes.polars.dataframes import (  # noqa: PLC0415
            parse_temporal_columns as parse_temporal_columns_polars,
        )

        return cast("DataFrameType", parse_temporal_columns_polars(cast("pl.DataFrame", frame), sample_size=sample_size))

    msg = f"Unsupported backend: {backend.name}"
    raise ValueError(msg)


__all__ = [
    "DATETIME_PATTERN",
    "DATE_PATTERN",
    "TEMPORAL_SAMPLE_SIZE",
    "TIME_PATTERN",
    "DatetimeKind",
    "detect_temporal_kind",
    "parse_temporal_columns",
]
