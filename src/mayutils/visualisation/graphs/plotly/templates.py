"""Plotly template registration and management for consistent chart styling."""

from collections.abc import Generator, Sequence
from contextlib import contextmanager
from typing import cast

from mayutils.core.extras import may_require_extras
from mayutils.objects.colours import (
    BASE_COLOURSCALE,
    CONTINUOUS_COLORSCALE,
    DIVERGENT_COLOURSCALE,
    hex_to_rgba,
)

with may_require_extras():
    import plotly.graph_objects as go
    import plotly.io as pio


TRANSPARENT = "rgba(0,0,0,0)"


def get_default_template_name() -> str:
    """
    Return the name of the currently active default Plotly template.

    Reads ``plotly.io.templates.default`` and casts the result to a plain string.

    Returns
    -------
    str
        Template name string registered in ``plotly.io.templates``.

    See Also
    --------
    default_template : Return the template object itself.
    set_template : Change the active default template.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.templates import default_template_name
    >>> isinstance(default_template_name(), str)
    True
    """
    return cast("str", pio.templates.default)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType, reportAttributeAccessIssue]


def get_template(
    *,
    template_name: str | None = None,
) -> go.layout.Template:
    """
    Return the currently active default Plotly template object.

    Looks up ``plotly.io.templates.default`` and resolves it to the full template.

    Parameters
    ----------
    template_name
        Name of a registered template to look up.  When ``None`` (the
        default), the current global default is used.

    Returns
    -------
    Template
        The resolved ``plotly.graph_objs.layout.Template`` instance.

    See Also
    --------
    default_template_name : Return the template name as a string.
    set_template : Change the active default template.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.templates import default_template
    >>> default_template() is not None
    True
    """
    if template_name is None:
        template_name = get_default_template_name()

    return cast("go.layout.Template", pio.templates[template_name])  # pyright: ignore[reportAssignmentType, reportInvalidTypeArguments]


def set_template(
    *,
    template: str = "base",
) -> None:
    """
    Set the global default Plotly template.

    Assigns the given template name to ``plotly.io.templates.default``.

    Parameters
    ----------
    template
        Name of a registered template. Defaults to ``"base"``.

    See Also
    --------
    use_template : Context manager for temporary template changes.
    register_templates : Register the custom templates available to this function.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.templates import set_template
    >>> set_template("base")
    """
    pio.templates.default = template  # pyright: ignore[reportAttributeAccessIssue]


def set_renderer(
    *,
    renderer: str = "vscode",
) -> None:
    """
    Set the global default Plotly renderer.

    Assigns the given renderer name to ``plotly.io.renderers.default``.

    Parameters
    ----------
    renderer
        Renderer name (e.g. ``"vscode"``, ``"browser"``). Defaults to
        ``"vscode"``.

    See Also
    --------
    set_template : Change the active template independently of the renderer.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.templates import set_renderer
    >>> set_renderer("vscode")
    """
    pio.renderers.default = renderer  # pyright: ignore[reportAttributeAccessIssue]


def get_template_layout(
    template: go.layout.Template,
    /,
) -> go.Layout:
    """
    Extract the layout from a Plotly template.

    Returns the ``layout`` attribute of *template*, falling back to an empty
    ``go.Layout()`` when the attribute is missing or ``None``.

    Parameters
    ----------
    template
        A Plotly ``Template`` instance.

    Returns
    -------
    go.Layout
        The template's layout object, or a fresh empty layout.

    See Also
    --------
    get_template : Retrieve a registered template by name.
    get_layout_value : Drill into a layout to read a nested property.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.templates import (
    ...     get_template,
    ...     get_template_layout,
    ... )
    >>> layout = get_template_layout(get_template())  # doctest: +SKIP
    """
    layout = getattr(template, "layout", None)

    if layout is None:
        layout = go.Layout()

    return layout


PLOTLY_DEFAULT_TEMPLATE_NAME = get_default_template_name()
PLOTLY_DEFAULT_TEMPLATE = get_template(template_name=PLOTLY_DEFAULT_TEMPLATE_NAME)
PLOTLY_DARK_TEMPLATE = get_template(template_name="plotly_dark")


