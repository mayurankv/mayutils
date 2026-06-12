"""Plotly trace types for building chart data series."""

from typing import TYPE_CHECKING

from mayutils.visualisation.graphs.plotly.traces.types import TraceType
from mayutils.visualisation.graphs.plotly.traces.utilities import is_trace_3d

if TYPE_CHECKING:
    from mayutils.visualisation.graphs.plotly.traces.ecdf import Ecdf
    from mayutils.visualisation.graphs.plotly.traces.icicle import Icicle
    from mayutils.visualisation.graphs.plotly.traces.kde import Kde
    from mayutils.visualisation.graphs.plotly.traces.line import Line
    from mayutils.visualisation.graphs.plotly.traces.mesh3d import Bar3d, Cuboid, merge_cuboids
    from mayutils.visualisation.graphs.plotly.traces.null import Null
    from mayutils.visualisation.graphs.plotly.traces.scatter import Scatter

__all__ = [
    "Bar3d",
    "Cuboid",
    "Ecdf",
    "Icicle",
    "Kde",
    "Line",
    "Null",
    "Scatter",
    "TraceType",
    "is_trace_3d",
    "merge_cuboids",
]


def __getattr__(
    name: str,
) -> object:
    """
    Materialise the lazily exported trace symbols on first access.

    The concrete trace classes subclass ``plotly.graph_objects`` types,
    so importing their defining modules requires the optional plotting
    extras. Deferring those imports to first attribute access (and
    caching the result back into the module globals) keeps this package
    importable without plotly while preserving the public
    ``mayutils.visualisation.graphs.plotly.traces`` surface.

    Parameters
    ----------
    name
        Attribute being looked up on the module.

    Returns
    -------
        The requested trace class or helper.

    Raises
    ------
    AttributeError
        If *name* is not a lazily materialised attribute.

    See Also
    --------
    mayutils.visualisation.graphs.plotly.traces.line.Line : One of the
        lazily exported trace classes.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.traces import Line
    >>> Line.__name__
    'Line'
    """
    submodules = {
        "Bar3d": "mesh3d",
        "Cuboid": "mesh3d",
        "Ecdf": "ecdf",
        "Icicle": "icicle",
        "Kde": "kde",
        "Line": "line",
        "Null": "null",
        "Scatter": "scatter",
        "merge_cuboids": "mesh3d",
    }

    if name not in submodules:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)

    from importlib import import_module

    value: object = getattr(import_module(f"{__name__}.{submodules[name]}"), name)
    globals()[name] = value

    return value
