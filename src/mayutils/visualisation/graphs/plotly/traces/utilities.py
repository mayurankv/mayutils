"""Provide trace-type inspection utilities."""

from typing import cast

from mayutils.visualisation.graphs.plotly.charts import Trace


def is_trace_3d(
    trace: Trace,
    /,
) -> bool:
    """
    Return whether *trace* is a 3-D type (mesh3d, surface, scatter3d, etc.).

    Checks the trace's ``type`` attribute against known 3-D suffixes and
    names to determine whether the trace renders in a 3-D scene.

    Parameters
    ----------
    trace
        A Plotly trace object with a ``type`` attribute.

    Returns
    -------
        ``True`` if the trace type ends with ``"3d"`` or is a known
        3-D type such as ``"surface"`` or ``"cone"``.

    Raises
    ------
    TypeError
        If *trace* lacks a ``type`` attribute.

    See Also
    --------
    plotly.basedatatypes.BaseTraceType : Base class for Plotly traces.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.traces.utilities import is_trace_3d
    >>> import plotly.graph_objects as go
    >>> is_trace_3d(go.Scatter3d())
    True
    """
    if not hasattr(trace, "type"):
        msg = f"Expected a Plotly trace object with a 'type' attribute, got {type(trace).__name__}"
        raise TypeError(msg)

    trace_type = cast("str", trace.type)

    return trace_type.endswith("3d") or trace_type in ["surface", "mesh3d", "cone", "streamtube", "volume"]