@contextmanager
def use_template(
    template: str,
) -> Generator[None]:
    """
    Temporarily switch the default Plotly template within a context.

    The previous template is restored when the context exits, even on error.

    Parameters
    ----------
    template
        Name of a registered template to use inside the block.

    Yields
    ------
    None

    See Also
    --------
    set_template : Permanently change the default template.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.templates import use_template
    >>> with use_template("base"):  # doctest: +SKIP
    ...     pass
    """
    previous = get_default_template_name()
    set_template(template=template)

    try:
        yield
    finally:
        set_template(template=previous)


axis_structure_dict = {
    "showgrid": True,
    "gridwidth": 2,
    "zeroline": True,
    "zerolinewidth": 2,
    "showline": True,
    "mirror": True,
    "minor": {
        "showgrid": True,
    },
    "title": {
        "standoff": 10,
        "font": {
            "size": 16,
        },
    },
    "tickfont": {
        "size": 12,
    },
    "ticklabelmode": "period",
}
axis_dict = {
    **axis_structure_dict,
    "zerolinecolor": "#283442",
    "gridcolor": "#283442",
    "linecolor": "#506784",
    "minor": {
        "showgrid": True,
        "gridcolor": hex_to_rgba(
            cast("str", PLOTLY_DARK_TEMPLATE.layout.xaxis.gridcolor),  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            alpha=0.4,
        ),
    },
}
scene_axis_dict = {
    "backgroundcolor": TRANSPARENT,
    "gridcolor": "#506784",
    "gridwidth": 2,
    "linecolor": "#506784",
    "showbackground": True,
    "ticks": "",
    "zerolinecolor": "#C8D4E3",
    "zeroline": True,
    "showline": True,
    "mirror": True,
}
non_primary_axis_structure_dict = {
    **axis_structure_dict,
    "side": "right",
    "anchor": "x",
    "overlaying": "y",
    "showgrid": False,
    "tickmode": "auto",
    "zerolinewidth": 2,
    "minor": {
        "showgrid": False,
    },
}
non_primary_axis_dict = {
    **axis_dict,
    **non_primary_axis_structure_dict,
}
save_axis_dict = {
    "zerolinecolor": "rgba(200,200,200,0.5)",
    "gridcolor": "rgba(200,200,200,0.3)",
    "linecolor": "rgba(200,200,200,0.5)",
    "minor": {
        "gridcolor": "rgba(200,200,200,0.1)",
    },
}

shuffled_colourscale = [
    BASE_COLOURSCALE[idx]
    for offset in range(4)
    for idx in range(
        offset,
        len(BASE_COLOURSCALE),
        4,
    )
][::-1]


def register_template(
    name: str,
    /,
    *,
    template: go.layout.Template,
) -> None:
    """
    Register a custom Plotly template under a given name.

    Adds *template* to the ``plotly.io.templates`` registry so it can be
    activated later via `set_template` or combined with other templates using
    the ``"+"`` syntax (e.g. ``"base+save"``).

    Parameters
    ----------
    name
        Name to register the template under. This is the string that can be
        passed to `set_template` to activate it.
    template
        The Plotly Template object to register.

    See Also
    --------
    register_templates : Batch-register all built-in custom templates.
    set_template : Activate a registered template as the global default.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.templates import register_template
    >>> from plotly.graph_objs.layout import Template  # type: ignore[import]
    >>> register_template("my_template", template=Template())
    """
    pio.templates[name] = template  # pyright: ignore[reportInvalidTypeArguments, reportGeneralTypeIssues]


