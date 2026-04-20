"""Custom ``pandas`` Series accessor registered under ``series.utils``.

This module defines :class:`SeriesUtilsAccessor`, the one-dimensional
counterpart to the DataFrame accessor provided elsewhere in
``mayutils.objects.dataframes.pandas``. It collects Series-level helpers
that are useful when working with time-indexed numeric data, such as
anchoring a Series to its mean over a user-supplied interval so that
multiple Series can be compared on a common base. The ``pandas``
dependency is imported lazily through :func:`may_require_extras` so that
importing this module does not require the full optional dependency set
to be installed.
"""

from pathlib import Path
from typing import NoReturn

from mayutils.core.extras import may_require_extras
from mayutils.objects.datetime import Date, DateTime, Interval

with may_require_extras():
    from pandas import Series


class SeriesUtilsAccessor:
    """Accessor providing Series-level helpers under ``series.utils``.

    The accessor stores a reference to the wrapped :class:`pandas.Series`
    and exposes methods that operate on a single one-dimensional array of
    values, complementing the DataFrame accessor for workflows where
    only a column-like object is being manipulated.

    Parameters
    ----------
    series : pandas.Series
        The underlying one-dimensional data container whose values and
        index are used by every method on the accessor.
    """

    def __init__(
        self,
        series: Series,
    ) -> None:
        """Store the target Series on the accessor instance.

        Parameters
        ----------
        series : pandas.Series
            The one-dimensional data container that the accessor will
            read from and transform when its methods are invoked.
        """
        self.series = series

    def save(
        self,
        path: Path | str,
    ) -> NoReturn:
        """Persist the wrapped Series to a file on disk.

        Parameters
        ----------
        path : pathlib.Path or str
            Filesystem location at which the Series would be written once
            serialisation support is implemented for one-dimensional
            inputs.

        Raises
        ------
        NotImplementedError
            Always raised; persistence for Series is not yet available,
            and callers should convert the Series to a DataFrame and use
            the DataFrame accessor's ``save`` method instead.
        """
        msg = "Not implemented for series yet: leverage existing df methods"
        raise NotImplementedError(msg)

    def slice_interval(
        self,
        interval: Interval[Date] | Interval[DateTime],
        /,
    ) -> Series:
        """Restrict the Series to entries whose index falls within ``interval``.

        Dispatches on the index's inferred type so that callers can pass
        a single :class:`Interval` regardless of whether the underlying
        index stores :class:`datetime.datetime` or :class:`datetime.date`
        values: datetime indices receive the interval promoted to full
        datetimes; date indices receive it further narrowed back to
        dates. The returned Series is a ``.loc`` view into the bound
        Series, not a copy.

        Parameters
        ----------
        interval : Interval
            Inclusive window whose endpoints bracket the entries to
            retain. Endpoint polarity is handled by
            :attr:`Interval.as_slice`, so inverted intervals are sliced
            in storage order.

        Returns
        -------
        pandas.Series
            Subset of the bound Series whose index values lie inside
            ``interval``.

        Raises
        ------
        TypeError
            Raised when the Series index is neither datetime- nor
            date-typed, which is required to translate the interval into
            a label-based slice.
        """
        if self.series.index.inferred_type == "datetime":
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
        """Divide the Series by its mean over a reference interval.

        Parameters
        ----------
        interval : Interval, optional
            Window used to compute the grounding reference. When
            supplied, the mean of the Series values whose index falls
            within ``interval`` is used as the divisor so that the
            resulting Series equals 1 on average across that window.
            When ``None`` the Series is returned unchanged.

        Returns
        -------
        pandas.Series
            The Series rescaled by the mean of its values inside
            ``interval``, or the original Series when no interval is
            provided.

        Raises
        ------
        TypeError
            If ``interval`` is provided but the Series index is neither
            datetime- nor date-typed, which is required to select values
            by time range.
        """
        if interval is None:
            return self.series

        return self.series.div(self.slice_interval(interval).mean())
