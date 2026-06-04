"""
Provide a ``pandas`` Series accessor registered under ``series.utils``.

This module defines :class:`SeriesUtilsAccessor`, the one-dimensional
counterpart to the DataFrame accessor provided elsewhere in
``mayutils.objects.dataframes.pandas``. It collects Series-level helpers
that are useful when working with time-indexed numeric data, such as
anchoring a Series to its mean over a user-supplied interval so that
multiple Series can be compared on a common base. The ``pandas``
dependency is imported lazily through :func:`may_require_extras` so that
importing this module does not require the full optional dependency set
to be installed.

See Also
--------
pandas.Series : Underlying one-dimensional labelled array backing the accessor.
pandas.DataFrame : Two-dimensional counterpart whose utilities live alongside this module.
mayutils.objects.datetime.Interval : Endpoint-polarity-aware window used for slicing.

Examples
--------
>>> import pandas as pd
>>> from mayutils.objects.dataframes.pandas.series import SeriesUtilsAccessor
>>> series = pd.Series(
...     [1.0, 2.0, 3.0],
...     index=pd.date_range("2024-01-01", periods=3, freq="D"),
... )
>>> accessor = SeriesUtilsAccessor(series=series)
>>> accessor.series.shape
(3,)
"""

from pathlib import Path
from typing import NoReturn

from mayutils.core.extras import may_require_extras
from mayutils.objects.datetime import Date, DateTime, Interval

with may_require_extras():
    from pandas import Series


