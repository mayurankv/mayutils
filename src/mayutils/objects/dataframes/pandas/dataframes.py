"""
Expose pandas DataFrame accessor utilities via the ``df.utils`` namespace.

This module defines :class:`DataframeUtilsAccessor`, a lightweight wrapper that
augments a :class:`pandas.DataFrame` with convenience helpers for persisting to
disk across a range of file formats, rendering interactive tables, computing
deviations from a reference value, collapsing long-tailed index ranges,
applying diverging heatmaps, coercing columns to declared dtypes with
datetime-aware parsing, and anchoring values to a chosen interval mean. The
module also declares the :data:`DatetimeKind` and :data:`DtypeSpec` type
aliases that describe the accepted values for the dtype mapping machinery.

See Also
--------
pandas.DataFrame : Underlying tabular structure exposed through the accessor.
mayutils.objects.dataframes.pandas.stylers : Companion module that supplies
    the :class:`Styler` wrapper used by this accessor.
mayutils.objects.dataframes.pandas.series : Sibling helpers that attach a
    matching accessor to :class:`pandas.Series`.
mayutils.objects.dataframes.pandas.index : Sibling helpers that operate on
    :class:`pandas.Index` objects.

Examples
--------
>>> import pandas as pd
>>> from mayutils.objects.dataframes.pandas.dataframes import (
...     DataframeUtilsAccessor,
... )
>>> df = pd.DataFrame({"a": [1, 2, 3]}, index=[0, 1, 2])
>>> accessor = DataframeUtilsAccessor(df=df)
>>> accessor.rename_index("row").index.name
'row'
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast, get_args

from mayutils.core.extras import may_require_extras
from mayutils.objects.dataframes.temporal import (
    TEMPORAL_SAMPLE_SIZE,
    DatetimeKind,
    detect_temporal_kind,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable, Mapping, Sequence

    from great_tables import GT
    from pandas import DataFrame, Index, Series
    from pandas._typing import DtypeObj

    from mayutils.objects.dataframes.pandas.stylers import Styler
    from mayutils.objects.datetime import Date, DateTime, Interval


type DtypeSpec = DatetimeKind | Literal["numeric"] | DtypeObj
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
    """
    Attach helper methods to a pandas DataFrame via the ``utils`` namespace.

    Registered as ``DataFrame.utils`` elsewhere in :mod:`mayutils`, this class
    aggregates operations that would otherwise clutter a notebook session:
    multi-format persistence, interactive rendering, diverging heatmap
    styling, numeric/datetime dtype coercion, tail aggregation and interval
    grounding. The wrapped frame is held on :attr:`df` and all helpers either
    mutate it in place and return it for chaining or derive new artefacts
    without touching the original. Because the frame is held by reference,
    copy-on-write semantics of the caller's pandas session are preserved and
    no implicit deep copy is taken.

    Parameters
    ----------
    df
        Frame bound to the accessor. Subsequent helper calls read from and
        (where noted) mutate this instance directly.

    Attributes
    ----------
    df
        The underlying DataFrame the accessor operates on.

    See Also
    --------
    pandas.DataFrame : Underlying tabular container wrapped by the accessor.
    mayutils.objects.dataframes.pandas.stylers.Styler : Styling wrapper used
        by :meth:`styler` and :meth:`change_map`.
    mayutils.objects.dataframes.pandas.series : Sibling accessor for
        :class:`pandas.Series`.

    Examples
    --------
    >>> import pandas as pd
    >>> from mayutils.objects.dataframes.pandas.dataframes import (
    ...     DataframeUtilsAccessor,
    ... )
    >>> df = pd.DataFrame({"x": [0.1, -0.2, 0.3]}, index=[0, 1, 2])
    >>> accessor = DataframeUtilsAccessor(df=df)
    >>> round(accessor.max_abs(0.0), 2)
    0.3
    """

    def __init__(
        self,
        df: DataFrame,
    ) -> None:
        """
        Bind the accessor instance to ``df``.

        The frame is stored as the :attr:`df` attribute without deep-copying,
        so any mutation performed by subsequent helpers propagates straight
        back to the caller's object. This keeps memory usage flat when the
        accessor is constructed in hot loops and preserves the copy-on-write
        semantics of the ambient pandas session. The accessor therefore
        behaves as a thin view on top of the supplied frame.

        Parameters
        ----------
        df
            Frame that every subsequent method call will operate on. Stored
            by reference; mutating methods therefore modify the caller's
            object directly.

        See Also
        --------
        pandas.DataFrame : Tabular container stored on :attr:`df`.
        DataframeUtilsAccessor.rename_index : Sibling helper that relabels
            the bound frame's index in place.
        DataframeUtilsAccessor.styler : Sibling helper that exposes the
            styling pipeline for the bound frame.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.pandas.dataframes import (
        ...     DataframeUtilsAccessor,
        ... )
        >>> frame = pd.DataFrame({"value": [10, 20, 30]})
        >>> accessor = DataframeUtilsAccessor(df=frame)
        >>> accessor.df is frame
        True
        """
        self.df = df

    def save(
        self,
        path: Path | str,
        /,
        **kwargs: Any,  # noqa: ANN401
    ) -> Path:
        """
        Serialise the underlying DataFrame to ``path``, dispatching on suffix.

        The file suffix selects the persistence backend: image/document
        suffixes (``.png``, ``.jpeg``, ``.jpg``, ``.pdf``, ``.svg``, ``.eps``)
        render through :class:`Styler`; ``.parquet``, ``.csv`` and ``.xlsx``
        round-trip via the matching pandas writers (all of which retain the
        index); any other suffix is rejected. Tabular backends pass
        ``index=True`` by default so the frame can be round-tripped without
        silently dropping the index, and ``**kwargs`` override that default
        when a caller wants to write a bare tabular representation.

        Parameters
        ----------
        path
            Destination on disk. Coerced to :class:`pathlib.Path` so the
            suffix-driven dispatch works regardless of the input type. The
            parent directory must already exist.
        **kwargs
            Additional keyword arguments forwarded unchanged to
            :meth:`Styler.save` when the suffix selects an image/document
            backend, or to the matching ``pandas.DataFrame.to_*`` writer for
            tabular backends.

        Returns
        -------
            The resolved path that was written to, suitable for chaining into
            downstream logging or assertions.

        Raises
        ------
        NotImplementedError
            Raised when the suffix is ``.feather`` (currently disabled) or
            any other value not listed above, signalling an unsupported
            output format.

        See Also
        --------
        pandas.DataFrame.to_parquet : Writer used for ``.parquet`` outputs.
        pandas.DataFrame.to_csv : Writer used for ``.csv`` outputs.
        pandas.DataFrame.to_excel : Writer used for ``.xlsx`` outputs.
        mayutils.objects.dataframes.pandas.stylers.Styler.save : Renderer
            used for image/document suffixes.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.pandas.dataframes import (
        ...     DataframeUtilsAccessor,
        ... )
        >>> df = pd.DataFrame({"a": [1, 2]})
        >>> accessor = DataframeUtilsAccessor(df=df)
        >>> with tempfile.TemporaryDirectory() as tmpdir:
        ...     out = accessor.save(Path(tmpdir) / "out.csv")
        ...     out.exists()
        True
        """
        path = Path(path)

        if path.suffix in [".png", ".jpeg", ".jpg", ".pdf", ".svg", ".eps"]:
            default_kwargs: dict[str, Any] = {}
            joint_kwargs = default_kwargs | kwargs
            return self.styler.save(
                path,
                **joint_kwargs,
            )

        if path.suffix == ".parquet":
            default_kwargs: dict[str, Any] = {
                "index": True,
            }
            joint_kwargs: dict[str, Any] = default_kwargs | kwargs
            self.df.to_parquet(
                path=path,
                **joint_kwargs,
            )

        elif path.suffix == ".feather":
            default_kwargs = {}
            joint_kwargs = default_kwargs | kwargs
            msg = "Feather not implemented"
            raise NotImplementedError(msg)
            self.df.to_feather(
                path,
                **joint_kwargs,
            )

        elif path.suffix == ".csv":
            default_kwargs = {
                "index": True,
            }
            joint_kwargs: dict[str, Any] = default_kwargs | kwargs
            self.df.to_csv(
                path_or_buf=path,
                **joint_kwargs,
            )

        elif path.suffix == ".xlsx":
            with may_require_extras():
                from pandas import ExcelWriter

            default_kwargs = {
                "index": True,
            }
            joint_kwargs: dict[str, Any] = default_kwargs | kwargs
            with ExcelWriter(path=path) as excel_writer:  # pyright: ignore[reportUnknownVariableType]
                self.df.to_excel(  # pyright: ignore[reportUnknownMemberType]
                    excel_writer=excel_writer,
                    **joint_kwargs,
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
        """
        Render the DataFrame interactively through :func:`itables.show`.

        Wraps the bound frame in an ``itables`` DataTables widget so callers
        can sort, search and paginate the data inside a notebook cell without
        first converting it to HTML manually. The frame is passed by
        reference, so the widget reflects the current state of :attr:`df`
        without allocating a copy; dtypes and the row/column index are
        preserved end-to-end.

        Parameters
        ----------
        caption
            Optional caption rendered above the DataTables widget. ``None``
            suppresses the caption row entirely.
        **kwargs
            Keyword arguments forwarded verbatim to :func:`itables.show`,
            controlling DataTables configuration such as pagination, column
            widths and styling.

        Returns
        -------
            The function is called purely for its side effect of rendering
            the interactive table in the active display context.

        See Also
        --------
        itables.show : Underlying DataTables renderer invoked by this helper.
        pandas.DataFrame.to_html : Static HTML alternative from pandas.
        mayutils.objects.dataframes.pandas.dataframes.DataframeUtilsAccessor.gt :
            Sibling helper returning a ``great_tables`` view instead.

        Examples
        --------
        >>> import contextlib
        >>> import io
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.pandas.dataframes import (
        ...     DataframeUtilsAccessor,
        ... )
        >>> df = pd.DataFrame({"x": [1, 2, 3]})
        >>> accessor = DataframeUtilsAccessor(df=df)
        >>> with contextlib.redirect_stdout(io.StringIO()):
        ...     result = accessor.interact(caption="Preview")
        >>> result is None
        True
        """
        with may_require_extras():
            from itables import show
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
        """
        Compute the largest absolute gap between the data and a reference point.

        Converts the selected subset of the frame to ``float`` and returns
        ``max(|x - reference_value|)``, clipping the positive and negative
        extremes at zero first so purely one-sided distributions still yield
        a meaningful non-negative magnitude. The result is typically used to
        symmetrise diverging colour scales around ``reference_value``. The
        intermediate array is materialised via :func:`numpy.asarray` which
        avoids an extra copy when the underlying frame is already backed by
        a contiguous float buffer.

        Parameters
        ----------
        reference_value
            Anchor point from which deviations are measured. Changing this
            shifts which direction a value is considered "positive" or
            "negative" for the purpose of the comparison.
        columns
            Subset of column labels to consider. When ``None`` every column
            in the bound frame participates; otherwise only the selected
            columns contribute to the maximum.

        Returns
        -------
            Non-negative magnitude of the furthest selected value from
            ``reference_value``, suitable for use as a symmetric colour-scale
            bound.

        Raises
        ------
        ValueError
            Raised when the maximum absolute deviation is exactly zero,
            i.e. every selected value equals ``reference_value`` and so no
            meaningful scale can be derived.

        See Also
        --------
        pandas.DataFrame : Tabular container whose values are summarised.
        numpy.abs : NumPy primitive underlying the magnitude calculation.
        mayutils.objects.dataframes.pandas.dataframes.DataframeUtilsAccessor.change_map :
            Consumer of this helper for symmetric diverging heatmaps.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.pandas.dataframes import (
        ...     DataframeUtilsAccessor,
        ... )
        >>> df = pd.DataFrame({"a": [1.0, -2.0, 3.0]})
        >>> accessor = DataframeUtilsAccessor(df=df)
        >>> accessor.max_abs(0.0)
        3.0
        """
        with may_require_extras():
            import numpy as np

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
        """
        Set the bound frame's index name and return the frame for chaining.

        Mutates :attr:`df` in place by assigning ``index_name`` to
        ``df.index.name`` so downstream operations that rely on a labelled
        index (e.g. ``reset_index``, groupby output) receive the intended
        label. Because pandas indices are immutable containers but carry a
        mutable ``name`` attribute, this update has zero memory cost and
        does not invalidate any existing references to the index object.

        Parameters
        ----------
        index_name
            Label to assign to the index. Replaces any existing name.

        Returns
        -------
            The bound DataFrame, returned to permit fluent chaining with
            other pandas operations.

        See Also
        --------
        pandas.Index.name : Attribute updated by this helper.
        pandas.DataFrame.rename_axis : Non-mutating pandas equivalent.
        mayutils.objects.dataframes.pandas.index : Sibling helpers for
            direct :class:`pandas.Index` manipulation.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.pandas.dataframes import (
        ...     DataframeUtilsAccessor,
        ... )
        >>> df = pd.DataFrame({"x": [1, 2]})
        >>> accessor = DataframeUtilsAccessor(df=df)
        >>> accessor.rename_index("row_id").index.name
        'row_id'
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
        """
        Collapse rows whose index meets ``cutoff`` into a single bucket row.

        Splits the frame on ``cutoff``, keeps the head as-is, reduces the
        tail with ``aggregation`` and re-appends it under the label
        ``f"{cutoff}+"``. The resulting index is cast to ``str`` and sorted
        numerically on the pre-``+`` prefix so the aggregated row always
        sits at the end. Passing ``aggregation=None`` omits the tail
        entirely, producing a hard truncation. The head slice is copied to
        avoid mutating the caller's frame when the aggregated row is
        written back via ``loc``.

        Parameters
        ----------
        cutoff
            Inclusive boundary applied to the frame's index. Rows with
            ``index < cutoff`` are retained; rows with ``index >= cutoff``
            form the tail that is aggregated.
        aggregation
            Reduction that turns the tail DataFrame into a single Series
            stored under the ``"<cutoff>+"`` label. ``None`` skips the
            aggregation step entirely, returning only the head portion.

        Returns
        -------
            Copy of the bound frame with its tail collapsed (or dropped).
            When aggregation is applied, the index is stringified and
            lexically ordered by the numeric prefix.

        See Also
        --------
        pandas.DataFrame.loc : Label-based indexer used for the head/tail
            split and the aggregated-row write-back.
        pandas.DataFrame.sum : Default tail reduction supplied by the
            fallback ``aggregation``.
        mayutils.objects.dataframes.pandas.dataframes.DataframeUtilsAccessor.slice_interval :
            Related helper that restricts the frame to a datetime window.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.pandas.dataframes import (
        ...     DataframeUtilsAccessor,
        ... )
        >>> df = pd.DataFrame({"n": [1, 2, 3, 4]}, index=[0, 1, 2, 3])
        >>> accessor = DataframeUtilsAccessor(df=df)
        >>> accessor.cutoff(2)["n"].tolist()
        [1.0, 2.0, 7.0]
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
        """
        Build a diverging heatmap centred on ``reference_value``.

        Delegates to :meth:`Styler.change_map` after computing a symmetric
        bound via :meth:`max_abs`, so positive and negative deviations
        receive matching colour intensities. The returned styler keeps the
        bound frame unchanged; colours are a presentation-only overlay that
        sits outside the numeric buffer so the source dtypes and index are
        preserved. Each call instantiates a fresh styler, avoiding any
        leakage of format state between rendering attempts.

        Parameters
        ----------
        reference_value
            Neutral midpoint that receives no colour. Cells equal to this
            value are rendered white; cells above/below diverge toward the
            positive/negative palette extremes.
        scaling
            Peak opacity applied to the extreme cells. Values in ``(0, 1]``
            dial the contrast down or up. ``0.6`` leaves headroom so text
            on coloured cells remains readable.
        columns
            Restrict styling (and the symmetric-bound calculation) to these
            columns. ``None`` styles the whole frame.

        Returns
        -------
            Styler wrapping the bound frame with the diverging colour map
            applied to the selected columns.

        See Also
        --------
        mayutils.objects.dataframes.pandas.stylers.Styler.change_map :
            Underlying renderer invoked with the symmetric bound.
        mayutils.objects.dataframes.pandas.dataframes.DataframeUtilsAccessor.max_abs :
            Helper that provides the symmetric bound consumed here.
        pandas.io.formats.style.Styler.background_gradient : Closest pandas
            equivalent for applying colour gradients to a frame.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.pandas.dataframes import (
        ...     DataframeUtilsAccessor,
        ... )
        >>> from mayutils.objects.dataframes.pandas.stylers import Styler
        >>> df = pd.DataFrame({"delta": [-0.4, 0.2, 0.5]})
        >>> accessor = DataframeUtilsAccessor(df=df)
        >>> styler = accessor.change_map(0.0)
        >>> isinstance(styler, Styler)
        True
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
        """
        Build a fresh :class:`Styler` bound to the underlying frame.

        Each access constructs a new styler so callers can stage independent
        styling pipelines without leaking formatting state between them. The
        styler references the frame rather than copying it, so column order
        and dtypes continue to reflect the live :attr:`df`. Constructing a
        throwaway styler per access is cheap because the wrapper only stores
        a reference alongside its own rule tables.

        Returns
        -------
            Newly instantiated styler wrapping :attr:`df`; any existing
            styling on other stylers is unaffected.

        See Also
        --------
        mayutils.objects.dataframes.pandas.stylers.Styler : Styler class
            returned by this property.
        pandas.io.formats.style.Styler : Native pandas styling API that the
            custom :class:`Styler` builds upon.
        mayutils.objects.dataframes.pandas.dataframes.DataframeUtilsAccessor.gt :
            Alternative renderer based on ``great_tables``.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.pandas.dataframes import (
        ...     DataframeUtilsAccessor,
        ... )
        >>> from mayutils.objects.dataframes.pandas.stylers import Styler
        >>> df = pd.DataFrame({"a": [1, 2]})
        >>> accessor = DataframeUtilsAccessor(df=df)
        >>> isinstance(accessor.styler, Styler)
        True
        """
        with may_require_extras():
            from mayutils.objects.dataframes.pandas.stylers import Styler

        return Styler(data=self.df)

    @property
    def gt(
        self,
    ) -> GT:
        """
        Build a fresh :class:`great_tables.GT` view of the bound frame.

        Provides direct access to the ``great_tables`` rendering pipeline for
        publication-grade tables. Each access builds a new ``GT`` so
        configuration applied to earlier accessors is not carried over. The
        underlying frame is referenced (not copied) which keeps the memory
        footprint small even when ``GT`` is constructed inside hot loops
        and preserves any column dtypes the caller has already coerced.

        Returns
        -------
            Newly instantiated ``GT`` wrapping :attr:`df`, ready for
            additional ``tab_*`` / ``fmt_*`` calls.

        See Also
        --------
        great_tables.GT : Rendering class returned by this property.
        mayutils.objects.dataframes.pandas.dataframes.DataframeUtilsAccessor.styler :
            Alternative renderer returning a custom :class:`Styler`.
        mayutils.objects.dataframes.pandas.dataframes.DataframeUtilsAccessor.interact :
            Interactive renderer based on ``itables``.

        Examples
        --------
        >>> import pandas as pd
        >>> from great_tables import GT
        >>> from mayutils.objects.dataframes.pandas.dataframes import (
        ...     DataframeUtilsAccessor,
        ... )
        >>> df = pd.DataFrame({"a": [1, 2]})
        >>> accessor = DataframeUtilsAccessor(df=df)
        >>> isinstance(accessor.gt, GT)
        True
        """
        with may_require_extras():
            from great_tables import GT

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
        """
        Cast columns in place to the dtypes declared in ``mapper``.

        Iterates over ``mapper`` and rewrites each target column with the
        appropriate conversion: datetime parsing dispatches through a local
        helper that honours the three per-kind format strings; ``"numeric"``
        coerces with :func:`pandas.to_numeric`; everything else is forwarded
        to :meth:`pandas.Series.astype`. All conversions mutate :attr:`df`
        directly so the accessor can be chained with other in-place helpers.
        Because each write replaces a single column at a time, the memory
        overhead is bounded by the size of the widest individual column.

        Parameters
        ----------
        mapper
            Column-label to target-dtype mapping. The value controls how the
            column is rewritten (see :data:`DtypeSpec` for the full set of
            accepted specifications).
        datetime_format
            ``strptime``-style pattern used when a column is mapped to
            ``"datetime"``. Applied verbatim by :func:`pandas.to_datetime`.
        date_format
            ``strptime``-style pattern used when a column is mapped to
            ``"date"``; after parsing, the ``.dt.date`` accessor strips the
            time component.
        time_format
            ``strptime``-style pattern used when a column is mapped to
            ``"time"``; after parsing, the ``.dt.time`` accessor strips the
            date component.

        Returns
        -------
            The bound frame after every requested conversion has been
            applied, returned for chaining.

        Raises
        ------
        TypeError
            Raised when a column lookup, parse or cast fails for any reason.
            :class:`KeyError`, :class:`ValueError` and :class:`TypeError`
            from the underlying pandas call are all rewrapped into a single
            informative message identifying the offending column/dtype pair.

        See Also
        --------
        pandas.to_datetime : Parser used for the datetime kinds.
        pandas.to_numeric : Parser used when ``dtype == "numeric"``.
        pandas.Series.astype : Fallback cast used for generic dtype specs.
        mayutils.objects.dataframes.pandas.series : Sibling accessor with
            equivalent column-level helpers for :class:`pandas.Series`.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.pandas.dataframes import (
        ...     DataframeUtilsAccessor,
        ... )
        >>> df = pd.DataFrame(
        ...     {"n": ["1", "2"], "f": ["1.5", "2.5"]},
        ... )
        >>> accessor = DataframeUtilsAccessor(df=df)
        >>> _ = accessor.map_dtypes(
        ...     {"n": "numeric", "f": float},
        ... )
        >>> accessor.df["n"].tolist()
        [1, 2]
        >>> accessor.df["f"].tolist()
        [1.5, 2.5]
        """
        with may_require_extras():
            from pandas import to_numeric

        def convert_datetime(
            series: Series,
            datetime_type: DatetimeKind,
        ) -> Series:
            """
            Parse ``series`` into the temporal kind selected by ``datetime_type``.

            Routes to :func:`pandas.to_datetime` with the format string from
            the enclosing :meth:`map_dtypes` call that matches
            ``datetime_type``. For ``"date"`` and ``"time"`` the parsed
            result is further narrowed with ``dt.date`` / ``dt.time`` so the
            returned series contains pure date or time values rather than
            full timestamps. This closure captures the three format strings
            from :meth:`map_dtypes` so dispatch cost stays ``O(1)`` per
            column regardless of how large ``series`` is.

            Parameters
            ----------
            series
                Column of string-like values to parse. Values not matching
                the relevant format will propagate a :class:`ValueError`
                from pandas.
            datetime_type
                Selects which format string from the enclosing scope is used
                and whether the post-parse accessor narrows the result.

            Returns
            -------
                Parsed series containing ``Timestamp``, ``date`` or ``time``
                values according to ``datetime_type``.

            Raises
            ------
            ValueError
                Raised when ``datetime_type`` is outside the supported
                literal set. Acts as a defensive guard for callers that
                bypass the type hints.

            See Also
            --------
            pandas.to_datetime : Underlying parser invoked by this helper.
            pandas.Series.dt : Datetime accessor used to narrow results to
                ``date`` or ``time``.
            mayutils.objects.dataframes.pandas.series : Sibling accessor
                offering equivalent datetime helpers at series level.

            Examples
            --------
            >>> import pandas as pd
            >>> from mayutils.objects.dataframes.pandas.dataframes import (
            ...     DataframeUtilsAccessor,
            ... )
            >>> df = pd.DataFrame({"d": ["2024-01-01", "2024-01-02"]})
            >>> accessor = DataframeUtilsAccessor(df=df)
            >>> _ = accessor.map_dtypes(
            ...     {"d": "date"},
            ...     date_format="%Y-%m-%d",
            ... )
            >>> [str(v) for v in accessor.df["d"].tolist()]
            ['2024-01-01', '2024-01-02']
            """
            with may_require_extras():
                from pandas import to_datetime

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
                if dtype in get_args(tp=DatetimeKind.__value__):
                    self.df[col] = convert_datetime(
                        series=column,
                        datetime_type=cast("DatetimeKind", dtype),
                    )
                elif dtype == "numeric":
                    self.df[col] = to_numeric(column)
                else:
                    self.df[col] = column.astype(cast("DtypeObj", dtype))

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
        """
        Restrict the frame to rows whose index falls within ``interval``.

        Dispatches on the index's inferred type so that callers can pass a
        single :class:`Interval` regardless of whether the underlying index
        stores :class:`datetime.datetime` or :class:`datetime.date` values:
        datetime indices receive the interval promoted to full datetimes;
        date indices receive it further narrowed back to dates. The
        returned frame is a ``.loc`` view into the bound DataFrame, not a
        copy, so mutating it may propagate back to :attr:`df` under
        pandas's copy-on-write settings.

        Parameters
        ----------
        interval
            Inclusive window whose endpoints bracket the rows to retain.
            Endpoint polarity is handled by
            :attr:`Interval.as_slice`, so inverted intervals are sliced
            in storage order.

        Returns
        -------
            Subset of the bound frame whose index values lie inside
            ``interval``.

        Raises
        ------
        TypeError
            Raised when the frame's index is neither datetime- nor
            date-typed, which is required to translate the interval into
            a label-based slice.

        See Also
        --------
        pandas.DataFrame.loc : Indexer used to translate interval endpoints
            into a slice operation.
        mayutils.objects.datetime.Interval : Window type accepted by this
            helper.
        mayutils.objects.dataframes.pandas.dataframes.DataframeUtilsAccessor.cutoff :
            Related helper that collapses tail rows rather than slicing
            by interval.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.datetime import Date, Interval
        >>> from mayutils.objects.dataframes.pandas.dataframes import (
        ...     DataframeUtilsAccessor,
        ... )
        >>> df = pd.DataFrame(
        ...     {"v": [1, 2, 3]},
        ...     index=pd.Index([Date(2024, 1, i) for i in (1, 2, 3)]),
        ... )
        >>> accessor = DataframeUtilsAccessor(df=df)
        >>> window = Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 2))
        >>> sliced = accessor.slice_interval(window)
        >>> sliced["v"].tolist()
        [1, 2]
        """
        if self.df.index.inferred_type in ("datetime", "datetime64"):
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
        """
        Rebase the frame against the mean of values within ``interval``.

        Intended to shift a timeseries-like frame so that the mean over the
        supplied :class:`Interval` becomes the new zero (or reference)
        baseline, mirroring the behaviour of the Series-level ``ground``
        helper. The DataFrame implementation is currently a stub: a
        ``None`` interval returns the frame untouched while any concrete
        interval is explicitly rejected. When eventually implemented the
        method will not allocate a copy; instead it will write in place
        once the anchoring mean has been computed across the slice.

        Parameters
        ----------
        interval
            Inclusive window over which the anchoring mean would be
            computed. ``None`` is a no-op passthrough; a concrete interval
            is rejected until the feature lands.

        Returns
        -------
            The bound frame returned unchanged when ``interval`` is
            ``None``.

        Raises
        ------
        NotImplementedError
            Raised whenever ``interval`` is not ``None``, signalling that
            DataFrame-level grounding has not yet been implemented.

        See Also
        --------
        mayutils.objects.dataframes.pandas.series : Sibling accessor
            providing the implemented series-level grounding helper.
        mayutils.objects.datetime.Interval : Window type that will be
            consumed once DataFrame grounding is implemented.
        mayutils.objects.dataframes.pandas.dataframes.DataframeUtilsAccessor.slice_interval :
            Related helper that already restricts the frame to an
            interval.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.pandas.dataframes import (
        ...     DataframeUtilsAccessor,
        ... )
        >>> df = pd.DataFrame({"v": [1.0, 2.0, 3.0]})
        >>> accessor = DataframeUtilsAccessor(df=df)
        >>> accessor.ground(None) is df
        True
        """
        if interval is None:
            return self.df

        msg = "Grounding not implemented for DataFrames yet"
        raise NotImplementedError(msg)


