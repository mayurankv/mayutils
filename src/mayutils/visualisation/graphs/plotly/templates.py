import plotly.graph_objects as go
import plotly.io as pio

from mayutils.objects.colours import (
    hex_to_rgba,
    BASE_COLOURSCALE,
    CONTINUOUS_COLORSCALE,
    DIVERGENT_COLOURSCALE,
)


TRANSPARENT = "rgba(0,0,0,0)"

axis_dict = dict(
    showgrid=True,
    gridwidth=2,
    zeroline=True,
    zerolinewidth=2,
    zerolinecolor="#283442",
    showline=True,
    mirror=True,
    gridcolor="#283442",
    linecolor="#506784",
    minor=dict(
        showgrid=True,
        gridcolor=hex_to_rgba(
            hex_colour=pio.templates["plotly_dark"].layout.xaxis.gridcolor,  # type: ignore
            alpha=0.4,
        ),
    ),
    title=dict(
        standoff=10,
        font=dict(
            size=16,
        ),
    ),
    tickfont=dict(
        size=12,
    ),
    ticklabelmode="period",
)
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
non_primary_axis_dict = {
    **axis_dict,
    "side": "right",
    "anchor": "x",
    "overlaying": "y",
    "showgrid": False,
    "tickmode": "auto",
    "zerolinewidth": 2,
    "minor": dict(
        showgrid=False,
    ),
}

shuffled_colourscale = [
    BASE_COLOURSCALE[i]
    for offset in range(4)
    for i in range(offset, len(BASE_COLOURSCALE), 4)
][::-1]

pio.templates["base"] = go.layout.Template(
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
            "choropleth": [
                {"colorbar": {"outlinewidth": 0, "ticks": ""}, "type": "choropleth"}
            ],
            "contour": [
                {
                    "colorbar": {"outlinewidth": 0, "ticks": ""},
                    "colorscale": CONTINUOUS_COLORSCALE,
                    "type": "contour",
                }
            ],
            "contourcarpet": [
                {"colorbar": {"outlinewidth": 0, "ticks": ""}, "type": "contourcarpet"}
            ],
            "heatmap": [
                {
                    "colorbar": {"outlinewidth": 0, "ticks": ""},
                    "colorscale": CONTINUOUS_COLORSCALE,
                    "type": "heatmap",
                    "hoverongaps": False,
                    "texttemplate": "%{z}",
                }
            ],
            # "heatmapgl": [
            #     {
            #         "colorbar": {"outlinewidth": 0, "ticks": ""},
            #         "colorscale": CONTINUOUS_COLORSCALE,
            #         "type": "heatmapgl",
            #     }
            # ],
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
            "mesh3d": [
                {"colorbar": {"outlinewidth": 0, "ticks": ""}, "type": "mesh3d"}
            ],
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
                        # "symbol": "x",
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
            "scattergl": [
                {"marker": {"line": {"color": "#283442"}}, "type": "scattergl"}
            ],
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
                "font": dict(
                    size=10,
                ),
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
                "pad": dict(b=40),
                "font": {
                    "size": 28,
                },
                "yref": "paper",
                "y": 1,
                "yanchor": "bottom",
            },
            "updatemenudefaults": {
                # "active_color": "#2a3f5f",
                "bgcolor": "rgba(33, 67, 96, 0.4)",
                "bordercolor": TRANSPARENT,
                "borderwidth": 0,
                "type": "buttons",
                "x": 1,
                "xanchor": "right",
                "yanchor": "bottom",
                "direction": "left",
                "showactive": True,
                "font": dict(
                    size=11,
                    weight=200,
                ),
                "buttons": [
                    dict(
                        args=["type", "mesh3d"],
                        label="3D Bar",
                        method="restyle",
                        name="bar3d",
                        # templateitemname="bar3d",
                    ),
                ],
            },
            "xaxis": axis_dict,
            "yaxis": axis_dict,
        },
    }
)
pio.templates["slides"] = go.layout.Template(
    layout=dict(
        width=900,
        height=600,
        autosize=False,
    )
)
save_axis_dict = dict(
    zerolinecolor="rgba(200,200,200,0.5)",
    gridcolor="rgba(200,200,200,0.3)",
    linecolor="rgba(200,200,200,0.5)",
    minor=dict(
        gridcolor="rgba(200,200,200,0.1)",
    ),
)
pio.templates["save"] = go.layout.Template(
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
)
pio.templates["business_compliant"] = go.layout.Template(
    {
        "layout": {
            "font": {
                "family": '"Mona Sans", "CMU Serif", "Monaspace Neon", "Open Sans", verdana, arial, sans-serif',
            },
        }
    }
)
pio.templates.default = "base"
pio.renderers.default = "vscode"
