"""Plotly-based visualisation components for creating charts, traces, and templates."""

from mayutils.visualisation.graphs.plotly.charts import (
    AxisConfig,
    MainAxisConfig,
    MainAxisConfigs,
    Plot,
    PlotConfig,
    SubPlot,
    SubPlotConfig,
    Titles,
    TracesConfig,
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
    TraceType,
    is_trace_3d,
    merge_cuboids,
)
from mayutils.visualisation.graphs.plotly.utilities import (
    include_plotly_js,
    map_categorical_array,
    melt_dataframe,
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
    "TraceType",
    "SubPlotConfig",
    "Titles",
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