def parse_temporal_columns(
    frame: DataFrame,
    /,
    *,
    sample_size: int = TEMPORAL_SAMPLE_SIZE,
) -> DataFrame:
    """
    Convert temporal-looking object columns of *frame* to native types.

    Detection is sample-based: for each ``object`` or string-dtype column
    the first ``sample_size`` non-null values are classified with
    :func:`~mayutils.objects.dataframes.temporal.detect_temporal_kind`.
    Both ``"date"`` and ``"datetime"`` samples convert to ``datetime64[ns]``
    (or ``datetime64[ns, tz]`` when offsets are present) via
    ``to_datetime(..., format="ISO8601")``, deliberately diverging from
    :meth:`DataframeUtilsAccessor.map_dtypes`'s ``"date"`` mode, which
    narrows to ``date`` objects — ``map_dtypes`` honours an explicit caller
    request, whereas auto-parsing restores the natural pandas dtype.
    ``"time"`` samples become object columns of :class:`datetime.time` via
    ``to_datetime(..., format="mixed").dt.time``. Object columns holding
    :class:`datetime.date` instances (the shape Snowflake returns for
    ``DATE`` columns) also convert to ``datetime64[ns]``. A column whose
    full conversion fails — e.g. an unparseable value beyond the sample —
    is left unchanged rather than nulled, and the input frame is never
    mutated: converted columns are written into a copy.

    Parameters
    ----------
    frame
        Source DataFrame to scan. It is returned as-is when no column
        converts; otherwise a copy with converted columns is returned.
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
    DataframeUtilsAccessor.map_dtypes : Explicit per-column dtype coercion.

    Examples
    --------
    >>> import pandas as pd
    >>> from mayutils.objects.dataframes.pandas.dataframes import (
    ...     parse_temporal_columns,
    ... )
    >>> frame = pd.DataFrame({"d": ["2026-01-01", "2026-06-11"]})
    >>> parse_temporal_columns(frame)["d"].dtype
    dtype('<M8[ns]')
    """
    with may_require_extras():
        from pandas import StringDtype

    replacements: dict[int, Series] = {}
    for position in range(frame.shape[1]):
        series = frame.iloc[:, position]
        if not (series.dtype == object or isinstance(series.dtype, StringDtype)):
            continue
        sample = series.dropna().head(n=sample_size)
        if sample.empty:
            continue

        try:
            with may_require_extras():
                from pandas import to_datetime

            if all(isinstance(value, date) and not isinstance(value, datetime) for value in sample):
                replacements[position] = to_datetime(series)
                continue

            kind = detect_temporal_kind(tuple(sample))
            if kind in {"date", "datetime"}:
                replacements[position] = to_datetime(series, format="ISO8601")
            elif kind == "time":
                replacements[position] = to_datetime(series, format="mixed").dt.time
        except (ValueError, TypeError):
            continue

    if not replacements:
        return frame

    converted = frame.copy()
    for position, series in replacements.items():
        converted.isetitem(position, series.to_numpy())

    return converted


__all__ = [
    "DataframeUtilsAccessor",
    "DatetimeKind",
    "DtypeSpec",
    "parse_temporal_columns",
]
