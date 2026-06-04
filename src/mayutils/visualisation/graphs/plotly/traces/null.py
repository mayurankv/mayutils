"""Provide an invisible scatter trace for initialising empty axes."""

from typing import Any, ClassVar

from mayutils.core.extras import may_require_extras
from mayutils.objects.datetime import DateTime
from mayutils.visualisation.graphs.plotly.traces.types import TraceType

with may_require_extras():
    import pandas as pd
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
        infers a datetime axis type.
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
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """
        Create the invisible scatter trace.

        Delegates to ``go.Scatter.__init__`` with empty ``y`` data and
        ``showlegend=False`` so the trace occupies no visual space.

        Parameters
        ----------
        x_datetime
            When ``True``, seed the x-axis with today's date so Plotly
            infers a datetime axis type.
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
        """
        if "meta" in kwargs:
            msg = "The 'meta' argument is reserved for internal use and cannot be set by the user."
            raise ValueError(msg)

        super().__init__(  # pyright: ignore[reportUnknownMemberType]
            x=[] if not x_datetime else pd.to_datetime([DateTime.today()]).to_numpy(),
            y=[],
            showlegend=False,
            meta=self.trace_type,
            **kwargs,
        )