class SeriesUtilsAccessor:
    """
    Accessor exposing Series-level helpers under ``series.utils``.

    The accessor stores a reference to the wrapped :class:`pandas.Series`
    and exposes methods that operate on a single one-dimensional array of
    values, complementing the DataFrame accessor for workflows where
    only a column-like object is being manipulated. Index alignment is
    inherited directly from pandas semantics, so no additional dtype
    coercion is performed beyond what the underlying Series provides.
    The helpers are deliberately lightweight and stateless.

    Parameters
    ----------
    series
        The underlying one-dimensional data container whose values and
        index are used by every method on the accessor.

    See Also
    --------
    pandas.Series : Backing one-dimensional labelled array.
    pandas.Series.mean : Aggregation used to compute the grounding reference.
    pandas.Series.div : Elementwise division used by :meth:`ground`.
    mayutils.objects.datetime.Interval : Window type consumed by time-based helpers.

    Examples
    --------
    >>> import pandas as pd
    >>> from mayutils.objects.dataframes.pandas.series import SeriesUtilsAccessor
    >>> series = pd.Series(
    ...     [10.0, 20.0, 30.0],
    ...     index=pd.date_range("2024-01-01", periods=3, freq="D"),
    ... )
    >>> accessor = SeriesUtilsAccessor(series=series)
    >>> float(accessor.series.mean())
    20.0
    """

    def __init__(
        self,
        series: Series,
    ) -> None:
        """
        Store the target Series on the accessor instance.

        The constructor simply binds the provided Series to an attribute
        so subsequent helper calls can read from and transform it. No
        copying, validation, or dtype coercion is performed here, which
        keeps the accessor lightweight and means downstream mutations of
        ``series`` will be visible through the accessor as well. NA
        handling and index alignment follow pandas defaults for every
        method invoked later on the instance.

        Parameters
        ----------
        series
            The one-dimensional data container that the accessor will
            read from and transform when its methods are invoked.

        See Also
        --------
        pandas.Series : Input type accepted by this constructor.
        SeriesUtilsAccessor.slice_interval : Time-window restriction helper.
        SeriesUtilsAccessor.ground : Mean-based rescaling helper.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.pandas.series import SeriesUtilsAccessor
        >>> series = pd.Series([1.0, 2.0, 3.0])
        >>> accessor = SeriesUtilsAccessor(series=series)
        >>> float(accessor.series.iloc[0])
        1.0
        """
        self.series = series

    def save(
        self,
        path: Path | str,
    ) -> NoReturn:
        """
        Persist the wrapped Series to a file on disk.

        This helper is a placeholder that mirrors the signature of the
        DataFrame accessor's ``save`` method. No serialisation is
        currently performed because Series persistence would duplicate
        logic already available on the DataFrame accessor. Callers
        needing to persist a Series should promote it to a
        single-column DataFrame and dispatch through that accessor
        instead. The method unconditionally raises to surface the
        missing functionality at call time rather than silently doing
        nothing.

        Parameters
        ----------
        path
            Filesystem location at which the Series would be written once
            serialisation support is implemented for one-dimensional
            inputs.

        Raises
        ------
        NotImplementedError
            Always raised; persistence for Series is not yet available,
            and callers should convert the Series to a DataFrame and use
            the DataFrame accessor's ``save`` method instead.

        See Also
        --------
        pandas.Series.to_csv : Alternative pandas-native persistence path.
        pandas.Series.to_frame : Conversion to a DataFrame for reuse of the DataFrame accessor.
        pandas.DataFrame.to_parquet : Parquet serialisation available via the DataFrame accessor.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.pandas.series import SeriesUtilsAccessor
        >>> series = pd.Series([1.0, 2.0])
        >>> accessor = SeriesUtilsAccessor(series=series)
        >>> accessor.save(path="out.parquet")
        Traceback (most recent call last):
            ...
        NotImplementedError: Not implemented for series yet: leverage existing df methods
        """
        msg = "Not implemented for series yet: leverage existing df methods"
        raise NotImplementedError(msg)

    def slice_interval(
        self,
        interval: Interval[Date] | Interval[DateTime],
        /,
    ) -> Series:
        """
        Restrict the Series to entries whose index falls within ``interval``.

        The method dispatches on the index's inferred type so that callers
        can pass a single :class:`Interval` regardless of whether the
        underlying index stores :class:`datetime.datetime` or
        :class:`datetime.date` values: datetime indices receive the
        interval promoted to full datetimes; date indices receive it
        further narrowed back to dates. Slicing is label-based through
        :meth:`pandas.Series.loc` so the returned Series preserves dtype
        and any NA entries in the selected range. No copy is made, so
        mutations on the result may propagate to the bound Series.

        Parameters
        ----------
        interval
            Inclusive window whose endpoints bracket the entries to
            retain. Endpoint polarity is handled by
            :attr:`Interval.as_slice`, so inverted intervals are sliced
            in storage order.

        Returns
        -------
            Subset of the bound Series whose index values lie inside
            ``interval``. The subset preserves the original dtype and NA
            placement.

        Raises
        ------
        TypeError
            Raised when the Series index is neither datetime- nor
            date-typed, which is required to translate the interval into
            a label-based slice.

        See Also
        --------
        pandas.Series.loc : Label-based selector used under the hood.
        pandas.Index.inferred_type : Dispatch key used to detect datetime or date indices.
        mayutils.objects.datetime.Interval.as_slice : Slice representation consumed by ``.loc``.
        SeriesUtilsAccessor.ground : Downstream helper that relies on interval slicing.

        Examples
        --------
        >>> import datetime
        >>> import pandas as pd
        >>> from mayutils.objects.datetime import DateTime, Interval
        >>> from mayutils.objects.dataframes.pandas.series import SeriesUtilsAccessor
        >>> index = pd.Index(
        ...     [
        ...         datetime.datetime(2024, 1, 1),
        ...         datetime.datetime(2024, 1, 2),
        ...         datetime.datetime(2024, 1, 3),
        ...     ],
        ...     dtype=object,
        ... )
        >>> series = pd.Series([1.0, 2.0, 3.0], index=index)
        >>> window = Interval[DateTime](
        ...     start=DateTime(2024, 1, 1),
        ...     end=DateTime(2024, 1, 2),
        ... )
        >>> accessor = SeriesUtilsAccessor(series=series)
        >>> accessor.slice_interval(window).tolist()
        [1.0, 2.0]
        """
        if self.series.index.inferred_type in ("datetime", "datetime64"):
            return self.series.loc[interval.to_datetime_interval().as_slice]
        if self.series.index.inferred_type == "date":
            return self.series.loc[interval.to_datetime_interval().to_date_interval().as_slice]

        msg = "Series index must be datetime or date type for interval slicing"
        raise TypeError(msg)

    def ground(
        self,
        interval: Interval[Date] | Interval[DateTime] | None,
        /,
    ) -> Series:
        """
        Divide the Series by its mean over a reference interval.

        Grounding is useful when comparing several Series that share a
        units scale but drift over time: anchoring each one to equal 1
        on average over a common window makes relative movements easier
        to read. The reference mean is computed by aggregating only the
        entries whose index falls within ``interval``, so NA entries in
        the window are excluded in line with :meth:`pandas.Series.mean`
        defaults. When no interval is supplied the Series is returned
        as-is so the helper can be used unconditionally in pipelines.

        Parameters
        ----------
        interval
            Window used to compute the grounding reference. When
            supplied, the mean of the Series values whose index falls
            within ``interval`` is used as the divisor so that the
            resulting Series equals 1 on average across that window.
            When ``None`` the Series is returned unchanged.

        Returns
        -------
            The Series rescaled by the mean of its values inside
            ``interval``, or the original Series when no interval is
            provided. Dtype coercion follows :meth:`pandas.Series.div`;
            integer inputs are promoted to floats on division.

        See Also
        --------
        pandas.Series.mean : Aggregation used to compute the divisor.
        pandas.Series.div : Elementwise division used to rescale the Series.
        SeriesUtilsAccessor.slice_interval : Helper that selects the reference window.
        numpy.ndarray : Underlying numpy storage whose dtype propagates through division.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.pandas.series import SeriesUtilsAccessor
        >>> series = pd.Series(
        ...     [10.0, 20.0, 30.0],
        ...     index=pd.date_range("2024-01-01", periods=3, freq="D"),
        ... )
        >>> accessor = SeriesUtilsAccessor(series=series)
        >>> accessor.ground(None).equals(series)
        True
        """
        if interval is None:
            return self.series

        return self.series.div(self.slice_interval(interval).mean())
