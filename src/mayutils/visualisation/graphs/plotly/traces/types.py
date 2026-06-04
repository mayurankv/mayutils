"""Enumeration of supported Plotly trace types."""

from enum import StrEnum


class TraceType(StrEnum):
    """
    Supported Plotly trace types.

    A string enumeration whose members map to the trace-type identifiers used
    throughout the ``mayutils`` charting API.  Each member's value is the
    lower-case slug passed to trace factory functions.

    Attributes
    ----------
    LINE
        Standard line trace.
    SCATTER
        Scatter (marker) trace.
    ECDF
        Empirical cumulative distribution function trace.
    KDE
        Kernel density estimation trace.
    NULL
        Null / placeholder trace (no visual output).
    BAR3D
        Three-dimensional bar (mesh) trace.

    See Also
    --------
    mayutils.visualisation.graphs.plotly.traces : Trace factory modules.

    Examples
    --------
    >>> TraceType.LINE  # doctest: +SKIP
    <TraceType.LINE: 'line'>
    >>> TraceType.LINE == "line"  # doctest: +SKIP
    True
    """

    LINE = "line"
    SCATTER = "scatter"
    ECDF = "ecdf"
    KDE = "kde"
    NULL = "null"
    BAR3D = "bar3d"
