"""Provide an invisible scatter trace for initialising empty axes."""

from typing import Any

from mayutils.core.extras import may_require_extras
from mayutils.objects.datetime import DateTime

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
    >>> trace = Null()  # doctest: +SKIP
    >>> trace.showlegend  # doctest: +SKIP
    False
    """

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

        See Also
        --------
        plotly.graph_objects.Scatter : Parent trace class.

        Examples
        --------
        >>> from mayutils.visualisation.graphs.plotly.traces.null import Null
        >>> trace = Null()  # doctest: +SKIP
        >>> trace.meta  # doctest: +SKIP
        'null'
        """
        super().__init__(  # pyright: ignore[reportUnknownMemberType]
            x=[] if not x_datetime else pd.to_datetime([DateTime.today()]).to_numpy(),
            y=[],
            showlegend=False,
            meta="null",
            **kwargs,
        )