def register_templates() -> None:
    """
    Register custom Plotly templates (``base``, ``slides``, ``save``, ``business_compliant``).

    Called automatically at module import time. After registration the
    default template is set to ``"base"`` via `set_template`.

    See Also
    --------
    set_template : Change the active default template after registration.
    use_template : Temporarily switch templates within a context.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.templates import register_templates
    >>> register_templates()
    """
    register_template(
        "base",
        template=go.layout.Template(
            {
                "data": {
                    "bar": [
                        {
                            "error_x": {"color": "#f2f5fa"},
                            "error_y": {"color": "#f2f5fa"},
                            "marker": {
                                "line": {"color": TRANSPARENT, "width": 0.5},
                                "pattern": {"fillmode": "overlay", "size": 10, "solidity": 0.2},
                            },
                            "type": "bar",
                        }
                    ],
                    "barpolar": [
                        {
                            "marker": {
                                "line": {"color": TRANSPARENT, "width": 0.5},
                                "pattern": {"fillmode": "overlay", "size": 10, "solidity": 0.2},
                            },
                            "type": "barpolar",
                        }
                    ],
                    "carpet": [
                        {
                            "aaxis": {
                                "endlinecolor": "#A2B1C6",
                                "gridcolor": "#506784",
                                "linecolor": "#506784",
                                "minorgridcolor": "#506784",
                                "startlinecolor": "#A2B1C6",
                            },
                            "baxis": {
                                "endlinecolor": "#A2B1C6",
                                "gridcolor": "#506784",
                                "linecolor": "#506784",
                                "minorgridcolor": "#506784",
                                "startlinecolor": "#A2B1C6",
                            },
                            "type": "carpet",
                        }
                    ],
                    "choropleth": [{"colorbar": {"outlinewidth": 0, "ticks": ""}, "type": "choropleth"}],
                    "contour": [
                        {
                            "colorbar": {"outlinewidth": 0, "ticks": ""},
                            "colorscale": CONTINUOUS_COLORSCALE,
                            "type": "contour",
                        }
                    ],
                    "contourcarpet": [{"colorbar": {"outlinewidth": 0, "ticks": ""}, "type": "contourcarpet"}],
                    "heatmap": [
                        {
                            "colorbar": {"outlinewidth": 0, "ticks": ""},
                            "colorscale": CONTINUOUS_COLORSCALE,
                            "type": "heatmap",
                            "hoverongaps": False,
                            "texttemplate": "%{z}",
                        }
                    ],
                    "histogram": [
                        {
                            "marker": {
                                "opacity": 0.4,
                                "line": {
                                    "width": 1,
                                },
                                "pattern": {
                                    "fillmode": "overlay",
                                    "size": 10,
                                    "solidity": 0.2,
                                },
                            },
                            "histnorm": "probability density",
                            "type": "histogram",
                        }
                    ],
                    "histogram2d": [
                        {
                            "colorbar": {"outlinewidth": 0, "ticks": ""},
                            "colorscale": CONTINUOUS_COLORSCALE,
                            "type": "histogram2d",
                        }
                    ],
                    "histogram2dcontour": [
                        {
                            "colorbar": {"outlinewidth": 0, "ticks": ""},
                            "colorscale": CONTINUOUS_COLORSCALE,
                            "type": "histogram2dcontour",
                        }
                    ],
                    "mesh3d": [{"colorbar": {"outlinewidth": 0, "ticks": ""}, "type": "mesh3d"}],
                    "parcoords": [
                        {
                            "line": {"colorbar": {"outlinewidth": 0, "ticks": ""}},
                            "type": "parcoords",
                        }
                    ],
                    "pie": [{"automargin": True, "type": "pie"}],
                    "scatter": [
                        {
                            "marker": {
                                "line": {"color": "#283442"},
                                "size": 4,
                            },
                            "hovertemplate": "<b>%{fullData.name}</b><br>x: %{x}<br>y: %{y}<extra></extra>",
                            "type": "scatter",
                        },
                    ],
                    "scatter3d": [
                        {
                            "line": {"colorbar": {"outlinewidth": 0, "ticks": ""}},
                            "marker": {"colorbar": {"outlinewidth": 0, "ticks": ""}},
                            "type": "scatter3d",
                        }
                    ],
                    "scattercarpet": [
                        {
                            "marker": {"colorbar": {"outlinewidth": 0, "ticks": ""}},
                            "type": "scattercarpet",
                        }
                    ],
                    "scattergeo": [
                        {
                            "marker": {"colorbar": {"outlinewidth": 0, "ticks": ""}},
                            "type": "scattergeo",
                        }
                    ],
                    "scattergl": [{"marker": {"line": {"color": "#283442"}}, "type": "scattergl"}],
                    "scattermapbox": [
                        {
                            "marker": {"colorbar": {"outlinewidth": 0, "ticks": ""}},
                            "type": "scattermapbox",
                        }
                    ],
                    "scatterpolar": [
                        {
                            "marker": {"colorbar": {"outlinewidth": 0, "ticks": ""}},
                            "type": "scatterpolar",
                        }
                    ],
                    "scatterpolargl": [
                        {
                            "marker": {"colorbar": {"outlinewidth": 0, "ticks": ""}},
                            "type": "scatterpolargl",
                        }
                    ],
                    "scatterternary": [
                        {
                            "marker": {"colorbar": {"outlinewidth": 0, "ticks": ""}},
                            "type": "scatterternary",
                        }
                    ],
                    "surface": [
                        {
                            "colorbar": {"outlinewidth": 0, "ticks": ""},
                            "colorscale": CONTINUOUS_COLORSCALE,
                            "type": "surface",
                        }
                    ],
                    "table": [
                        {
                            "cells": {
                                "fill": {"color": "#506784"},
                                "line": {"color": TRANSPARENT},
                            },
                            "header": {
                                "fill": {"color": "#2a3f5f"},
                                "line": {"color": TRANSPARENT},
                            },
                            "type": "table",
                        }
                    ],
                },
                "layout": {
                    "annotationdefaults": {
                        "arrowcolor": "#f2f5fa",
                        "arrowhead": 0,
                        "arrowwidth": 0.5,
                        "font": {
                            "size": 10,
                        },
                    },
                    "autotypenumbers": "strict",
                    "barmode": "overlay",
                    "boxmode": "group",
                    "coloraxis": {"colorbar": {"outlinewidth": 0, "ticks": ""}},
                    "colorscale": {
                        "diverging": DIVERGENT_COLOURSCALE,
                        "sequential": CONTINUOUS_COLORSCALE,
                        "sequentialminus": CONTINUOUS_COLORSCALE,
                    },
                    "colorway": shuffled_colourscale,
                    "font": {
                        "color": "#f2f5fa",
                        "family": '"SF Pro Rounded", "Mona Sans", "CMU Serif", "Monaspace Neon", "Open Sans", verdana, arial, sans-serif',
                        "weight": 200,
                    },
                    "geo": {
                        "bgcolor": TRANSPARENT,
                        "lakecolor": TRANSPARENT,
                        "landcolor": TRANSPARENT,
                        "showlakes": True,
                        "showland": True,
                        "subunitcolor": "#506784",
                    },
                    "hoverlabel": {
                        "align": "left",
                        "font": {},
                    },
                    "hovermode": "closest",
                    "legend": {
                        "yref": "paper",
                        "y": 1,
                        "yanchor": "bottom",
                        "itemsizing": "trace",
                        "orientation": "h",
                        "font": {"size": 10},
                        "itemwidth": 30,
                        "grouptitlefont": {
                            "size": 12,
                            "weight": 200,
                        },
                        "bgcolor": TRANSPARENT,
                    },
                    "mapbox": {
                        "style": "dark",
                    },
                    "margin": {
                        "l": 50,
                        "b": 50,
                        "t": 75,
                        "r": 10,
                    },
                    "modebar": {
                        "bgcolor": TRANSPARENT,
                        "add": [],
                        "remove": ["zoomin", "zoomout", "lasso", "autoscale", "select"],
                    },
                    "paper_bgcolor": TRANSPARENT,
                    "plot_bgcolor": TRANSPARENT,
                    "polar": {
                        "angularaxis": {
                            "gridcolor": "#506784",
                            "linecolor": "#506784",
                            "ticks": "",
                        },
                        "bgcolor": TRANSPARENT,
                        "radialaxis": {
                            "gridcolor": "#506784",
                            "linecolor": "#506784",
                            "ticks": "",
                        },
                    },
                    "scene": {
                        "xaxis": {
                            **scene_axis_dict,
                            "showspikes": False,
                        },
                        "yaxis": {
                            **scene_axis_dict,
                            "showspikes": False,
                        },
                        "zaxis": scene_axis_dict,
                        "bgcolor": TRANSPARENT,
                        "aspectmode": "auto",
                    },
                    "shapedefaults": {"line": {"color": "#f2f5fa"}},
                    "showlegend": True,
                    "sliderdefaults": {
                        "bgcolor": "#C8D4E3",
                        "bordercolor": TRANSPARENT,
                        "borderwidth": 1,
                        "tickwidth": 0,
                    },
                    "ternary": {
                        "aaxis": {
                            "gridcolor": "#506784",
                            "linecolor": "#506784",
                            "ticks": "",
                        },
                        "baxis": {
                            "gridcolor": "#506784",
                            "linecolor": "#506784",
                            "ticks": "",
                        },
                        "bgcolor": TRANSPARENT,
                        "caxis": {
                            "gridcolor": "#506784",
                            "linecolor": "#506784",
                            "ticks": "",
                        },
                    },
                    "title": {
                        "x": 0.5,
                        "pad": {"b": 40},
                        "font": {
                            "size": 28,
                        },
                        "yref": "paper",
                        "y": 1,
                        "yanchor": "bottom",
                    },
                    "updatemenudefaults": {
                        "bgcolor": "rgba(33, 67, 96, 0.4)",
                        "bordercolor": TRANSPARENT,
                        "borderwidth": 0,
                        "type": "buttons",
                        "x": 1,
                        "xanchor": "right",
                        "yanchor": "bottom",
                        "direction": "left",
                        "showactive": True,
                        "font": {
                            "size": 11,
                            "weight": 200,
                        },
                        "buttons": [
                            {
                                "args": ["type", "mesh3d"],
                                "label": "3D Bar",
                                "method": "restyle",
                                "name": "bar3d",
                            },
                        ],
                    },
                    "xaxis": axis_dict,
                    "yaxis": axis_dict,
                },
            }
        ),
    )
    register_template(
        "slides",
        template=go.layout.Template(
            layout={
                "width": 900,
                "height": 600,
                "autosize": False,
            }
        ),
    )
    register_template(
        "save",
        template=go.layout.Template(
            {
                "layout": {
                    "xaxis": save_axis_dict,
                    "yaxis": save_axis_dict,
                    "colorscale": {
                        "diverging": DIVERGENT_COLOURSCALE,
                        "sequential": CONTINUOUS_COLORSCALE,
                        "sequentialminus": CONTINUOUS_COLORSCALE,
                    },
                    "colorway": shuffled_colourscale,
                    "legend": {
                        "bgcolor": TRANSPARENT,
                    },
                }
            }
        ),
    )
    register_template(
        "save_white",
        template=go.layout.Template(
            {
                "layout": {
                    "paper_bgcolor": "rgba(255,255,255,1)",
                    "plot_bgcolor": "rgba(255,255,255,1)",
                }
            }
        ),
    )
    register_template(
        "business_compliant",
        template=go.layout.Template(
            {
                "layout": {
                    "font": {
                        "family": '"Mona Sans", "CMU Serif", "Monaspace Neon", "Open Sans", verdana, arial, sans-serif',
                    },
                }
            }
        ),
    )

    set_template()


