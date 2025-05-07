import os
from math import isqrt, ceil
from typing import Literal, Optional, Self, final
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd
from pandas import DataFrame
import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.stats import gaussian_kde, norm

import plotly.graph_objects as go
from plotly.basedatatypes import BaseTraceType as Trace
import plotly.io as pio
from plotly.subplots import make_subplots
from plotly._subplots import _build_subplot_title_annotations
import pymupdf
from PIL import Image

from mayutils.core.constants import (
    DISPLAY_TYPE_ENV_VAR,
)
from mayutils.objects.colours import Colour, hex_to_rgba

from mayutils.objects.functions import null, set_inline
from mayutils.export import OUTPUT_FOLDER

IMAGES_FOLDER = OUTPUT_FOLDER / "Images"

TRANSPARENT = "rgba(0,0,0,0)"
BASE_COLOURSCALE = [
    "#EF553B",  # Red
    "#FF6692",  # Reddish-pink
    "#FF97FF",  # Pink
    "#FF85FF",  # Bright pink
    "#FFCCFF",  # Light pink
    "#FFA15A",  # Orange
    "#FFBD8E",  # Peach
    "#FECB52",  # Yellow-orange
    "#FFE989",  # Yellow
    "#B6E880",  # Yellow-green
    "#3BDB5F",  # Green
    "#00cc96",  # Teal
    "#73DBB6",  # Mint
    "#30D5DB",  # Light cyan
    "#19d3f3",  # Cyan
    "#636efa",  # Blue
    "#9299FD",  # Blue-violet
    "#ab63fa",  # Violet
    "#C592FD",  # Lavender
]
CONTINUOUS_COLORSCALE = [
    [0.0, "#0d0887"],
    [0.1111111111111111, "#46039f"],
    [0.2222222222222222, "#7201a8"],
    [0.3333333333333333, "#9c179e"],
    [0.4444444444444444, "#bd3786"],
    [0.5555555555555556, "#d8576b"],
    [0.6666666666666666, "#ed7953"],
    [0.7777777777777778, "#fb9f3a"],
    [0.8888888888888888, "#fdca26"],
    [1.0, "#f0f921"],
]
DIVERGENT_COLOURSCALE = [
    [0, "#8e0152"],
    [0.1, "#c51b7d"],
    [0.2, "#de77ae"],
    [0.3, "#f1b6da"],
    [0.4, "#fde0ef"],
    [0.5, "#f7f7f7"],
    [0.6, "#e6f5d0"],
    [0.7, "#b8e186"],
    [0.8, "#7fbc41"],
    [0.9, "#4d9221"],
    [1, "#276419"],
]

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
            "heatmapgl": [
                {
                    "colorbar": {"outlinewidth": 0, "ticks": ""},
                    "colorscale": CONTINUOUS_COLORSCALE,
                    "type": "heatmapgl",
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
                "family": '"SF Pro Rounded", "CMU Serif", "Monaspace Neon", "Open Sans", verdana, arial, sans-serif',
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
            },
            "mapbox": {
                "style": "dark",
            },
            "margin": {
                "l": 50,
                "b": 50,
                "t": 75,
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
pio.templates.default = "base"
pio.renderers.default = "vscode"


AxisConfig = dict


class Null(go.Scatter):
    def __init__(
        self,
        x_datetime: bool = False,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(
            x=[] if not x_datetime else pd.to_datetime([datetime.today()]),
            y=[],
            showlegend=False,
            meta="null",
            *args,
            **kwargs,
        )


class Line(go.Scatter):
    _counter = 0

    def __init__(
        self,
        label_name: bool | str = False,
        *args,
        **kwargs,
    ) -> None:
        mode: str = kwargs.pop("mode", "lines")
        mode += (
            "+text" if label_name is not False and not mode.endswith("+text") else ""
        )
        kwargs["mode"] = mode

        label_name = (
            kwargs.get("name", None) if label_name is True else label_name
        ) or ""
        kwargs["text"] = [""] * (len(kwargs.get("x", [])) - 1) + [label_name]

        super().__init__(
            meta="line",
            *args,
            **kwargs,
        )

        type(self)._counter += 1
        self._count = type(self)._counter

    @classmethod
    def with_bounds(
        cls,
        x: ArrayLike,
        y: ArrayLike,
        y_upper: list[ArrayLike],
        y_lower: list[ArrayLike],
        max_opacity: float = 0.4,
        *args,
        **kwargs,
    ) -> tuple[Self, ...]:
        if len(y_lower) != len(y_upper):
            raise ValueError("Asymmetric bounds provided")
        last_lower = np.asarray(y)
        last_upper = last_lower
        for lower, upper in zip(y_lower, y_upper):
            if len(lower) != len(y) or len(upper) != len(y):  # type: ignore
                raise ValueError("Y Values of different length provided")
            elif np.any(np.asarray(lower) > last_lower) or np.any(
                np.asarray(upper) < last_upper
            ):
                raise ValueError("Monotonic bounds not passed")

            last_lower = lower
            last_upper = upper

        base_trace = cls(
            x=x,
            y=y,
            line=kwargs.pop("line", {}),
            *[*args],
            **{**kwargs},
        )
        legendgroup = kwargs.pop("legendgroup", f"bounds{base_trace._count}")
        base_trace.legendgroup = legendgroup

        # TODO: Set colour
        color_str = base_trace.line.color or "black"  # type: ignore
        color = Colour.parse(colour=color_str)
        return (
            *[
                cls(
                    x=np.concatenate([x, x[::-1]]),  # type: ignore
                    y=np.concatenate([upper, lower[::-1]]),  # type: ignore
                    fill="toself",
                    showlegend=False,
                    fillcolor=color.to_str(opacity=max_opacity / (1 + len(y_upper))),
                    line=dict(color=color.to_str(opacity=0)),
                    legendgroup=legendgroup,
                    hoverinfo="skip",
                    *[*args],
                    **{
                        key: value
                        for key, value in kwargs.items()
                        if key != "line_color"
                    },
                )
                for lower, upper in zip(y_lower, y_upper)
            ],
            base_trace,
        )

    @classmethod
    def from_bounds_dataframe(
        cls,
        df: DataFrame,
        *args,
        **kwargs,
    ) -> tuple[Self, ...]:
        # TODO: Complete
        raise NotImplementedError("Method incomplete")


class Scatter(go.Scatter):
    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(
            mode="markers",
            meta="scatter",
            *args,
            **kwargs,
        )


class Cuboid(go.Mesh3d):
    def __init__(
        self,
        x: tuple[float, float],
        y: tuple[float, float],
        z: tuple[float, float],
        weight: float = 1,
        flatshading: bool = True,
        showscale: bool = False,
        alphahull: float = 1,
        cmin: float = 0,
        cmax: float = 1,
        *args,
        **kwargs,
    ) -> None:
        x0, x1 = x
        y0, y1 = y
        z0, z1 = z

        super().__init__(
            x=[x0, x0, x1, x1, x0, x0, x1, x1],
            y=[y0, y1, y1, y0, y0, y1, y1, y0],
            z=[z0, z0, z0, z0, z1, z1, z1, z1],
            i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
            j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
            k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
            intensity=[weight for _ in range(8)],
            cmin=cmin,
            cmax=cmax,
            alphahull=alphahull,
            flatshading=flatshading,
            showscale=showscale,
            *args,
            **kwargs,
        )


class Bar3d(go.Mesh3d):
    def __init__(
        self,
        x: ArrayLike,
        y: ArrayLike,
        z: ArrayLike,
        w: Optional[ArrayLike] = None,
        showscale: bool = True,
        alphahull: float = 1,
        flatshading: bool = True,
        dx: float = 1,
        dy: float = 1,
        z0: float = 0,
        x_start: float = 0,
        y_start: float = 0,
        z_start: float = 0,
        x_mapping: Optional[ArrayLike] = None,
        y_mapping: Optional[ArrayLike] = None,
        *args,
        **kwargs,
    ) -> None:
        x_arr = np.asarray(x)
        y_arr = np.asarray(y)
        z_arr = np.asarray(z, dtype=np.float64)
        w_arr = (
            np.asarray(w, dtype=np.float64)
            if w is not None
            else np.ones(z_arr.shape, dtype=np.float64)
        )

        if any(len(arr) != len(w_arr) for arr in [x_arr, y_arr, z_arr]):
            raise ValueError("Input arrays are not same length")

        nan_idxs = np.isnan(z_arr)
        self._x_arr = x_arr[~nan_idxs]
        self._y_arr = y_arr[~nan_idxs]
        self._z_arr = z_arr[~nan_idxs]
        self._w_arr = w_arr[~nan_idxs]

        x_arr_numerical = (
            map_categorical_array(
                arr=self._x_arr,
                mapping=x_mapping,
            )
            * dx
        )
        self._x = (
            np.stack([x_arr_numerical - dx / 2, x_arr_numerical + dx / 2], axis=1)[
                np.arange(x_arr_numerical.size)[:, None], [0, 0, 1, 1, 0, 0, 1, 1]
            ].reshape(-1)
            + x_start
        )
        y_arr_numerical = (
            map_categorical_array(
                arr=self._y_arr,
                mapping=y_mapping,
            )
            * dy
        )
        self._y = (
            np.stack([y_arr_numerical - dy / 2, y_arr_numerical + dy / 2], axis=1)[
                np.arange(y_arr_numerical.size)[:, None], [0, 1, 1, 0, 0, 1, 1, 0]
            ].reshape(-1)
            + y_start
        )
        self._z = np.ones(self._z_arr.size * 8, dtype=self._z_arr.dtype) * z0
        self._z[(np.arange(self._z_arr.size) * 8)[:, None] + np.array([4, 5, 6, 7])] = (
            self._z_arr[:, None]
        )
        self._z += z_start
        self._w = np.repeat(
            self._w_arr,
            repeats=8,
        )

        i = (
            np.tile([7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2], (len(self._x_arr), 1))
            + np.arange(len(self._x_arr))[:, np.newaxis] * 8
        ).flatten()
        j = (
            np.tile([3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3], (len(self._x_arr), 1))
            + np.arange(len(self._x_arr))[:, np.newaxis] * 8
        ).flatten()
        k = (
            np.tile([0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6], (len(self._x_arr), 1))
            + np.arange(len(self._x_arr))[:, np.newaxis] * 8
        ).flatten()

        return super().__init__(
            x=self._x,
            y=self._y,
            z=self._z,
            intensity=self._w,
            i=i,
            j=j,
            k=k,
            showscale=showscale,
            alphahull=alphahull,
            flatshading=flatshading,
            hovertemplate="x: %{customdata[0]}<br>"
            "y: %{customdata[1]}<br>"
            "z: %{customdata[2]:.2f}<br>"
            "w: %{customdata[3]:.2f}<extra></extra>",
            customdata=np.stack(
                [
                    np.repeat(self._x_arr, repeats=8),
                    np.repeat(self._y_arr, repeats=8),
                    np.repeat(self._z[8 - 1 :: 8], repeats=8),
                    self._w,
                ],
                axis=1,
            ),
            meta="bar3d",
            *args,
            **kwargs,
        )

    @classmethod
    def from_dataframe(
        cls,
        df: DataFrame,
        value_weights: bool = False,
        x_mapping: Optional[ArrayLike] = None,
        y_mapping: Optional[ArrayLike] = None,
        *args,
        **kwargs,
    ) -> Self:
        if not df.columns.is_unique:
            raise ValueError("Dataframe columns are not unique")
        elif not df.index.is_unique:
            raise ValueError("Dataframe index is not unique")

        x, y, z = melt_dataframe(
            df.loc[  # type: ignore
                x_mapping if x_mapping is not None else slice(None),
                y_mapping if y_mapping is not None else slice(None),
            ]
        )

        return cls(
            x=x,
            y=y,
            z=z,
            w=z if value_weights else kwargs.pop("w", None),
            *args,
            **kwargs,
        )


@dataclass
class TracesConfig:
    traces: tuple[Trace, ...]
    yaxis_config: AxisConfig = field(default_factory=AxisConfig)

    @classmethod
    def from_trace(
        cls,
        trace: Trace,
        yaxis_config: AxisConfig = AxisConfig(),
    ) -> "TracesConfig":
        return cls(
            traces=(trace,),
            yaxis_config=yaxis_config,
        )


@dataclass
class PlotConfig:
    yaxes_configs: tuple[TracesConfig, ...]
    xaxis_config: AxisConfig = field(default_factory=AxisConfig)

    @classmethod
    def empty(
        cls,
    ) -> "PlotConfig":
        return cls(
            yaxes_configs=tuple(),
            xaxis_config=AxisConfig(),
        )

    @classmethod
    def from_trace(
        cls,
        trace: Trace,
        yaxis_config: AxisConfig = AxisConfig(),
        xaxis_config: AxisConfig = AxisConfig(),
    ) -> "PlotConfig":
        return cls(
            yaxes_configs=(
                TracesConfig.from_trace(
                    trace=trace,
                    yaxis_config=yaxis_config,
                ),
            ),
            xaxis_config=xaxis_config,
        )

    @classmethod
    def from_traces(
        cls,
        *traces: Trace,
        yaxis_config: AxisConfig = AxisConfig(),
        xaxis_config: AxisConfig = AxisConfig(),
    ) -> "PlotConfig":
        return cls(
            yaxes_configs=(
                TracesConfig(
                    traces=traces,
                    yaxis_config=yaxis_config,
                ),
            ),
            xaxis_config=xaxis_config,
        )


@dataclass
class Titles:
    main: str = ""
    rows: Optional[tuple[str, ...]] = None
    cols: Optional[tuple[str, ...]] = None
    plots: Optional[tuple[tuple[Optional[str], ...], ...]] = None

    def __post_init__(
        self,
    ) -> None:
        self.main = self.main.replace("\n", "<br>")
        self.rows = (
            self.rows
            if self.rows is None
            else tuple(row.replace("\n", "<br>") for row in self.rows)
        )
        self.cols = (
            self.cols
            if self.cols is None
            else tuple(col.replace("\n", "<br>") for col in self.cols)
        )
        self.plots = (
            self.plots
            if self.plots is None
            else tuple(
                tuple(
                    plot_title.replace("\n", "<br>") if plot_title is not None else ""
                    for plot_title in row_titles
                )
                for row_titles in self.plots
            )
        )


@dataclass
class MainAxisConfig:
    config: AxisConfig = field(default_factory=AxisConfig)
    mode: Literal["independent", "shared", "collapsed"] = "collapsed"

    @classmethod
    def from_dict(
        cls,
        *args,
        **kwargs,
    ) -> Self:
        return cls(
            config=dict(
                *args,
                **kwargs,
            ),
        )


@dataclass
class MainAxisConfigs:
    xaxis: MainAxisConfig = field(default_factory=MainAxisConfig)
    yaxes: tuple[MainAxisConfig, ...] = tuple()


@dataclass
class SubPlotConfig:
    plots: tuple[tuple[Optional[PlotConfig], ...], ...]
    main_axis_configs: MainAxisConfigs = field(default_factory=MainAxisConfigs)
    titles: Titles = field(default_factory=Titles)

    def __post_init__(
        self,
    ) -> None:
        if len(self.plots) == 0:
            raise ValueError("Plots is empty")
        elif any(len(self.plots[0]) != len(row) for row in self.plots[1:]):
            raise ValueError("Subplot layout has inconsistent row lengths")
        elif self.titles.rows is not None and len(self.titles.rows) != len(self.plots):
            raise ValueError(
                f"Row titles are of length {len(self.titles.rows)} whilst plots have {len(self.plots)} rows"
            )
        elif self.titles.cols is not None and len(self.titles.cols) != len(
            self.plots[0]
        ):
            raise ValueError(
                f"Column titles are of length {len(self.titles.cols)} whilst plots have {len(self.plots[0])} columns"
            )
        elif self.titles.plots is not None and len(self.titles.plots) != len(
            self.plots
        ):
            raise ValueError(
                f"Subplot titles have {len(self.titles.plots)} rows whilst there are {len(self.plots)} subplot rows"
            )
        elif self.titles.plots is not None and len(self.titles.plots[0]) != len(
            self.plots[0]
        ):
            raise ValueError(
                f"Subplot titles have {len(self.titles.plots[0])} columns whilst there are {len(self.plots[0])} subplot columns"
            )

        if self.titles.plots is None:
            self.titles.plots = tuple(
                tuple("" for _ in range(len(self.plots[0])))
                for _ in range(len(self.plots))
            )

        max_yaxis = max(
            len(plot_config.yaxes_configs) if plot_config is not None else 0
            for row_plot_configs in self.plots
            for plot_config in row_plot_configs
        )
        self.main_axis_configs.yaxes = (
            self.main_axis_configs.yaxes
            + tuple(MainAxisConfig() for _ in range(max_yaxis))
        )[:max_yaxis]

    @classmethod
    def flat(
        cls,
        plots: tuple[Optional[PlotConfig], ...],
        cols: Optional[int],
        *args,
        **kwargs,
    ) -> "SubPlotConfig":
        if cols is None:
            cols = isqrt(len(plots) - 1) + 1

        rows = ceil(len(plots) / cols)

        extended_plots = list(plots) + [None] * (cols * rows - len(plots))

        return cls(
            plots=tuple(
                tuple(extended_plots[idx : idx + cols])
                for idx in range(0, len(extended_plots), cols)
            ),
            *args,
            **kwargs,
        )


class Plot(go.Figure):
    def __init__(
        self,
        description: str,
        plot_config: PlotConfig,
        layout: dict = {},
        *args,
        **kwargs,
    ) -> None:
        self._description = description
        self._display_type = os.getenv(key=DISPLAY_TYPE_ENV_VAR, default=None)

        super().__init__(
            *args,
            layout=layout,
            **kwargs,
        )

        self.update_layout(
            xaxis=plot_config.xaxis_config,
        )
        max_yaxis = len(plot_config.yaxes_configs)
        if max_yaxis >= 2:
            self.update_layout({"yaxis2": non_primary_axis_dict})
        if max_yaxis > 2:
            self.update_layout(
                xaxis=dict(
                    domain=[
                        0,
                        get_domain_fraction(
                            axis_idx=1,
                            max_yaxis=max_yaxis,
                        ),
                    ]
                ),
            )
            for axis_idx in range(2, max_yaxis):
                self.update_layout(
                    {
                        f"yaxis{axis_idx + 1}": {
                            **non_primary_axis_dict,
                            "anchor": "free",
                        }
                    }
                )

        for axis_idx, traces_config in enumerate(plot_config.yaxes_configs):
            yaxis = f"yaxis{'' if axis_idx == 0 else str(axis_idx + 1)}"
            self.update_layout(
                {yaxis: traces_config.yaxis_config},
            )

            try:
                if axis_idx != 0:
                    axis_title: str = getattr(getattr(self.layout, yaxis).title, "text")

                    self.add_title(
                        title=axis_title,
                        x_domain=(0, 1 - (max_yaxis - axis_idx - 1) * 0.1),
                    )
                    setattr(
                        getattr(self.layout, yaxis).title,
                        "text",
                        "",
                    )
                    setattr(
                        getattr(self.layout, yaxis),
                        "position",
                        get_domain_fraction(
                            axis_idx=axis_idx,
                            max_yaxis=max_yaxis,
                        ),
                    )
            except AttributeError:
                pass

            for trace in traces_config.traces:
                if not is_trace_3d(trace):
                    trace.yaxis = yaxis.replace("yaxis", "y")
                self.add_trace(
                    trace=trace,
                )

        try:
            self.layout.title.text = self.layout.title.text.replace("\n", "<br>")  # type: ignore
        except AttributeError:
            pass

        self.modifications()

    @classmethod
    def from_traces(
        cls,
        *traces: Trace,
        description: str,
        xaxis_config: AxisConfig = AxisConfig(),
        yaxis_config: AxisConfig = AxisConfig(),
        **kwargs,
    ) -> Self:
        return cls(
            description,
            PlotConfig.from_traces(
                *traces,
                yaxis_config=yaxis_config,
                xaxis_config=xaxis_config,
            ),
            **kwargs,
        )

    @classmethod
    def from_figure(
        cls,
        fig: go.Figure,
        description: str,
    ) -> Self:
        return cls(
            description,
            PlotConfig.empty(),
            {},
            fig,
        )

    @classmethod
    def from_existing(
        cls,
        plot: "Plot",
        description: str,
    ) -> Self:
        return cls.from_figure(
            fig=plot,
            description=description,
        )

    @classmethod
    def empty(
        cls,
        description: str,
    ) -> Self:
        return cls(
            description=description,
            plot_config=PlotConfig.empty(),
        )

    def to_figure(
        self,
    ) -> go.Figure:
        return go.Figure(data=self)

    def add_trace(
        self,
        trace,
        *args,
        **kwargs,
    ) -> Self:
        super().add_trace(
            trace=trace,
            *args,
            **kwargs,
        )

        return self

    def update_layout(
        self,
        *args,
        **kwargs,
    ) -> Self:
        super().update_layout(
            *args,
            **kwargs,
        )

        return self

    def add_title(
        self,
        title: str,
        edge: Literal["left", "right", "top", "bottom"] = "right",
        offset: float = 30,
        x_domain: tuple[float, float] = (0, 1),
        y_domain: tuple[float, float] = (0, 1),
        *args,
        **kwargs,
    ) -> Self:
        annotations = _build_subplot_title_annotations(
            subplot_titles=[title],
            list_of_domains=[x_domain, y_domain],
            title_edge=edge,
            offset=offset,  # type: ignore
        )

        for annotation in annotations:
            self.add_annotation(
                *args,
                **{
                    **annotation,
                    **kwargs,
                },
            )

        return self

    def shift_title(
        self,
        offset: int,
    ) -> Self:
        self.update_layout(
            margin_t=(
                self.layout.margin.t  # type: ignore
                or pio.templates[pio.templates.default].layout.margin.t  # type: ignore
            )
            + offset,
            title_pad_b=(
                self.layout.title.pad.b  # type: ignore
                or pio.templates[pio.templates.default].layout.title.pad.b  # type: ignore
            )
            + offset,
        )

        return self

    def show(
        self,
        show: bool = True,
        layout: dict = {},
        *args,
        **kwargs,
    ) -> None:
        if show:
            layout = {
                **layout,
                **(
                    {}
                    if self._display_type != "slides"
                    else dict(height=600, width=900)
                ),
            }
            super(Plot, self.copy().update_layout(layout)).show(
                config=dict(
                    showTips=False,
                    displaylogo=False,
                    displayModeBar=(
                        "hover" if not self._display_type == "slides" else False
                    ),
                ),
                *args,
                **kwargs,
            )

        return None

    def copy(
        self,
        description: Optional[str] = None,
    ) -> "Plot":
        return Plot.from_existing(
            plot=self,
            description=description or self._description,
        )

    def save(
        self,
        filename: str,
        image_formats: list[str] = ["png"],  # ["png", "jpeg", "pdf"]
        scale: Optional[int] = 5,
        save: bool = True,
        *args,
        **kwargs,
    ) -> None:
        if save:
            for image_format in image_formats:
                self.copy().update_layout(
                    paper_bgcolor="rgba(255,255,255,1)",
                    plot_bgcolor="rgba(255,255,255,1)",
                    template="plotly_white",
                ).write_image(
                    file=IMAGES_FOLDER / f"{filename}.{image_format}",
                    format=image_format,
                    scale=scale,
                    *args,
                    **kwargs,
                )

    def modifications(
        self,
    ) -> Self:
        for idx, trace in enumerate(self.data):
            if isinstance(trace, go.Histogram):
                trace.marker.line.color = (  # type: ignore
                    trace.marker.color  # type: ignore
                    or shuffled_colourscale[idx % len(shuffled_colourscale)]
                )
            elif trace.meta == "line":
                trace.textfont.color = (
                    trace.line.color
                    or shuffled_colourscale[idx % len(shuffled_colourscale)]
                )

        bound_groups = {}
        for idx, trace in enumerate(self.data):
            if trace.legendgroup and trace.legendgroup.startswith("bounds"):
                if trace.legendgroup not in bound_groups:
                    bound_groups[trace.legendgroup] = [None, []]

                if trace.fill == "toself":
                    bound_groups[trace.legendgroup][1].append(trace)
                else:
                    bound_groups[trace.legendgroup][0] = (trace.line.color, idx)

        for (line_colour, idx), bound_traces in bound_groups.values():
            if line_colour is None:
                colour = Colour.parse(
                    colour=shuffled_colourscale[idx % len(shuffled_colourscale)]
                )

                opacity = Colour.parse(colour=bound_traces[0].fillcolor).a
                for bound_trace in bound_traces:
                    bound_trace.fillcolor = colour.to_str(
                        opacity=opacity,  # type: ignore
                    )

        return self

    def add_histogram_gaussians(
        self,
        *args,
        **kwargs,
    ) -> Self:
        for idx, trace in enumerate(self.data):
            if isinstance(trace, go.Histogram):
                self.add_trace(
                    trace=Line(
                        x=(
                            gaussian_x := np.linspace(
                                min(self.data[idx].x),  # type: ignore
                                max(self.data[idx].x),  # type: ignore
                                500,
                            )
                        ),
                        y=norm.pdf(
                            gaussian_x,
                            loc=(fit := norm.fit(self.data[idx].x))[0],  # type: ignore
                            scale=fit[1],
                        ),
                        line=dict(
                            color=self.data[idx].marker.line.color,  # type: ignore
                            width=0.8,
                            dash="dash",
                        ),
                        opacity=0.9,
                        name=(
                            (self.data[idx].name + " Gaussian")  # type: ignore
                            if self.data[idx].name  # type: ignore
                            else f"trace {idx} Gaussian"
                        ),
                        xaxis=self.data[idx].xaxis,  # type: ignore
                        yaxis=self.data[idx].yaxis,  # type: ignore
                        legendgroup=self.data[idx].legendgroup  # type: ignore
                        or null(set_inline(self.data[idx], "legendgroup", idx))
                        or idx,
                        showlegend=False,
                        label_name=False,
                    )
                )

        return self

    @final
    def add_rug(
        self,
        rug_type: Literal["scatter", "violin", "box", "strip"] = "scatter",
        *args,
        **kwargs,
    ) -> Self:
        if getattr(self, "_added_rugs", False):
            return self

        hist_count = 0
        traces = []
        for idx, trace in enumerate(self.data):
            if isinstance(trace, go.Histogram):
                hist_count += 1
                if rug_type == "scatter":
                    traces.append(
                        go.Scatter(
                            x=self.data[idx].x,  # type: ignore
                            y=([hist_count] * len(self.data[idx].x)),  # type: ignore
                            xaxis="x1",
                            yaxis="y2",
                            mode="markers",
                            name=(
                                (self.data[idx].name + " Rug")  # type: ignore
                                if self.data[idx].name  # type: ignore
                                else f"trace {idx} Rug"
                            ),
                            legendgroup=self.data[idx].legendgroup  # type: ignore
                            or null(set_inline(self.data[idx], "legendgroup", idx))
                            or idx,
                            showlegend=False,
                            marker=dict(
                                color=self.data[idx].marker.line.color,  # type: ignore
                                symbol="line-ns-open",
                            ),
                            *args,
                            **kwargs,
                        )
                    )
                elif rug_type == "box":
                    traces.append(
                        # TODO: Different rug types
                        go.Box(
                            x=self.data[idx].x,  # type: ignore
                            y=([hist_count] * len(self.data[idx].x)),  # type: ignore
                            xaxis="x1",
                            yaxis="y2",
                            orientation="h",
                            name=(
                                (self.data[idx].name + " Rug")  # type: ignore
                                if self.data[idx].name  # type: ignore
                                else f"trace {idx} Rug"
                            ),
                            legendgroup=self.data[idx].legendgroup  # type: ignore
                            or null(set_inline(self.data[idx], "legendgroup", idx))
                            or idx,
                            showlegend=False,
                            line=dict(
                                color=TRANSPARENT,
                            ),
                            fillcolor=TRANSPARENT,
                            marker=dict(
                                color=self.data[idx].marker.line.color,  # type: ignore
                                size=4,
                            ),
                            notched=True,
                            boxpoints="all",
                            hoveron="points",
                            width=0.6,
                            opacity=0.6,
                            jitter=0.6,
                            pointpos=0,
                            *args,
                            **kwargs,
                        )
                    )
                elif rug_type == "strip":
                    traces.append(
                        # TODO: Different rug types
                        go.Box(
                            x=self.data[idx].x,  # type: ignore
                            y=([hist_count] * len(self.data[idx].x)),  # type: ignore
                            xaxis="x1",
                            yaxis="y2",
                            orientation="h",
                            name=(
                                (self.data[idx].name + " Rug")  # type: ignore
                                if self.data[idx].name  # type: ignore
                                else f"trace {idx} Rug"
                            ),
                            legendgroup=self.data[idx].legendgroup  # type: ignore
                            or null(set_inline(self.data[idx], "legendgroup", idx))
                            or idx,
                            showlegend=False,
                            line=dict(
                                color=self.data[idx].marker.line.color,  # type: ignore
                            ),
                            marker=dict(
                                color=self.data[idx].marker.line.color,  # type: ignore
                                size=4,
                            ),
                            notched=True,
                            boxpoints=kwargs.pop(
                                "points", kwargs.pop("boxpoints", "suspectedoutliers")
                            ),
                            width=0.4,
                            opacity=0.6,
                            jitter=0.6,
                            *args,
                            **kwargs,
                        )
                    )
                elif rug_type == "violin":
                    traces.append(
                        go.Violin(
                            x=self.data[idx].x,  # type: ignore
                            y=([hist_count] * len(self.data[idx].x)),  # type: ignore
                            xaxis="x1",
                            yaxis="y2",
                            orientation="h",
                            name=(
                                (self.data[idx].name + " Rug")  # type: ignore
                                if self.data[idx].name  # type: ignore
                                else f"trace {idx} Rug"
                            ),
                            legendgroup=self.data[idx].legendgroup  # type: ignore
                            or null(set_inline(self.data[idx], "legendgroup", idx))
                            or idx,
                            showlegend=False,
                            line=dict(
                                color=self.data[idx].marker.line.color,  # type: ignore
                            ),
                            marker=dict(
                                color=self.data[idx].marker.line.color,  # type: ignore
                                size=5,
                            ),
                            scalegroup="histogram_added_rug",
                            points=kwargs.pop("points", "suspectedoutliers"),
                            opacity=0.6,
                            jitter=0.6,
                            width=1,
                            side="positive",
                            *args,
                            **kwargs,
                        )
                    )
                else:
                    raise ValueError(f"Rug type {rug_type} is unknown")

        height = 0.15 if rug_type == "scatter" else 0.3
        if hist_count > 0:
            self.update_layout(
                yaxis1=dict(
                    domain=[height + 0.1, 1],
                ),
                yaxis2=dict(
                    anchor="x1",
                    dtick=1,
                    showticklabels=False,
                    domain=[0, height],
                    fixedrange=True,
                    showline=True,
                    showgrid=False,
                    minor=dict(showgrid=False),
                ),
            )

            for trace in traces:
                self.add_trace(trace=trace)

        self._added_rugs = True

        return self

    def add_defaults(
        self,
        **kwargs,
    ) -> Self:
        plot_types = {
            plot_name: [
                isinstance(trace, plot_class)
                or (
                    (trace.meta == plot_name)  # type: ignore
                    and (plot_name in ["bar3d", "null", "scatter"])
                )
                for trace in self.data
            ]
            for plot_name, plot_class in {
                "bar3d": Bar3d,
                "null": Null,
                "scatter": Scatter,
                "histogram": go.Histogram,
            }.items()
        }
        scatter_density_bins = kwargs.pop("scatter_density_bins", (None, None))
        additions = {
            "scatter": {
                "traces": [
                    go.Histogram2d(
                        x=np.concatenate([trace.x for trace in traces]),
                        y=np.concatenate([trace.y for trace in traces]),
                        xaxis=xaxis,
                        yaxis=yaxis,
                        bingroup=99,
                        opacity=0.5,
                        hoverinfo="skip",
                        coloraxis="coloraxis99",
                        nbinsx=scatter_density_bins[0],
                        nbinsy=scatter_density_bins[1],
                        showlegend=False,
                        visible=False,
                    )
                    for (xaxis, yaxis), traces in sort_traces_by_axes(
                        traces=[  # type: ignore
                            self.data[idx]
                            for idx, include in enumerate(
                                plot_types["scatter"],
                            )
                            if include
                        ]
                    ).items()
                ],
                "layout": dict(
                    coloraxis99=dict(
                        colorscale=[
                            [0.0, "rgba(255, 0, 0, 0.0)"],
                            [0.1, "rgba(255, 0, 0, 0.1)"],
                            [0.2, "rgba(255, 0, 0, 0.2)"],
                            [0.5, "rgba(255, 0, 0, 0.5)"],
                            [1.0, "rgba(255, 0, 0, 1.0)"],
                        ],
                        colorbar=dict(title_text="Density"),
                    )
                ),
            },
            "histogram": {
                "traces": [
                    Line(
                        x=(
                            kde_x := np.linspace(
                                min(self.data[idx].x),  # type: ignore
                                max(self.data[idx].x),  # type: ignore
                                500,
                            )
                        ),
                        y=gaussian_kde(self.data[idx].x)(kde_x),  # type: ignore
                        line=dict(
                            color=self.data[idx].marker.line.color,  # type: ignore
                            width=0.8,
                        ),
                        opacity=0.9,
                        name=(
                            (self.data[idx].name + " KDE")  # type: ignore
                            if self.data[idx].name  # type: ignore
                            else f"trace {idx} KDE"
                        ),
                        xaxis=self.data[idx].xaxis,  # type: ignore
                        yaxis=self.data[idx].yaxis,  # type: ignore
                        legendgroup=self.data[idx].legendgroup  # type: ignore
                        or null(set_inline(self.data[idx], "legendgroup", idx))
                        or idx,
                        showlegend=False,
                        label_name=False,
                    )
                    for idx, include in enumerate(
                        plot_types["histogram"],
                    )
                    if include
                ],
                "layout": dict(),
            },
        }
        buttons = {
            "scatter": [
                dict(
                    label="Toggle Density",
                    method="restyle",
                    args=[
                        {"visible": True},
                        [
                            offset + idx
                            for idx in range(len(additions["scatter"]["traces"]))
                            if (
                                offset := len(self.data)  # type: ignore
                                + sum(
                                    len(v["traces"])
                                    for k, v in additions.items()
                                    if k != "scatter"
                                    and list(additions).index(k)
                                    < list(additions).index("scatter")
                                )
                            )
                        ],
                    ],
                    args2=[
                        {"visible": False},
                        [
                            offset + idx
                            for idx in range(len(additions["scatter"]["traces"]))
                            if offset
                        ],
                    ],
                ),
            ],
            "histogram": [],
            "bar3d": [
                dict(
                    label="3D Bar",
                    method="restyle",
                    args=[
                        {
                            "type": [
                                "mesh3d" if plot_types["bar3d"][trace_idx] else None
                                for trace_idx in range(len(self.data))  # type: ignore
                            ],
                            "x": [
                                self.data[trace_idx].x  # type: ignore
                                if plot_types["bar3d"][trace_idx]
                                else None
                                for trace_idx in range(len(self.data))  # type: ignore
                            ],
                            "y": [
                                self.data[trace_idx].y  # type: ignore
                                if plot_types["bar3d"][trace_idx]
                                else None
                                for trace_idx in range(len(self.data))  # type: ignore
                            ],
                            "z": [
                                self.data[trace_idx].z  # type: ignore
                                if plot_types["bar3d"][trace_idx]
                                else None
                                for trace_idx in range(len(self.data))  # type: ignore
                            ],
                        },
                    ],
                ),
                dict(
                    label="Heatmap",
                    method="restyle",
                    args=[
                        {
                            "type": [
                                "heatmap" if plot_types["bar3d"][trace_idx] else None
                                for trace_idx in range(len(self.data))  # type: ignore
                            ],
                            "x": [
                                self.data[trace_idx].customdata[::8, 0]  # type: ignore
                                if plot_types["bar3d"][trace_idx]
                                else None
                                for trace_idx in range(len(self.data))  # type: ignore
                            ],
                            "y": [
                                self.data[trace_idx].customdata[::8, 1]  # type: ignore
                                if plot_types["bar3d"][trace_idx]
                                else None
                                for trace_idx in range(len(self.data))  # type: ignore
                            ],
                            "z": [
                                self.data[trace_idx].customdata[::8, 2]  # type: ignore
                                if plot_types["bar3d"][trace_idx]
                                else None
                                for trace_idx in range(len(self.data))  # type: ignore
                            ],
                        },
                    ],
                ),
            ],
        }
        for addition in additions.values():
            for trace in addition["traces"]:
                self.add_trace(trace=trace)
            self.update_layout(addition["layout"])

        self.update_layout(
            updatemenus=[
                dict(
                    **kwargs,
                    buttons=[dict()]
                    + [
                        button
                        for plot_type, idxs in plot_types.items()
                        if any(idxs)
                        for button in buttons[plot_type]
                    ],
                )
            ]
        )

        return self

    def __call__(
        self,
        save: bool = True,
        show: bool = True,
    ) -> Self:
        self.save(
            filename=self._description,
            save=save,
        )
        self.show(
            show=show,
        )

        return self


class SubPlot(Plot):
    def __init__(
        self,
        description: str,
        subplot_config: SubPlotConfig,
        layout: dict = {},
        x_datetime: bool = False,
        x_spacing: dict[str, float] = {},
        y_spacing: dict[str, float] = {},
        line_title_offsets: tuple[float, float] = (22.5, 22.5),
        line_title_styles: dict = dict(
            font_weight=700,
            font_size=12,
        ),
        plot_title_styles: dict = dict(),
        fill_nulls: bool = True,
        *args,
        **kwargs,
    ) -> None:
        spacing = {
            "x": {
                "collapsed": 0.01,
                "shared": 0.06,
                "independent": 0.06,
                **x_spacing,
            },
            "y": {
                "collapsed": 0.025,
                "shared": 0.08,
                "independent": 0.08,
                **y_spacing,
            },
        }

        plot_count = len(subplot_config.plots) * len(subplot_config.plots[0])
        max_yaxis = max(
            len(plot_config.yaxes_configs) if plot_config is not None else 0
            for row_plot_configs in subplot_config.plots
            for plot_config in row_plot_configs
        )

        x_domains = get_domains(
            spacing=spacing["x"]["collapsed"]
            if all(
                yaxis_info.mode == "collapsed"
                for yaxis_info in subplot_config.main_axis_configs.yaxes
            )
            else (
                spacing["x"]["independent"]
                if any(
                    yaxis_info.mode == "independent"
                    for yaxis_info in subplot_config.main_axis_configs.yaxes
                )
                else spacing["x"]["shared"]
            )
            * (max_yaxis - 1),
            num_axes=len(subplot_config.plots[0]),
            fraction=get_domain_fraction(
                axis_idx=1,
                max_yaxis=max_yaxis,
            )
            if max_yaxis > 2
            else 1,
        )
        y_domains = get_domains(
            spacing=(
                spacing["y"]["collapsed"]
                if subplot_config.main_axis_configs.xaxis.mode == "collapsed"
                else (
                    spacing["y"]["independent"]
                    if subplot_config.main_axis_configs.xaxis.mode == "independent"
                    else spacing["y"]["shared"]
                )
            )
            + (0.025 if subplot_config.titles.plots is not None else 0),
            num_axes=len(subplot_config.plots),
        )

        xaxis_title = pop_axis_config_title(
            config=subplot_config.main_axis_configs.xaxis.config
        )
        yaxes_titles = [
            pop_axis_config_title(
                config=subplot_config.main_axis_configs.yaxes[idx].config
            )
            for idx in range(len(subplot_config.main_axis_configs.yaxes))
        ]

        specs = [
            [
                {"type": "surface"}
                if (
                    (plot_config is not None)
                    and (len(plot_config.yaxes_configs) > 0)
                    and (len(plot_config.yaxes_configs[0].traces) > 0)
                    and (is_trace_3d(plot_config.yaxes_configs[0].traces[0]))
                )
                else {}
                for plot_config in row_configs
            ]
            for row_configs in subplot_config.plots
        ]

        fig = make_subplots(
            rows=len(subplot_config.plots),
            cols=len(subplot_config.plots[0]),
            specs=specs,
        )

        super().__init__(
            description,
            PlotConfig.empty(),
            {},
            fig,
            *args,
            **kwargs,
        )

        if subplot_config.titles.rows is not None:
            self.update_layout(
                margin_l=(
                    self.layout.margin.l  # type: ignore
                    or pio.templates[pio.templates.default].layout.margin.l  # type: ignore
                )
                + 20
            )
        for row_idx, row_title in enumerate(subplot_config.titles.rows or []):
            self.add_title(
                title=row_title,
                edge="left",
                x_domain=(
                    x_domains[0][0],
                    x_domains[0][1],
                ),
                y_domain=(
                    y_domains[row_idx][0],
                    y_domains[row_idx][1],
                ),
                offset=line_title_offsets[0],
                **line_title_styles,
            )

        if subplot_config.titles.cols is not None:
            self.update_layout(
                margin_b=(
                    self.layout.margin.b  # type: ignore
                    or pio.templates[pio.templates.default].layout.margin.b  # type: ignore
                )
                + 20
            )
        for col_idx, col_title in enumerate(subplot_config.titles.cols or []):
            self.add_title(
                title=col_title,
                edge="bottom",
                x_domain=(
                    x_domains[col_idx][0],
                    x_domains[col_idx][1],
                ),
                y_domain=(
                    y_domains[0][0],
                    y_domains[0][1],
                ),
                offset=line_title_offsets[1],
                **line_title_styles,
            )

        for row_idx, row_titles in enumerate(subplot_config.titles.plots or []):
            for col_idx, plot_title in enumerate(row_titles):
                self.add_title(
                    title=plot_title or "",
                    edge="top",
                    x_domain=(
                        x_domains[col_idx][0],
                        x_domains[col_idx][1],
                    ),
                    y_domain=(
                        y_domains[row_idx][0],
                        y_domains[row_idx][1],
                    ),
                    offset=0,
                    **plot_title_styles,
                )

        self.update_layout(
            layout,
        ).update_layout(
            title_text=subplot_config.titles.main,
        )

        if xaxis_title is not None:
            self.add_title(
                title=xaxis_title,
                edge="bottom",
                x_domain=(0, x_domains[-1][-1]),
                offset=30 if subplot_config.titles.cols is None else 40,
            )

        for axis_idx, yaxis_title in enumerate(yaxes_titles):
            if yaxis_title is not None:
                self.add_title(
                    title=yaxis_title,
                    edge="left" if axis_idx == 0 else "right",
                    offset=30
                    if subplot_config.titles.rows is None or axis_idx != 0
                    else 40,
                    x_domain=(
                        0,
                        get_domain_fraction(
                            axis_idx=axis_idx,
                            max_yaxis=max_yaxis,
                        ),
                    ),
                    y_domain=(0, y_domains[-1][-1]),
                )

        scene_count = 0
        for row_idx, row_plot_configs in enumerate(subplot_config.plots):
            for col_idx, plot_config in enumerate(row_plot_configs):
                if plot_config is None:
                    plot_config = PlotConfig(
                        yaxes_configs=(
                            TracesConfig.from_trace(
                                trace=Null(
                                    x_datetime=x_datetime,
                                ),
                                yaxis_config=dict(
                                    # showgrid=False,
                                    # minor=dict(
                                    #     showgrid=False,
                                    # ),
                                    # zeroline=False,
                                ),
                            ),
                        ),
                    )

                is_scene = specs[row_idx][col_idx].get("type", False) == "surface"
                if is_scene:
                    scene_count += 1
                    scene_str = str(scene_count) if scene_count != 1 else ""

                xaxis_num = (
                    col_idx + row_idx * len(subplot_config.plots[0]) + 1 - scene_count
                )
                xaxis_str = str(xaxis_num) if xaxis_num != 1 else ""

                self.update_layout(
                    {
                        "scene": dict(
                            domain=dict(
                                x=x_domains[col_idx],
                                y=y_domains[::-1][row_idx],
                            )
                        ),
                    }
                    if is_scene
                    else {
                        f"xaxis{xaxis_str}": {
                            **axis_dict,
                            **subplot_config.main_axis_configs.xaxis.config,
                            **plot_config.xaxis_config,
                            "matches": "x"
                            if subplot_config.main_axis_configs.xaxis.mode
                            != "independent"
                            else None,
                            "domain": x_domains[col_idx],
                            "showticklabels": (
                                subplot_config.main_axis_configs.yaxes[axis_idx].mode
                                != "collapsed"
                            )
                            or (row_idx == len(subplot_config.plots) - 1),
                        },
                    }
                )

                for axis_idx in range(0, max_yaxis):
                    yaxis_num = plot_count * axis_idx + xaxis_num
                    yaxis_str = str(yaxis_num) if yaxis_num != 1 else ""
                    iaxis_num = plot_count * axis_idx + 1
                    iaxis_str = str(iaxis_num) if iaxis_num != 1 else ""

                    y_axis_details = subplot_config.main_axis_configs.yaxes[axis_idx]

                    if not is_scene:
                        self.update_layout(
                            {
                                f"yaxis{yaxis_str}": {
                                    **(
                                        axis_dict
                                        if axis_idx == 0
                                        else {
                                            **non_primary_axis_dict,
                                            "position": get_domain_fraction(
                                                axis_idx=axis_idx,
                                                max_yaxis=max_yaxis,
                                            ),
                                            "overlaying": f"y{xaxis_str}",
                                            "anchor": f"x{xaxis_str}"
                                            if axis_idx == 1
                                            and y_axis_details.mode != "collapsed"
                                            else "free",
                                        }
                                    ),
                                    "matches": f"y{iaxis_str}"
                                    if y_axis_details.mode != "independent"
                                    else None,
                                    "domain": y_domains[::-1][row_idx],
                                    "showticklabels": (
                                        y_axis_details.mode != "collapsed"
                                    )
                                    or (col_idx == 0),
                                    **y_axis_details.config,
                                },
                            },
                        )

                    if len(plot_config.yaxes_configs) > axis_idx:
                        traces_config = plot_config.yaxes_configs[axis_idx]
                        if not is_scene:
                            self.update_layout(
                                {f"yaxis{yaxis_str}": traces_config.yaxis_config}
                            )
                        traces = traces_config.traces
                    else:
                        traces = (
                            (
                                Null(
                                    x_datetime=x_datetime,
                                ),
                            )
                            if fill_nulls and not is_scene
                            else tuple()
                        )

                    for trace in traces:
                        if is_scene:
                            trace.scene = f"scene{scene_str}"
                        else:
                            trace.xaxis = f"x{xaxis_str}"
                            trace.yaxis = f"y{yaxis_str}"
                        self.add_trace(
                            trace=trace,
                        )

        self.modifications()

    def add_rug(
        self,
        *args,
        **kwargs,
    ) -> None:
        pass


def map_categorical_array(
    arr: NDArray,
    mapping: Optional[ArrayLike] = None,
) -> NDArray[np.int64]:
    if (mapping is not None) and (len(set(mapping)) != len(mapping)):  # type: ignore
        raise ValueError("Mapping is not unique")

    mapping_ = (
        np.asarray(mapping)
        if mapping is not None
        else arr[sorted(np.unique(arr, return_index=True)[1])]
    )
    mapping_dict = {value: idx for idx, value in enumerate(mapping_)}
    arr_numerical = np.asarray([mapping_dict.get(value, -1) for value in arr])
    if arr_numerical.min() != 0:
        raise ValueError("Mapping is not complete")

    return arr_numerical


def melt_dataframe(
    df: DataFrame,
) -> tuple[NDArray, NDArray, NDArray]:
    values = df.melt(ignore_index=False).reset_index().to_numpy().transpose()

    return (
        values[0],
        values[1],
        values[2],
    )


def get_domains(
    spacing: float,
    num_axes: int,
    fraction: float = 1,
) -> list[list[float]]:
    gap = (1 - spacing * (num_axes - 1)) / num_axes
    domains = [
        [
            (gap + spacing) * idx * fraction,
            (gap + spacing) * idx * fraction + gap * fraction,
        ]
        for idx in range(num_axes)
    ]

    return domains


def is_trace_3d(
    trace: Trace,
) -> bool:
    return (
        trace.type.endswith("3d")  # type: ignore
        or trace.type  # type: ignore
        in ["surface", "mesh3d", "cone", "streamtube", "volume"]
    )


def get_domain_fraction(
    axis_idx: int,
    max_yaxis: int,
) -> float:
    if max_yaxis <= 2:
        return 1

    return 1 - (max_yaxis - axis_idx - 1) * 0.1


def pop_axis_config_title(
    config: dict,
) -> Optional[str]:
    title = config.pop("title_text", None)

    if title is not None:
        return title

    title = config.get("title", {})
    if isinstance(title, str):
        return config.pop("title")
    else:
        return config.get("title", {}).pop("text", None)


def sort_traces_by_axes(
    traces: list[Trace],
) -> dict:
    traces_axes = {}
    for trace in traces:
        if (trace.xaxis, trace.yaxis) in traces_axes:  # type: ignore
            traces_axes[(trace.xaxis, trace.yaxis)].append(trace)  # type: ignore
        else:
            traces_axes[(trace.xaxis, trace.yaxis)] = [trace]  # type: ignore

    return traces_axes


def merge_cuboids(
    *cuboids: Cuboid,
) -> go.Mesh3d:
    x = np.zeros(len(cuboids) * 8)
    y = np.zeros(len(cuboids) * 8)
    z = np.zeros(len(cuboids) * 8)
    intensity = np.zeros(len(cuboids) * 8)
    i = (
        np.tile([7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2], (len(cuboids), 1))
        + np.arange(len(cuboids))[:, np.newaxis] * 8
    ).flatten()
    j = (
        np.tile([3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3], (len(cuboids), 1))
        + np.arange(len(cuboids))[:, np.newaxis] * 8
    ).flatten()
    k = (
        np.tile([0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6], (len(cuboids), 1))
        + np.arange(len(cuboids))[:, np.newaxis] * 8
    ).flatten()

    for idx, cuboid in enumerate(cuboids):
        x[idx * 8 : (idx + 1) * 8] = cuboid.x  # type: ignore
        y[idx * 8 : (idx + 1) * 8] = cuboid.y  # type: ignore
        z[idx * 8 : (idx + 1) * 8] = cuboid.z  # type: ignore
        intensity[idx * 8 : (idx + 1) * 8] = cuboid.intensity  # type: ignore

    return go.Mesh3d(
        x=x,
        y=y,
        z=z,
        i=i,
        j=j,
        k=k,
        intensity=intensity,
        flatshading=True,
        showscale=False,
        cmin=0,
        cmax=1,
    )


def combine_figures(
    files: list[str],
    title: str,
    cols: int,
    rows: int,
    filetype: str = "pdf",
) -> None:
    if filetype == "pdf":
        images = []
        for file in files:
            doc = pymupdf.open(file)
            pix = doc[0].get_pixmap()  # type: ignore
            img = Image.frombytes(
                mode="RGB",
                size=(
                    pix.width,
                    pix.height,
                ),
                data=pix.samples,
            )
            images.append(img)

        img_width, img_height = images[0].size

        final_image = Image.new(
            mode="RGB",
            size=(
                img_width * cols,
                img_height * rows,
            ),
            color="white",
        )

        for idx, img in enumerate(images):
            row, col = divmod(idx, cols)
            final_image.paste(
                im=img,
                box=(
                    col * img_width,
                    row * img_height,
                ),
            )

        final_image.save(fp=f"{title}")

    else:
        raise NotImplementedError("Other conversions are not supported yet")
