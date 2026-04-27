"""
Define the graphing backend namespace for the visualisation layer.

Group the plotting helpers that sit on top of the supported rendering
libraries (Plotly, Matplotlib, Seaborn, ggplot). Centralise the shared
type aliases used to discriminate between backends so downstream modules
dispatch on a single canonical literal rather than ad-hoc strings,
keeping the chart construction APIs backend-agnostic.

See Also
--------
mayutils.visualisation.graphs.plotly : Plotly-backed chart helpers.
mayutils.visualisation.graphs.matplotlib : Matplotlib-backed chart helpers.
plotly.graph_objects.Figure : Plotly figure object produced by the Plotly backend.
matplotlib.figure.Figure : Matplotlib figure object produced by the Matplotlib backend.

Examples
--------
Annotate a dispatcher function with the ``PlotType`` literal alias to
restrict acceptable backend names at type-check time.

>>> from mayutils.visualisation.graphs import PlotType
>>> def render(backend: PlotType) -> str:
...     return f"using {backend}"
>>> render("plotly")
'using plotly'
"""

from typing import Literal

type PlotType = Literal["plotly", "matplotlib", "seaborn", "ggplot"]
