"""
Scatter trace with sensible defaults.

Thin wrapper around :class:`plotly.graph_objects.Scatter` that defaults to
``mode="markers"`` and reserves the ``meta`` field for internal trace-type
identification.
"""

from typing import Any, ClassVar

from mayutils.core.extras import may_require_extras
from mayutils.visualisation.graphs.plotly.traces.types import TraceType

with may_require_extras():
    import plotly.graph_objects as go


class Scatter(go.Scatter):
    """
    Scatter trace defaulting to marker mode.

    Thin wrapper around :class:`plotly.graph_objects.Scatter` that sets
    ``mode="markers"`` by default and reserves ``meta`` for internal
    trace-type identification.

    Parameters
    ----------
    mode
        Plotly drawing mode, by default ``"markers"``.
    **kwargs
        Forwarded to :class:`plotly.graph_objects.Scatter`.

    Raises
    ------
    ValueError
        If ``meta`` is passed, since it is reserved for internal use.

    See Also
    --------
    mayutils.visualisation.graphs.plotly.traces.line.Line :
        Line trace built on the same Scatter base.

    Examples
    --------
    >>> Scatter(x=[1, 2, 3], y=[4, 5, 6])  # doctest: +SKIP
    """

    trace_type: ClassVar[TraceType] = TraceType.SCATTER

    def __init__(
        self,
        mode: str | None = "markers",
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """
        Initialise a Scatter trace.

        Sets ``meta="scatter"`` for internal trace-type identification.

        Parameters
        ----------
        mode
            Plotly drawing mode, by default ``"markers"``.
        **kwargs
            Forwarded to :class:`plotly.graph_objects.Scatter`.

        Raises
        ------
        ValueError
            If ``meta`` is passed, since it is reserved for internal use.

        See Also
        --------
        mayutils.visualisation.graphs.plotly.traces.line.Line :
            Line trace built on the same Scatter base.

        Examples
        --------
        >>> Scatter(x=[1, 2, 3], y=[4, 5, 6])  # doctest: +SKIP
        """
        if "meta" in kwargs:
            msg = "The 'meta' argument is reserved for internal use and cannot be set by the user."
            raise ValueError(msg)

        super().__init__(
            mode=mode,
            meta=self.trace_type,
            **kwargs,
        )
