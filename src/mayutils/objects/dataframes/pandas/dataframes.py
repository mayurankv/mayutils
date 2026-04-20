"""Pandas DataFrame accessor utilities exposed through the ``df.utils`` namespace.

This module defines :class:`DataframeUtilsAccessor`, a lightweight wrapper that
augments a :class:`pandas.DataFrame` with convenience helpers for persisting to
disk across a range of file formats, rendering interactive tables, computing
deviations from a reference value, collapsing long-tailed index ranges,
applying diverging heatmaps, coercing columns to declared dtypes with
datetime-aware parsing, and anchoring values to a chosen interval mean. The
module also declares the :data:`DatetimeKind` and :data:`DtypeSpec` type
aliases that describe the accepted values for the dtype mapping machinery.
"""

from collections.abc import Callable, Hashable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from mayutils.core.extras import may_require_extras
from mayutils.objects.dataframes.pandas.stylers import Styler
from mayutils.objects.datetime import Date, DateTime, Interval

with may_require_extras():
    import numpy as np
    from great_tables import GT
    from itables import show
    from pandas import (
        DataFrame,
        ExcelWriter,
        Index,
        Series,
        to_datetime,
        to_numeric,
    )

type DatetimeKind = Literal["datetime", "date", "time"]
"""Enumerates the temporal parsing modes accepted by
:meth:`DataframeUtilsAccessor.map_dtypes`.

Each literal selects a different parsing pathway:

- ``"datetime"`` produces full ``datetime64`` values using the caller's
  ``datetime_format``.
- ``"date"`` parses with ``date_format`` and then strips to ``date`` objects.
- ``"time"`` parses with ``time_format`` and then strips to ``time`` objects.
"""

type DtypeSpec = DatetimeKind | Literal["numeric"] | str | type  # noqa: PYI051
"""Describes an acceptable target dtype for a single column in
:meth:`DataframeUtilsAccessor.map_dtypes`.

The following values are supported:

- A :data:`DatetimeKind` literal, which triggers ``pandas.to_datetime``
  based parsing with the caller-supplied format string.
- ``"numeric"``, which delegates to :func:`pandas.to_numeric` and coerces
  the column to the most appropriate numeric dtype.
- Any pandas-compatible dtype string (e.g. ``"Int64"``, ``"category"``) or
  Python ``type`` (e.g. ``float``), which is forwarded to
  :meth:`pandas.Series.astype`.
"""


