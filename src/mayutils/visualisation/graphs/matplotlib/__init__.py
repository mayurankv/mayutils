"""
Expose the Matplotlib-backed chart helper namespace.

Group chart builders, styling helpers, and theme templates that produce
Matplotlib figures consistent with the shared visual identity used
across the library's plotting backends. Sit inside
:mod:`mayutils.visualisation.graphs` so that chart construction code can
dispatch between Matplotlib, Plotly, and other backends using a uniform
namespace structure.

See Also
--------
mayutils.visualisation.graphs.matplotlib.templates : Matplotlib theme
    configuration applied by the chart helpers exposed from this package.
mayutils.visualisation.graphs.plotly : Sibling Plotly backend providing
    the equivalent chart helpers for Plotly output.
matplotlib.figure.Figure : Matplotlib figure object that the helpers in
    this package construct and return.
matplotlib.pyplot : Matplotlib state-based interface used when no
    existing :class:`~matplotlib.figure.Figure` is supplied.

Examples
--------
Import the Matplotlib backend to pick up both the chart helpers and the
theme templates applied to all figures it emits.

>>> from mayutils.visualisation.graphs import matplotlib as mpl_charts
>>> mpl_charts.__name__
'mayutils.visualisation.graphs.matplotlib'
"""
