"""Provide an invisible scatter trace for initialising empty axes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from mayutils.core.extras import may_require_extras
from mayutils.visualisation.graphs.plotly.traces.types import TraceType

if TYPE_CHECKING:
    from collections.abc import Sequence

with may_require_extras():
    import plotly.graph_objects as go


class Null(go.Scatter):
    """
    Invisible scatter trace used to initialise an axis without visible data.

    Creates a hidden ``go.Scatter`` with empty data so that an axis exists
    in the figure layout before real traces are added.

    Parameters
    ----------
    x_datetime
        When ``True``, seed the x-axis with today's date so Plotly
        infers a datetime axis type. Ignored when *x* and *y* are given.
    x
        Real ``x`` values to anchor the placeholder to, e.g. borrowed from
        another trace sharing a ``matches``-linked axis. Ignored unless
        *y* is also given.
    y
        Real ``y`` values to anchor the placeholder to. Ignored unless *x*
        is also given.
    **kwargs
        Additional keyword arguments forwarded to
        ``plotly.graph_objects.Scatter``.

    See Also
    --------
    plotly.graph_objects.Scatter : Parent trace class.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.traces.null import Null
    >>> trace = Null()
    >>> trace.showlegend
    False
    """

    trace_type: ClassVar[TraceType] = TraceType.NULL

    def __init__(
        self,
        *,
        x_datetime: bool = False,
        x: Sequence[Any] | None = None,
        y: Sequence[Any] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """
        Create the invisible scatter trace.

        Without *x*/*y*, delegates to ``go.Scatter.__init__`` with empty
        data and ``showlegend=False`` so the trace occupies no visual
        space. When real *x*/*y* are supplied, renders a genuinely
        invisible (fully transparent) two-or-more-point line instead:
        Plotly only draws a subplot's axis tick labels when at least one
        of its traces has real rendered path geometry, so an empty-data
        placeholder silently suppresses ticks that a shared/``matches``
        axis still needs from a neighbouring populated cell. Colour
        transparency (rather than ``opacity=0``) keeps the trace invisible
        without triggering that same suppression.

        Parameters
        ----------
        x_datetime
            When ``True``, seed the x-axis with today's date so Plotly
            infers a datetime axis type. Ignored when *x* and *y* are
            given.
        x
            Real ``x`` values to anchor the placeholder to. Ignored
            unless *y* is also given.
        y
            Real ``y`` values to anchor the placeholder to. Ignored
            unless *x* is also given.
        **kwargs
            Additional keyword arguments forwarded to
            ``plotly.graph_objects.Scatter``.

        Raises
        ------
        ValueError
            If ``meta`` is passed, since it is reserved for internal use.

        See Also
        --------
        plotly.graph_objects.Scatter : Parent trace class.

        Examples
        --------
        >>> from mayutils.visualisation.graphs.plotly.traces.null import Null
        >>> trace = Null()
        >>> trace.meta
        <TraceType.NULL: 'null'>
        >>> anchored = Null(x=[1, 2], y=[3, 4])
        >>> anchored.line.color
        'rgba(0,0,0,0)'
        """
        with may_require_extras():
            import pandas as pd

        from mayutils.objects.datetime import DateTime

        if "meta" in kwargs:
            msg = "The 'meta' argument is reserved for internal use and cannot be set by the user."
            raise ValueError(msg)

        if x is not None and y is not None and len(x) > 0 and len(y) > 0:
            super().__init__(  # pyright: ignore[reportUnknownMemberType]
                x=x,
                y=y,
                mode="lines",
                line={"color": "rgba(0,0,0,0)"},
                hoverinfo="skip",
                showlegend=False,
                meta=self.trace_type,
                **kwargs,
            )
        else:
            super().__init__(  # pyright: ignore[reportUnknownMemberType]
                x=[] if not x_datetime else pd.to_datetime([DateTime.today()]).to_numpy(),
                y=[],
                showlegend=False,
                meta=self.trace_type,
                **kwargs,
            )
