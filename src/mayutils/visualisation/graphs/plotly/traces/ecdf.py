"""Empirical cumulative distribution function trace."""

from typing import Any, ClassVar, Literal

from mayutils.core.extras import may_require_extras
from mayutils.visualisation.graphs.plotly.traces.line import Line
from mayutils.visualisation.graphs.plotly.traces.types import TraceType

with may_require_extras():
    import numpy as np
    from numpy.typing import ArrayLike


class Ecdf(Line):
    """
    Empirical cumulative distribution function trace.

    Computes a step-wise CDF from raw observations and renders it as a
    filled :class:`Line` trace.  Supports probability, percentage, and
    raw-count normalisation as well as reversed and complementary modes.

    Parameters
    ----------
    x
        Raw observation values.
    y
        Optional per-observation weights; defaults to uniform weights.
    y_shift
        Vertical offset applied after normalisation.
    norm
        Normalisation mode for the cumulative sum.
    mode
        Direction of the CDF: standard (ascending), reversed, or
        complementary (survival function).
    fill
        Plotly fill mode for the area under the curve.
    left_inclusive
        When ``True``, the step function includes the left endpoint.
    **kwargs
        Forwarded to :class:`Line`.

    Raises
    ------
    ValueError
        If *x* and *y* have different lengths.

    See Also
    --------
    mayutils.visualisation.graphs.plotly.traces.kde.Kde :
        Kernel density estimate trace.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.traces.ecdf import Ecdf
    >>> Ecdf(x=[1, 2, 3, 4])  # doctest: +SKIP
    """

    trace_type: ClassVar[TraceType] = TraceType.ECDF

    def __init__(
        self,
        *,
        x: ArrayLike,
        y: ArrayLike | None = None,
        y_shift: float = 0,
        norm: Literal["probability", "percentage", "count"] = "probability",
        mode: Literal["standard", "reversed", "complementary"] = "standard",
        fill: Literal["tozeroy", "tonexty", "toself"] = "toself",
        left_inclusive: bool = False,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """
        Compute the ECDF and initialise the trace.

        Sorts *x*, computes the cumulative sum (optionally weighted by
        *y*), normalises according to *norm*, and delegates to
        :class:`Line`.

        Parameters
        ----------
        x
            Raw observation values.
        y
            Optional per-observation weights; defaults to uniform.
        y_shift
            Vertical offset applied after normalisation.
        norm
            Normalisation mode for the cumulative sum.
        mode
            Direction of the CDF.
        fill
            Plotly fill mode for the area under the curve.
        left_inclusive
            When ``True``, the step includes the left endpoint.
        **kwargs
            Forwarded to :class:`Line`.

        Raises
        ------
        ValueError
            If *x* and *y* have different lengths.

        See Also
        --------
        Line : Parent trace class.

        Examples
        --------
        >>> Ecdf(x=[1, 2, 3], norm="percentage")  # doctest: +SKIP
        """
        x_arr = np.asarray(x)
        idx = np.argsort(x_arr)

        if mode == "reversed":
            idx = np.flip(idx)

        x_arr = x_arr[idx]

        if y is None:
            y_arr = np.ones(shape=len(x_arr))
        else:
            y_arr = np.asarray(y)
            if len(y_arr) != len(x_arr):
                msg = "x and y arrays are not the same length"
                raise ValueError(msg)

            y_arr = y_arr[idx]

        y_sum = np.sum(y_arr)
        y_arr = np.cumsum(y_arr)
        if mode == "complementary":
            y_arr = y_sum - y_arr

        if norm == "probability":
            y_arr = y_arr / y_sum
        elif norm == "percentage":
            y_arr = 100 * y_arr / y_sum

        y_arr += y_shift

        kwargs["line_shape"] = "hv" if ((mode != "reversed") ^ (not left_inclusive)) else "vh"
        kwargs["fill"] = fill

        if fill == "toself":
            x_arr = np.insert(x_arr, 0, x_arr[-1])
            y_arr = np.insert(y_arr, 0, y_shift)

        super().__init__(
            x=x_arr,
            y=y_arr,
            customdata=y_arr - y_shift,
            hovertemplate="<b>%{fullData.name}</b><br>x: %{x}<br>y: %{customdata}<extra></extra>",
            **kwargs,
        )