class DataframeUtilsAccessor:
    """Accessor that attaches helper methods to a pandas DataFrame.

    Registered as ``DataFrame.utils`` elsewhere in :mod:`mayutils`, this class
    aggregates operations that would otherwise clutter a notebook session:
    multi-format persistence, interactive rendering, diverging heatmap
    styling, numeric/datetime dtype coercion, tail aggregation and interval
    grounding. The wrapped frame is held on :attr:`df` and all helpers either
    mutate it in place and return it for chaining or derive new artefacts
    without touching the original.

    Parameters
    ----------
    df : pandas.DataFrame
        Frame bound to the accessor. Subsequent helper calls read from and
        (where noted) mutate this instance directly.

    Attributes
    ----------
    df : pandas.DataFrame
        The underlying DataFrame the accessor operates on.
    """

    def __init__(
        self,
        df: DataFrame,
    ) -> None:
        """Bind the accessor instance to ``df``.

        Parameters
        ----------
        df : pandas.DataFrame
            Frame that every subsequent method call will operate on. Stored
            by reference; mutating methods therefore modify the caller's
            object directly.
        """
        self.df = df

    def save(
        self,
        path: Path | str,
        /,
        **kwargs: Any,  # noqa: ANN401
    ) -> Path:
        """Serialise the underlying DataFrame to ``path``, dispatching on suffix.

        The file suffix selects the persistence backend: image/document
        suffixes (``.png``, ``.jpeg``, ``.jpg``, ``.pdf``, ``.svg``, ``.eps``)
        render through :class:`Styler`; ``.parquet``, ``.csv`` and ``.xlsx``
        round-trip via the matching pandas writers (all of which retain the
        index); any other suffix is rejected.

        Parameters
        ----------
        path : pathlib.Path or str
            Destination on disk. Coerced to :class:`pathlib.Path` so the
            suffix-driven dispatch works regardless of the input type. The
            parent directory must already exist.
        **kwargs
            Additional keyword arguments forwarded unchanged to
            :meth:`Styler.save` when the suffix selects an image/document
            backend. Ignored for tabular writers.

        Returns
        -------
        pathlib.Path
            The resolved path that was written to, suitable for chaining into
            downstream logging or assertions.

        Raises
        ------
        NotImplementedError
            Raised when the suffix is ``.feather`` (currently disabled) or
            any other value not listed above, signalling an unsupported
            output format.
        """
        path = Path(path)

        if path.suffix in [".png", ".jpeg", ".jpg", ".pdf", ".svg", ".eps"]:
            default_kwargs = {}
            joint_kwargs = default_kwargs | kwargs  # pyright: ignore[reportUnknownVariableType]
            return self.styler.save(
                path,
                **joint_kwargs,  # pyright: ignore[reportUnknownArgumentType]
            )

        if path.suffix == ".parquet":
            default_kwargs = {
                "index": True,
            }
            joint_kwargs = default_kwargs | kwargs  # pyright: ignore[reportUnknownVariableType]
            self.df.to_parquet(  # pyright: ignore[reportCallIssue]
                path=path,
                **joint_kwargs,  # pyright: ignore[reportArgumentType]
            )

        elif path.suffix == ".feather":
            default_kwargs = {}
            joint_kwargs = default_kwargs | kwargs  # pyright: ignore[reportUnknownVariableType]
            msg = "Feather not implemented"
            raise NotImplementedError(msg)
            self.df.to_feather(
                path,
                **(default_kwargs | kwargs),
            )

        elif path.suffix == ".csv":
            default_kwargs = {
                "index": True,
            }
            joint_kwargs = default_kwargs | kwargs  # pyright: ignore[reportUnknownVariableType]
            self.df.to_csv(  # pyright: ignore[reportCallIssue]
                path_or_buf=path,
                **joint_kwargs,  # pyright: ignore[reportArgumentType]
            )

        elif path.suffix == ".xlsx":
            default_kwargs = {
                "index": True,
            }
            joint_kwargs = default_kwargs | kwargs  # pyright: ignore[reportUnknownVariableType]
            with ExcelWriter(path=path) as excel_writer:  # pyright: ignore[reportUnknownVariableType]
                self.df.to_excel(  # pyright: ignore[reportUnknownMemberType]
                    excel_writer=excel_writer,
                    **joint_kwargs,  # pyright: ignore[reportArgumentType]
                )
        else:
            msg = f"Format {path.suffix} is an unsupported format"
            raise NotImplementedError(msg)

        return path

    def interact(
        self,
        *,
        caption: str | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Render the DataFrame interactively through :func:`itables.show`.

        Wraps the bound frame in an ``itables`` DataTables widget so callers
        can sort, search and paginate the data inside a notebook cell without
        first converting it to HTML manually.

        Parameters
        ----------
        *args
            Positional arguments forwarded verbatim to :func:`itables.show`;
            see the ``itables`` documentation for the supported options
            (row limits, column definitions, etc.).
        **kwargs
            Keyword arguments forwarded verbatim to :func:`itables.show`,
            controlling DataTables configuration such as pagination, column
            widths and styling.

        Returns
        -------
        None
            The function is called purely for its side effect of rendering
            the interactive table in the active display context.
        """
        return show(
            df=self.df,
            caption=caption,
            **kwargs,
        )

    def max_abs(
        self,
        reference_value: float = 0,
        /,
        *,
        columns: Sequence[Hashable] | Index | None = None,
    ) -> float:
        """Compute the largest absolute gap between the data and a reference point.

        Converts the selected subset of the frame to ``float`` and returns
        ``max(|x - reference_value|)``, clipping the positive and negative
        extremes at zero first so purely one-sided distributions still yield
        a meaningful non-negative magnitude. The result is typically used to
        symmetrise diverging colour scales around ``reference_value``.

        Parameters
        ----------
        reference_value : float, default ``0``
            Anchor point from which deviations are measured. Changing this
            shifts which direction a value is considered "positive" or
            "negative" for the purpose of the comparison.
        columns : Sequence[Hashable] or pandas.Index or None, default ``None``
            Subset of column labels to consider. When ``None`` every column
            in the bound frame participates; otherwise only the selected
            columns contribute to the maximum.

        Returns
        -------
        float
            Non-negative magnitude of the furthest selected value from
            ``reference_value``, suitable for use as a symmetric colour-scale
            bound.

        Raises
        ------
        ValueError
            Raised when the maximum absolute deviation is exactly zero,
            i.e. every selected value equals ``reference_value`` and so no
            meaningful scale can be derived.
        """
        values = self.df if columns is None else self.df[columns]
        deviations = np.asarray(values - reference_value, dtype=float)
        min_neg: float = min(float(deviations.min()), 0.0)
        max_pos: float = max(float(deviations.max()), 0.0)
        max_abs = max(max_pos, -min_neg)
        if max_abs == 0:
            msg = f"All values are constant equal to {reference_value}"
            raise ValueError(msg)

        return max_abs

    def rename_index(
        self,
        index_name: str,
        /,
    ) -> DataFrame:
        """Set the bound frame's index name and return the frame for chaining.

        Mutates :attr:`df` in place by assigning ``index_name`` to
        ``df.index.name`` so downstream operations that rely on a labelled
        index (e.g. ``reset_index``, groupby output) receive the intended
        label.

        Parameters
        ----------
        index_name : str
            Label to assign to the index. Replaces any existing name.

        Returns
        -------
        pandas.DataFrame
            The bound DataFrame, returned to permit fluent chaining with
            other pandas operations.
        """
        self.df.index.name = index_name

        return self.df

    def cutoff(
        self,
        cutoff: int,
        /,
        *,
        aggregation: Callable[[DataFrame], Series] | None = lambda x: x.sum(),
    ) -> DataFrame:
        """Collapse rows with index greater than or equal to ``cutoff`` into a single bucket.

        Splits the frame on ``cutoff``, keeps the head as-is, reduces the
        tail with ``aggregation`` and re-appends it under the label
        ``f"{cutoff}+"``. The resulting index is cast to ``str`` and sorted
        numerically on the pre-``+`` prefix so the aggregated row always
        sits at the end. Passing ``aggregation=None`` omits the tail
        entirely, producing a hard truncation.

        Parameters
        ----------
        cutoff : int
            Inclusive boundary applied to the frame's index. Rows with
            ``index < cutoff`` are retained; rows with ``index >= cutoff``
            form the tail that is aggregated.
        aggregation : Callable[[pandas.DataFrame], pandas.Series] or None, default ``lambda x: x.sum()``
            Reduction that turns the tail DataFrame into a single Series
            stored under the ``"<cutoff>+"`` label. ``None`` skips the
            aggregation step entirely, returning only the head portion.

        Returns
        -------
        pandas.DataFrame
            Copy of the bound frame with its tail collapsed (or dropped).
            When aggregation is applied, the index is stringified and
            lexically ordered by the numeric prefix.
        """
        df_cut = self.df.loc[self.df.index < cutoff].copy()
        if aggregation is not None:
            df_cut.loc[f"{cutoff}+", :] = aggregation(self.df.loc[self.df.index >= cutoff])
            df_cut.index = df_cut.index.astype(dtype=str)
            df_cut = df_cut.sort_index(key=lambda x: x.str.split(pat="+").str[0].astype(dtype=int))

        return df_cut

    def change_map(
        self,
        reference_value: float = 0,
        /,
        *,
        scaling: float = 0.6,
        columns: Sequence[Hashable] | Index | None = None,
    ) -> Styler:
        """Build a diverging heatmap centred on ``reference_value``.

        Delegates to :meth:`Styler.change_map` after computing a symmetric
        bound via :meth:`max_abs`, so positive and negative deviations
        receive matching colour intensities. The returned styler keeps the
        bound frame unchanged; colours are a presentation-only overlay.

        Parameters
        ----------
        reference_value : float, default ``0``
            Neutral midpoint that receives no colour. Cells equal to this
            value are rendered white; cells above/below diverge toward the
            positive/negative palette extremes.
        scaling : float, default ``0.6``
            Peak opacity applied to the extreme cells. Values in ``(0, 1]``
            dial the contrast down or up — ``0.6`` leaves headroom so text
            on coloured cells remains readable.
        columns : Sequence[Hashable] or pandas.Index or None, default ``None``
            Restrict styling (and the symmetric-bound calculation) to these
            columns. ``None`` styles the whole frame.

        Returns
        -------
        Styler
            Styler wrapping the bound frame with the diverging colour map
            applied to the selected columns.
        """
        return self.styler.change_map(
            self.max_abs(
                reference_value,
                columns=columns,
            ),
            reference_value=reference_value,
            scaling=scaling,
            columns=columns,
        )

    @property
    def styler(
        self,
    ) -> Styler:
        """Fresh :class:`Styler` bound to the underlying frame.

        Each access constructs a new styler so callers can stage independent
        styling pipelines without leaking formatting state between them.

        Returns
        -------
        Styler
            Newly instantiated styler wrapping :attr:`df`; any existing
            styling on other stylers is unaffected.
        """
        return Styler(data=self.df)

    @property
    def gt(
        self,
    ) -> GT:
        """Fresh :class:`great_tables.GT` view of the bound frame.

        Provides direct access to the ``great_tables`` rendering pipeline for
        publication-grade tables. Each access builds a new ``GT`` so
        configuration applied to earlier accessors is not carried over.

        Returns
        -------
        great_tables.GT
            Newly instantiated ``GT`` wrapping :attr:`df`, ready for
            additional ``tab_*`` / ``fmt_*`` calls.
        """
        return GT(data=self.df)

    def map_dtypes(
        self,
        mapper: Mapping[Hashable, DtypeSpec],
        /,
        *,
        datetime_format: str = "%Y-%m-%d %H:%M:%S",
        date_format: str = "%Y-%m-%d %H:%M:%S",
        time_format: str = "%H:%M:%S",
    ) -> DataFrame:
        """Cast columns in place to the dtypes declared in ``mapper``.

        Iterates over ``mapper`` and rewrites each target column with the
        appropriate conversion: datetime parsing dispatches through a local
        helper that honours the three per-kind format strings; ``"numeric"``
        coerces with :func:`pandas.to_numeric`; everything else is forwarded
        to :meth:`pandas.Series.astype`. All conversions mutate :attr:`df`
        directly so the accessor can be chained with other in-place helpers.

        Parameters
        ----------
        mapper : Mapping[Hashable, DtypeSpec]
            Column-label to target-dtype mapping. The value controls how the
            column is rewritten (see :data:`DtypeSpec` for the full set of
            accepted specifications).
        datetime_format : str, default ``"%Y-%m-%d %H:%M:%S"``
            ``strptime``-style pattern used when a column is mapped to
            ``"datetime"``. Applied verbatim by :func:`pandas.to_datetime`.
        date_format : str, default ``"%Y-%m-%d %H:%M:%S"``
            ``strptime``-style pattern used when a column is mapped to
            ``"date"``; after parsing, the ``.dt.date`` accessor strips the
            time component.
        time_format : str, default ``"%H:%M:%S"``
            ``strptime``-style pattern used when a column is mapped to
            ``"time"``; after parsing, the ``.dt.time`` accessor strips the
            date component.

        Returns
        -------
        pandas.DataFrame
            The bound frame after every requested conversion has been
            applied, returned for chaining.

        Raises
        ------
        TypeError
            Raised when a column lookup, parse or cast fails for any reason
            — :class:`KeyError`, :class:`ValueError` and :class:`TypeError`
            from the underlying pandas call are all rewrapped into a single
            informative message identifying the offending column/dtype pair.
        """

        def convert_datetime(
            series: Series,
            datetime_type: DatetimeKind,
        ) -> Series:
            """Parse ``series`` into the temporal kind selected by ``datetime_type``.

            Routes to :func:`pandas.to_datetime` with the format string from
            the enclosing :meth:`map_dtypes` call that matches
            ``datetime_type``. For ``"date"`` and ``"time"`` the parsed
            result is further narrowed with ``dt.date`` / ``dt.time`` so the
            returned series contains pure date or time values rather than
            full timestamps.

            Parameters
            ----------
            series : pandas.Series
                Column of string-like values to parse. Values not matching
                the relevant format will propagate a :class:`ValueError`
                from pandas.
            datetime_type : Literal['datetime', 'date', 'time']
                Selects which format string from the enclosing scope is used
                and whether the post-parse accessor narrows the result.

            Returns
            -------
            pandas.Series
                Parsed series containing ``Timestamp``, ``date`` or ``time``
                values according to ``datetime_type``.

            Raises
            ------
            ValueError
                Raised when ``datetime_type`` is outside the supported
                literal set — acts as a defensive guard for callers that
                bypass the type hints.
            """
            if datetime_type == "datetime":
                return to_datetime(series, format=datetime_format)
            if datetime_type == "date":
                return to_datetime(series, format=date_format).dt.date
            if datetime_type == "time":
                return to_datetime(series, format=time_format).dt.time

            msg = f"Unknown datetime_type: {datetime_type}"
            raise ValueError(msg)

        for col, dtype in mapper.items():
            try:
                column: Series = self.df[col]
                if dtype in ("datetime", "date", "time"):
                    self.df[col] = convert_datetime(
                        series=column,
                        datetime_type=cast("DatetimeKind", dtype),  # pyright: ignore[reportUnnecessaryCast]
                    )
                elif dtype == "numeric":
                    self.df[col] = to_numeric(column)
                else:
                    self.df[col] = column.astype(cast("Any", dtype))

            except (
                KeyError,
                ValueError,
                TypeError,
            ) as err:
                msg = f"Error parsing dtype {dtype} for columns {col}"
                raise TypeError(msg) from err

        return self.df

    def slice_interval(
        self,
        interval: Interval[Date] | Interval[DateTime],
        /,
    ) -> DataFrame:
        """Restrict the frame to rows whose index falls within ``interval``.

        Dispatches on the index's inferred type so that callers can pass a
        single :class:`Interval` regardless of whether the underlying index
        stores :class:`datetime.datetime` or :class:`datetime.date` values:
        datetime indices receive the interval promoted to full datetimes;
        date indices receive it further narrowed back to dates. The
        returned frame is a ``.loc`` view into the bound DataFrame, not a
        copy.

        Parameters
        ----------
        interval : Interval
            Inclusive window whose endpoints bracket the rows to retain.
            Endpoint polarity is handled by
            :attr:`Interval.as_slice`, so inverted intervals are sliced
            in storage order.

        Returns
        -------
        pandas.DataFrame
            Subset of the bound frame whose index values lie inside
            ``interval``.

        Raises
        ------
        TypeError
            Raised when the frame's index is neither datetime- nor
            date-typed, which is required to translate the interval into
            a label-based slice.
        """
        if self.df.index.inferred_type == "datetime":
            return self.df.loc[interval.to_datetime_interval().as_slice]
        if self.df.index.inferred_type == "date":
            return self.df.loc[interval.to_datetime_interval().to_date_interval().as_slice]

        msg = "DataFrame index must be datetime or date type for interval slicing"
        raise TypeError(msg)

    def ground(
        self,
        interval: Interval[Date] | Interval[DateTime] | None,
        /,
    ) -> DataFrame:
        """Rebase the frame against the mean of values within ``interval``.

        Intended to shift a timeseries-like frame so that the mean over the
        supplied :class:`Interval` becomes the new zero (or reference)
        baseline, mirroring the behaviour of the Series-level ``ground``
        helper. The DataFrame implementation is currently a stub: a
        ``None`` interval returns the frame untouched while any concrete
        interval is explicitly rejected.

        Parameters
        ----------
        interval : Interval or None, default ``None``
            Inclusive window over which the anchoring mean would be
            computed. ``None`` is a no-op passthrough; a concrete interval
            is rejected until the feature lands.

        Returns
        -------
        pandas.DataFrame
            The bound frame returned unchanged when ``interval`` is
            ``None``.

        Raises
        ------
        NotImplementedError
            Raised whenever ``interval`` is not ``None``, signalling that
            DataFrame-level grounding has not yet been implemented.
        """
        if interval is None:
            return self.df

        msg = "Grounding not implemented for DataFrames yet"
        raise NotImplementedError(msg)
