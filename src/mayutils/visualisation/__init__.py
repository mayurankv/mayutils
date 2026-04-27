"""
Gather visualisation helpers for plots, charts and notebook rendering.

Bundle the visual output layer of ``mayutils`` into a single namespace,
covering graph construction, rich console rendering, and Jupyter
notebook display configuration. The package offers a common surface for
turning the dataframes and arrays used elsewhere in the library into
interactive or static figures, while keeping heavy third-party
dependencies (plotly, matplotlib, IPython) behind the ``plotting`` and
``notebook`` extras so base installs stay lean. Import costs are paid
lazily by the submodules so that downstream code can opt into the
subsystems it actually needs.

See Also
--------
mayutils.visualisation.console : Rich-backed console helpers for
    formatted text, tables and mathematical notation in terminals.
mayutils.visualisation.notebook : Jupyter display configuration shims
    gated behind the ``notebook`` extra.
mayutils.visualisation.graphs : Chart builders that wrap plotly and
    matplotlib behind a uniform API, gated behind the ``plotting``
    extra.
plotly.graph_objects : Third-party plotting library targeted by the
    default chart builders.
matplotlib.pyplot : Alternative plotting backend used for static figure
    export.

Examples
--------
>>> from mayutils import visualisation
>>> "console" in dir(visualisation) or hasattr(visualisation, "__doc__")
True
"""
