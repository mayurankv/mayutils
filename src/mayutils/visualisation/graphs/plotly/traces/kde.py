"""Kernel density estimate trace."""

from typing import Any, ClassVar, cast

from mayutils.core.extras import may_require_extras
from mayutils.visualisation.graphs.plotly.traces.line import Line
from mayutils.visualisation.graphs.plotly.traces.types import TraceType

with may_require_extras():
    import numpy as np
    from numpy.typing import ArrayLike, NDArray
    from scipy.stats import gaussian_kde


class Kde(Line):
    trace_type: ClassVar[TraceType] = TraceType.KDE
    """
    Kernel density estimate rendered as a filled line trace.

    Computes a Gaussian KDE over *x* using :func:`scipy.stats.gaussian_kde`
    and plots the resulting density curve as a :class:`Line`.

    Parameters
    ----------
    x
        Raw observation values.
    bandwidth
        Bandwidth (smoothing parameter) passed to
        :func:`~scipy.stats.gaussian_kde`; ``None`` uses Scott's rule.
    **kwargs
        Forwarded to :class:`Line`.

    See Also
    --------
    mayutils.visualisation.graphs.plotly.traces.ecdf.Ecdf :
        Empirical CDF trace.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.traces.kde import Kde
    >>> Kde(x=[1, 2, 2, 3, 3, 3])  # doctest: +SKIP
    """

    def __init__(
        self,
        *,
        x: ArrayLike,
        bandwidth: float | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """
        Compute the KDE and initialise the trace.

        Evaluates the density over a 1 000-point grid spanning the range
        of *x* and delegates to :class:`Line`.

        Parameters
        ----------
        x
            Raw observation values.
        bandwidth
            Bandwidth passed to :func:`~scipy.stats.gaussian_kde`;
            ``None`` uses Scott's rule.
        **kwargs
            Forwarded to :class:`Line`.

        See Also
        --------
        Line : Parent trace class.

        Examples
        --------
        >>> Kde(x=[1, 2, 3], bandwidth=0.5)  # doctest: +SKIP
        """
        x_arr = np.asarray(x)
        kde = gaussian_kde(dataset=x_arr, bw_method=bandwidth)

        x_grid = cast("NDArray[np.float64]", np.linspace(start=np.min(a=x_arr), stop=np.max(a=x_arr), num=1000))
        y_arr = kde(points=x_grid)

        super().__init__(
            x=x_grid,
            y=y_arr,
            customdata=x_arr,
            fill=kwargs.pop("fill", "tozeroy"),
            **kwargs,
        )
