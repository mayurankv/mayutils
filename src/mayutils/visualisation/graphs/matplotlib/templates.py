"""
Define the Matplotlib styling templates for the graphs package.

Centralise the colour palettes, rc parameter overrides, and figure-level
theme configuration applied by the Matplotlib chart helpers inside
:mod:`mayutils.visualisation.graphs.matplotlib`. Provide the canonical
location for typography, grid styling, and palette tokens so that every
Matplotlib figure produced by the package shares the same visual
identity as its Plotly counterparts.

See Also
--------
mayutils.visualisation.graphs.matplotlib : Parent package that imports
    and applies the templates defined in this module.
mayutils.visualisation.graphs.plotly.templates : Sibling Plotly template
    module whose themes encode the equivalent visual identity for
    Plotly output.
matplotlib.figure.Figure : Matplotlib figure object whose defaults are
    configured by the templates defined here.
matplotlib.pyplot : Matplotlib state-based interface whose rcParams
    receive any global overrides declared in this module.

Examples
--------
Import the templates module so that any palette or rcParams overrides
declared at module scope are registered with Matplotlib before a figure
is constructed by the helpers in
:mod:`mayutils.visualisation.graphs.matplotlib`.

>>> from mayutils.visualisation.graphs.matplotlib import templates
>>> templates.__name__
'mayutils.visualisation.graphs.matplotlib.templates'
"""
