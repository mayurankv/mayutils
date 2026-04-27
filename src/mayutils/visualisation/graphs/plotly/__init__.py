"""
Expose the Plotly-backed chart helper namespace.

Group chart builders, trace helpers, layout utilities, and theme
templates that produce Plotly figures consistent with the shared visual
identity used across the library's plotting backends. Sit inside
:mod:`mayutils.visualisation.graphs` so that chart construction code can
dispatch between Plotly, Matplotlib, and other backends using a uniform
namespace structure.

See Also
--------
mayutils.visualisation.graphs.plotly.templates : Plotly ``base``,
    ``slides``, ``save``, and ``business_compliant`` layout templates
    registered on :mod:`plotly.io.templates` at import time.
mayutils.visualisation.graphs.plotly.utilities : Helpers for embedding
    ``plotly.min.js``, encoding categorical arrays, and melting
    DataFrames for trace constructors.
mayutils.visualisation.graphs.matplotlib : Sibling Matplotlib backend
    exposing the equivalent chart helpers for Matplotlib output.
plotly.graph_objects.Figure : Plotly figure object that the helpers in
    this package construct and return.
plotly.io.templates : Plotly template registry that receives the themes
    declared in :mod:`mayutils.visualisation.graphs.plotly.templates`.

Examples
--------
Import the Plotly backend to pick up both the chart helpers and the
registered layout templates used as package-wide defaults.

>>> from mayutils.visualisation.graphs import plotly as plotly_charts
>>> plotly_charts.__name__
'mayutils.visualisation.graphs.plotly'
"""
