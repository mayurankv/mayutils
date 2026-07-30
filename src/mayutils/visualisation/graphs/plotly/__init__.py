"""Plotly-based visualisation components for creating charts, traces, and templates."""

from typing import TYPE_CHECKING

from mayutils.visualisation.graphs.plotly.charts import (
    AxisConfig,
    MainAxisConfig,
    MainAxisConfigs,
    PlotConfig,
    SubPlotConfig,
    Titles,
    TracesConfig,
)
from mayutils.visualisation.graphs.plotly.traces import (
    TraceType,
    is_trace_3d,
)
from mayutils.visualisation.graphs.plotly.utilities import (
    include_plotly_js,
    map_categorical_array,
    melt_dataframe,
)

if TYPE_CHECKING:
    from mayutils.visualisation.graphs.plotly.charts import (
        Plot,
        SubPlot,
    )
    from mayutils.visualisation.graphs.plotly.templates import (
        get_default_template_name,
        get_template,
        set_renderer,
        set_template,
        use_template,
    )
    from mayutils.visualisation.graphs.plotly.traces import (
        Bar3d,
        Cuboid,
        Ecdf,
        Icicle,
        Kde,
        Line,
        Null,
        Scatter,
        merge_cuboids,
    )

__all__ = [
    "AxisConfig",
    "Bar3d",
    "Cuboid",
    "Ecdf",
    "Icicle",
    "Kde",
    "Line",
    "MainAxisConfig",
    "MainAxisConfigs",
    "Null",
    "Plot",
    "PlotConfig",
    "Scatter",
    "SubPlot",
    "SubPlotConfig",
    "Titles",
    "TraceType",
    "TracesConfig",
    "get_default_template_name",
    "get_template",
    "include_plotly_js",
    "is_trace_3d",
    "map_categorical_array",
    "melt_dataframe",
    "merge_cuboids",
    "set_renderer",
    "set_template",
    "use_template",
]


def __getattr__(
    name: str,
) -> object:
    """
    Materialise the lazily exported plotly symbols on first access.

    The chart and trace classes subclass plotly types and the template
    helpers register custom templates at import time, so importing their
    defining modules requires the optional plotting extras. Deferring
    those imports to first attribute access (and caching the result back
    into the module globals) keeps this package importable without
    plotly while preserving the public
    ``mayutils.visualisation.graphs.plotly`` surface.

    Parameters
    ----------
    name
        Attribute being looked up on the module.

    Returns
    -------
        The requested chart class, trace class, or template helper.

    Raises
    ------
    AttributeError
        If *name* is not a lazily materialised attribute.

    See Also
    --------
    mayutils.visualisation.graphs.plotly.charts : Source of the chart classes.
    mayutils.visualisation.graphs.plotly.templates : Source of the template helpers.
    mayutils.visualisation.graphs.plotly.traces : Source of the trace classes.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly import Plot
    >>> Plot.__name__
    'Plot'
    """
    submodules = {
        "Bar3d": "traces",
        "Cuboid": "traces",
        "Ecdf": "traces",
        "Icicle": "traces",
        "Kde": "traces",
        "Line": "traces",
        "Null": "traces",
        "Plot": "charts",
        "Scatter": "traces",
        "SubPlot": "charts",
        "get_default_template_name": "templates",
        "get_template": "templates",
        "merge_cuboids": "traces",
        "set_renderer": "templates",
        "set_template": "templates",
        "use_template": "templates",
    }

    if name not in submodules:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)

    from importlib import import_module

    value: object = getattr(import_module(f"{__name__}.{submodules[name]}"), name)
    globals()[name] = value

    return value