def get_layout_value(
    layout: go.Layout,
    /,
    *,
    props: Sequence[str],
) -> object | None:
    """
    Retrieve a nested property from a Plotly layout by attribute chain.

    Walks *props* from left to right, calling ``getattr`` at each level.
    Returns ``None`` as soon as any intermediate attribute is missing.

    Parameters
    ----------
    layout
        The ``go.Layout`` instance to inspect.
    props
        Ordered sequence of attribute names forming the property path
        (e.g. ``["xaxis", "title", "text"]``).

    Returns
    -------
    object | None
        The value found at the end of the chain, or ``None`` if any
        intermediate attribute does not exist.

    Raises
    ------
    ValueError
        If *props* is empty.

    See Also
    --------
    get_template_layout : Extract the layout object from a template.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.templates import (
    ...     get_layout_value,
    ...     get_template,
    ...     get_template_layout,
    ... )
    >>> layout = get_template_layout(get_template())  # doctest: +SKIP
    >>> get_layout_value(layout, props=["xaxis", "showgrid"])  # doctest: +SKIP
    True
    """
    if len(props) == 0:
        msg = "At least one layout property must be specified"
        raise ValueError(msg)

    current_value = layout
    for layout_prop in props:
        current_value = getattr(current_value, layout_prop, None)

    return current_value


def setup_plot_export(
    *,
    light: bool = True,
) -> None:
    """
    Configure Plotly for notebook export with a print-friendly template.

    Sets the renderer to ``plotly_mimetype+notebook`` and applies a light
    template suitable for static export.

    Parameters
    ----------
    light
        Whether to use the light-mode template. Defaults to ``True``.
        Dark mode is not yet supported.

    Raises
    ------
    NotImplementedError
        If ``light`` is ``False``.

    See Also
    --------
    set_template : Change the active default template.
    set_renderer : Change the active Plotly renderer.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.templates import setup_plot_export
    >>> setup_plot_export()  # doctest: +SKIP
    """
    set_renderer(renderer="plotly_mimetype+notebook")

    if light:
        set_template(template="base+plotly_white+save")
    else:
        msg = "Dark mode plot export not implemented yet."
        raise NotImplementedError(msg)


register_templates()
