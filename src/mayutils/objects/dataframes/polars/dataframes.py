"""
Provide helpers for working with Polars dataframes.

This module centralises Polars-specific transformation, inspection, and
conversion utilities shared across the wider :mod:`mayutils` codebase. It is
intended to cover both eager :class:`polars.DataFrame` and lazy
:class:`polars.LazyFrame` workflows, with functions favouring expression-based
APIs such as :func:`polars.col` so that schema inference and predicate pushdown
are preserved whenever possible. The first such helper is
:func:`parse_temporal_columns`, which converts temporal-looking string columns
of an eager frame to native ``Date``/``Datetime``/``Time`` dtypes. Future
helpers added to this file should continue to honour that eager-versus-lazy
distinction and keep signatures explicit about which variant they accept or
return.

See Also
--------
polars.DataFrame : Eager columnar dataframe used by the helpers in this module.
polars.LazyFrame : Lazy query graph that defers execution until collection.
polars.col : Expression builder referenced for schema-aware transformations.
mayutils.objects.dataframes.temporal : Shared detection logic and dispatcher.
mayutils.objects.dataframes : Parent namespace hosting sibling dataframe helpers.

Examples
--------
>>> import polars as pl
>>> from mayutils.objects.dataframes.polars.dataframes import (
...     parse_temporal_columns,
... )
>>> frame = pl.DataFrame({"d": ["2026-01-01", "2026-06-11"]})
>>> parse_temporal_columns(frame).schema["d"]
Date
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mayutils.core.extras import may_require_extras
from mayutils.objects.dataframes.temporal import TEMPORAL_SAMPLE_SIZE, detect_temporal_kind

if TYPE_CHECKING:
    import polars as pl


def parse_temporal_columns(
    frame: pl.DataFrame,
    /,
    *,
    sample_size: int = TEMPORAL_SAMPLE_SIZE,
) -> pl.DataFrame:
    """
    Convert temporal-looking string columns of *frame* to native types.

    Detection is sample-based: for each :class:`polars.String` column the
    first ``sample_size`` non-null values are classified with
    :func:`~mayutils.objects.dataframes.temporal.detect_temporal_kind`.
    ``"date"`` samples convert via :meth:`polars.Expr.str.to_date` to
    :class:`polars.Date`, ``"datetime"`` samples via
    :meth:`polars.Expr.str.to_datetime` to :class:`polars.Datetime`, and
    ``"time"`` samples via :meth:`polars.Expr.str.to_time` to
    :class:`polars.Time`. Conversion is strict (no null-coercion): a column
    whose full conversion fails — e.g. an unparseable value beyond the
    sample, or a UTC-offset datetime that polars refuses to infer without
    an explicit format — is left unchanged rather than nulled. The input
    frame is never mutated; ``with_columns`` returns a new frame at each
    successful conversion.

    Parameters
    ----------
    frame
        Source DataFrame to scan. It is returned as-is when no column
        converts; otherwise a new frame with converted columns is returned.
    sample_size
        Maximum number of leading non-null values inspected per column.
        Defaults to :data:`~mayutils.objects.dataframes.temporal.TEMPORAL_SAMPLE_SIZE`.

    Returns
    -------
        New DataFrame with temporal columns converted to native types, or
        the original *frame* object when nothing needed converting.

    See Also
    --------
    mayutils.objects.dataframes.temporal.detect_temporal_kind : Sample classifier.
    mayutils.objects.dataframes.temporal.parse_temporal_columns : Backend dispatcher.
    mayutils.objects.dataframes.pandas.dataframes.parse_temporal_columns :
        Pandas counterpart with the same sampling contract.

    Examples
    --------
    >>> import polars as pl
    >>> from mayutils.objects.dataframes.polars.dataframes import (
    ...     parse_temporal_columns,
    ... )
    >>> frame = pl.DataFrame({"d": ["2026-01-01", "2026-06-11"]})
    >>> parse_temporal_columns(frame).schema["d"]
    Date
    """
    with may_require_extras():
        import polars as pl

    for name, dtype in frame.schema.items():
        if dtype != pl.String:
            continue
        sample = frame.get_column(name=name).drop_nulls().head(n=sample_size)
        kind = detect_temporal_kind(sample.to_list())
        if kind is None:
            continue

        expression = {
            "date": pl.col(name=name).str.to_date(),
            "datetime": pl.col(name=name).str.to_datetime(),
            "time": pl.col(name=name).str.to_time(),
        }[kind]
        try:
            frame = frame.with_columns(expression)
        except (pl.exceptions.ComputeError, pl.exceptions.InvalidOperationError):
            continue

    return frame


__all__ = [
    "parse_temporal_columns",
]
