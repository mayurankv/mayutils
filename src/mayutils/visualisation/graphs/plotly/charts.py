import os
from math import isqrt, ceil
from pathlib import Path
from typing import Any, Literal, Mapping, Optional, Self, final, Sequence
from dataclasses import dataclass, field
from mayutils.export.images import IMAGES_FOLDER
import numpy as np
from scipy.stats import gaussian_kde, norm
import datetime
from pandas import to_datetime as to_pandas_datetime

import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
from plotly._subplots import _build_subplot_title_annotations

from mayutils.objects.colours import TRANSPARENT, Colour

from mayutils.objects.datetime import Interval
from mayutils.objects.functions import set_inline

from mayutils.visualisation.graphs.plotly.templates import (
    non_primary_axis_dict,
    axis_dict,
    shuffled_colourscale,
)
from plotly.basedatatypes import BaseTraceType as Trace
from mayutils.visualisation.graphs.plotly.traces import (
    Null,
    Line,
    Scatter,
    Ecdf,
    Bar3d,
    is_trace_3d,
)

AxisConfig = dict


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
    cols_top: bool = False

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
            **kwargs,
        )


class Plot(go.Figure):
    def __init__(
        self,
        description: str,
        plot_config: PlotConfig,
        layout: Mapping = {},
        *args,
        **kwargs,
    ) -> None:
        self._description = description
        self._nbconvert_output_format = os.getenv(
            key="_NBCONVERT_OUTPUT_FORMAT",
            default=None,
        )

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
                if not (is_trace_3d(trace) or isinstance(trace, go.Icicle)):
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

    @classmethod
    def as_dropdown(
        cls,
        description: str,
        **plots: Self,
    ) -> Self:
        return cls.from_figure(
            fig=go.Figure(
                data=(first_plot := next(iter(plots.values()))).data,
                layout=first_plot.layout.update(  # type: ignore
                    updatemenus=[
                        dict(
                            buttons=[
                                dict(
                                    label=label,
                                    method="animate",
                                    args=[
                                        [label],
                                        dict(
                                            mode="immediate",
                                            frame=dict(
                                                duration=0,
                                                redraw=True,
                                            ),
                                            transition=dict(duration=0),
                                        ),
                                    ],
                                )
                                for label in plots.keys()
                            ],
                            type="dropdown",
                            direction="down",
                        )
                    ],
                ),
                frames=[
                    go.Frame(
                        data=plot.data,
                        layout=plot.layout.update(  # type: ignore
                            **(
                                dict(
                                    shapes=(
                                        go.layout.Shape(
                                            type="rect",
                                            line=dict(color="rgba(0,0,0,0)", width=0),
                                            fillcolor="rgba(0,0,0,0)",
                                        ),
                                    )
                                )
                                if not hasattr(plot.layout, "shapes")
                                or plot.layout.shapes == tuple()  # type: ignore
                                else dict()
                            ),
                            **(
                                dict(
                                    annotations=(
                                        go.layout.Annotation(
                                            xref="paper",
                                            yref="paper",
                                            text="",
                                            showarrow=False,
                                        ),
                                    )
                                )
                                if not hasattr(plot.layout, "annotations")
                                or plot.layout.annotations == tuple()  # type: ignore
                                else dict()
                            ),
                            xaxis=dict(
                                autorange=False,
                                range=plot.layout.xaxis.range  # type: ignore
                                or (
                                    np.nanmin(
                                        [
                                            np.nanmin(trace.x)  # type: ignore
                                            for trace in plot.data
                                            if hasattr(trace, "x") and trace.x.any()  # type: ignore
                                        ]
                                    ),
                                    np.nanmax(
                                        [
                                            np.nanmax(trace.x)  # type: ignore
                                            for trace in plot.data
                                            if hasattr(trace, "x") and trace.x.any()  # type: ignore
                                        ]
                                    ),
                                ),
                            ),
                            yaxis=dict(
                                autorange=False,
                                range=plot.layout.yaxis.range  # type: ignore
                                or (
                                    np.nanmin(
                                        [
                                            np.nanmin(trace.y)  # type: ignore
                                            for trace in plot.data
                                            if hasattr(trace, "y") and trace.y.any()  # type: ignore
                                        ]
                                    ),
                                    np.nanmax(
                                        [
                                            np.nanmax(trace.y)  # type: ignore
                                            for trace in plot.data
                                            if hasattr(trace, "y") and trace.y.any()  # type: ignore
                                        ]
                                    ),
                                ),
                            ),
                        ),
                        name=label,
                    )
                    for label, plot in plots.items()
                ],
            ),
            description=description,
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

    def add_annotation(
        self,
        *args,
        **kwargs,
    ) -> Self:
        super().add_annotation(
            *args,
            **kwargs,
        )

        return self

    def add_shape(
        self,
        *args,
        **kwargs,
    ) -> Self:
        # update_wrapper(wrapper=go.Figure.add_shape, wrapped=self.add_shape)
        super().add_shape(
            *args,
            **kwargs,
        )

        return self

    def add_vrect(
        self,
        *args,
        **kwargs,
    ) -> Self:
        # update_wrapper(wrapper=go.Figure.add_vrect, wrapped=self.add_vrect)
        super().add_vrect(
            *args,
            **kwargs,
        )

        return self

    def add_vline(
        self,
        *args,
        **kwargs,
    ) -> Self:
        # update_wrapper(wrapper=go.Figure.add_vline, wrapped=self.add_vline)
        super().add_vline(
            *args,
            **kwargs,
        )

        return self

    def add_hline(
        self,
        *args,
        **kwargs,
    ) -> Self:
        # update_wrapper(wrapper=go.Figure.add_hline, wrapped=self.add_hline)
        super().add_hline(
            *args,
            **kwargs,
        )

        return self

    def empty_traces(
        self,
        *args,
        **kwargs,
    ) -> Self:
        self.data: Any = []  #  pyright: ignore[reportIncompatibleMethodOverride]

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

    def update_traces(
        self,
        *args,
        **kwargs,
    ) -> Self:
        super().update_traces(
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
        layout: Mapping = {},
        *args,
        **kwargs,
    ) -> None:
        if show:
            super(Plot, self.copy().update_layout(layout)).show(
                config=dict(
                    showTips=False,
                    displaylogo=False,
                    displayModeBar=(
                        False if self._nbconvert_output_format == "slides" else "hover"
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
        image_formats: Sequence[str] = ["png"],  # ["png", "jpeg", "pdf"]
        scale: Optional[int] = 5,
        template: Optional[str] = None,
        *args,
        **kwargs,
    ) -> Path:
        if template is None:
            template = f"{pio.templates.default}+plotly_white+save"

        for image_format in image_formats:
            self.copy().update_layout(
                paper_bgcolor="rgba(255,255,255,1)",
                plot_bgcolor="rgba(255,255,255,1)",
                template=template,
            ).write_image(
                file=IMAGES_FOLDER / f"{filename}.{image_format}",
                format=image_format,
                scale=scale,
                *args,
                **kwargs,
            )

        return (
            IMAGES_FOLDER / f"{filename}.{image_formats[0]}"
            if len(image_formats) > 0
            else IMAGES_FOLDER
        )

    def modifications(
        self,
    ) -> Self:
        for idx, trace in enumerate(self.data):
            if isinstance(trace, go.Histogram) or trace.meta in ["kde"]:  # type: ignore
                trace.marker.line.color = (  # type: ignore
                    trace.marker.color  # type: ignore
                    or shuffled_colourscale[idx % len(shuffled_colourscale)]
                )
            if trace.meta in ["line", "ecdf", "kde"]:  # type: ignore
                trace.textfont.color = (  # type: ignore
                    trace.line.color  # type: ignore
                    or trace.marker.color  # type: ignore
                    or shuffled_colourscale[idx % len(shuffled_colourscale)]
                )
                if trace.meta in ["ecdf", "kde"]:  # type: ignore
                    colour = Colour.parse(colour=trace.textfont.color)  # type: ignore
                    opacity = 0.1 if trace.meta == "ecdf" else 0.4  # type: ignore
                    trace.fillcolor = colour.to_str(opacity=opacity)  # type: ignore

        bound_groups: dict[str, tuple[tuple[Optional[str], int], list[Trace]]] = {}
        for idx, trace in enumerate(self.data):
            if (
                hasattr(trace, "legendgroup")
                and trace.legendgroup  # type: ignore
                and trace.legendgroup.startswith("bounds")  # type: ignore
            ):
                if trace.legendgroup not in bound_groups:  # type: ignore
                    bound_groups[trace.legendgroup] = ((None, 0), [])  # type: ignore

                if trace.fill == "toself":  # type: ignore
                    bound_groups[trace.legendgroup][1].append(trace)  # type: ignore
                else:
                    bound_groups[trace.legendgroup][0] = (trace.line.color, idx)  # type: ignore

        for (line_colour, idx), bound_traces in bound_groups.values():
            if line_colour is None:
                colour = Colour.parse(
                    colour=shuffled_colourscale[idx % len(shuffled_colourscale)]
                )

                opacity = Colour.parse(colour=bound_traces[0].fillcolor).a  # type: ignore
                for bound_trace in bound_traces:
                    bound_trace.fillcolor = colour.to_str(opacity=opacity)  # type: ignore

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
                        or getattr(
                            set_inline(
                                self.data[idx],
                                "legendgroup",
                                idx,
                            ),
                            "legendgroup",
                            idx,
                        ),
                        showlegend=False,
                        label_name=False,
                    )
                )

        return self

    @final
    def add_rug(
        self,
        rug_type: Literal[
            "scatter", "violin", "box", "strip", "historgram", "ecdf"
        ] = "scatter",
        rug_height: Optional[float] = None,
        *args,
        **kwargs,
    ) -> Self:
        if getattr(self, "_added_rugs", False):
            return self

        rug_count = 0
        traces = []
        for idx, trace in enumerate(self.data):
            if isinstance(trace, go.Histogram):
                x = self.data[idx].x  # type: ignore
            elif trace.meta == "kde":  # type: ignore
                x = self.data[idx].customdata  # type: ignore
            else:
                continue
            rug_count += 1
            if rug_type == "scatter":
                traces.append(
                    go.Scatter(
                        x=x,  # type: ignore
                        y=([rug_count] * len(x)),  # type: ignore
                        xaxis="x1",
                        yaxis="y2",
                        mode="markers",
                        name=(
                            (self.data[idx].name + " Rug")  # type: ignore
                            if self.data[idx].name  # type: ignore
                            else f"trace {idx} Rug"
                        ),
                        legendgroup=self.data[idx].legendgroup  # type: ignore
                        or getattr(
                            set_inline(
                                self.data[idx],
                                "legendgroup",
                                idx,
                            ),
                            "legendgroup",
                            idx,
                        ),
                        showlegend=False,
                        marker=dict(
                            color=self.data[idx].marker.line.color,  # type: ignore
                            symbol="line-ns-open",
                        ),
                        *args,
                        **kwargs,
                    )
                )
            elif rug_type == "strip":
                traces.append(
                    go.Box(
                        x=x,  # type: ignore
                        y=([rug_count] * len(x)),  # type: ignore
                        xaxis="x1",
                        yaxis="y2",
                        orientation="h",
                        name=(
                            (self.data[idx].name + " Rug")  # type: ignore
                            if self.data[idx].name  # type: ignore
                            else f"trace {idx} Rug"
                        ),
                        legendgroup=self.data[idx].legendgroup  # type: ignore
                        or getattr(
                            set_inline(
                                self.data[idx],
                                "legendgroup",
                                idx,
                            ),
                            "legendgroup",
                            idx,
                        ),
                        showlegend=False,
                        line=dict(
                            color=TRANSPARENT.to_str(),
                        ),
                        fillcolor=TRANSPARENT.to_str(),
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
            elif rug_type == "box":
                traces.append(
                    go.Box(
                        x=x,  # type: ignore
                        y=([rug_count] * len(x)),  # type: ignore
                        xaxis="x1",
                        yaxis="y2",
                        orientation="h",
                        name=(
                            (self.data[idx].name + " Rug")  # type: ignore
                            if self.data[idx].name  # type: ignore
                            else f"trace {idx} Rug"
                        ),
                        legendgroup=self.data[idx].legendgroup  # type: ignore
                        or getattr(
                            set_inline(
                                self.data[idx],
                                "legendgroup",
                                idx,
                            ),
                            "legendgroup",
                            idx,
                        ),
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
                        x=x,  # type: ignore
                        y=([rug_count] * len(x)),  # type: ignore
                        xaxis="x1",
                        yaxis="y2",
                        orientation="h",
                        name=(
                            (self.data[idx].name + " Rug")  # type: ignore
                            if self.data[idx].name  # type: ignore
                            else f"trace {idx} Rug"
                        ),
                        legendgroup=self.data[idx].legendgroup  # type: ignore
                        or getattr(
                            set_inline(
                                self.data[idx],
                                "legendgroup",
                                idx,
                            ),
                            "legendgroup",
                            idx,
                        ),
                        showlegend=False,
                        line=dict(
                            color=self.data[idx].marker.line.color,  # type: ignore
                        ),
                        marker=dict(
                            color=self.data[idx].marker.line.color,  # type: ignore
                            size=5,
                        ),
                        scalegroup="added_rug",
                        points=kwargs.pop("points", "suspectedoutliers"),
                        opacity=0.6,
                        jitter=0.6,
                        width=1,
                        side="positive",
                        *args,
                        **kwargs,
                    )
                )
            elif rug_type == "histogram":
                raise NotImplementedError("Histogram not implemented")
            elif rug_type == "ecdf":
                traces.append(
                    Ecdf(
                        x=x,  # type: ignore
                        y_shift=rug_count,  # type: ignore
                        xaxis="x1",
                        yaxis="y2",
                        name=(
                            (self.data[idx].name + " Rug")  # type: ignore
                            if self.data[idx].name  # type: ignore
                            else f"trace {idx} Rug"
                        ),
                        legendgroup=self.data[idx].legendgroup  # type: ignore
                        or getattr(
                            set_inline(
                                self.data[idx],
                                "legendgroup",
                                idx,
                            ),
                            "legendgroup",
                            idx,
                        ),
                        showlegend=False,
                        line=dict(
                            color=self.data[idx].marker.line.color,  # type: ignore
                        ),
                        fill="toself",
                        *args,
                        **kwargs,
                    )
                )
            else:
                raise ValueError(f"Rug type {rug_type} is unknown")

        height = rug_height or (0.15 if rug_type == "scatter" else 0.3)
        if rug_count > 0:
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

            # for trace in traces:
            self.add_traces(data=traces)

        self._added_rugs = True

        self.modifications()

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
                    and (plot_name in ["bar3d", "null", "scatter", "line", "ecdf"])
                )
                for trace in self.data
            ]
            for plot_name, plot_class in {
                "bar3d": Bar3d,
                "line": Line,
                "ecdf": Ecdf,
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
                        or getattr(
                            set_inline(
                                self.data[idx],
                                "legendgroup",
                                idx,
                            ),
                            "legendgroup",
                            idx,
                        ),
                        showlegend=False,
                        label_name=False,
                    )
                    for idx, include in enumerate(plot_types["histogram"])
                    if include
                ],
                "layout": dict(),
            },
        }
        buttons: dict[str, list[dict[str, Any]]] = {
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
                        for button in buttons.get(plot_type, [])
                    ],
                )
            ]
        )

        return self

    def add_interval(
        self,
        interval: Optional[Interval],
        **kwargs,
    ) -> Self:
        if interval is None:
            return self

        kwargs = {"line_width": 0, "opacity": 0.1} | kwargs

        self.add_vrect(
            x0=interval.start.simple,
            x1=interval.end.simple,
            **kwargs,
        )

        return self

    def hide_traces(
        self,
        trace_names: Sequence[str],
    ) -> Self:
        for name in trace_names:
            self = self.update_traces(
                visible="legendonly",
                selector=dict(name=name),
            )

        return self

    def set_visible_y_range(
        self,
        y_padding: float = 0.05,
    ) -> Self:
        yaxes = sorted([prop for prop in self.layout if prop.startswith("yaxis")])
        trace_limits_full = {
            yaxis: np.asarray(
                [
                    (
                        np.nanmin(visible_y)
                        if not np.isnan(visible_y := trace.y[visible_mask]).all()
                        and not visible_y.shape == (0,)
                        else np.nan,
                        np.nanmax(visible_y)
                        if not np.isnan(visible_y).all() and not visible_y.shape == (0,)
                        else np.nan,
                    )
                    for trace in self.data
                    if trace.visible in [None, True]
                    and isinstance(trace.y, np.ndarray)
                    and (
                        trace_yaxis_obj := getattr(
                            self.layout,
                            trace.yaxis.replace("y", "yaxis"),
                            None,
                        )
                    )
                    is not None
                    and (
                        (
                            (matching_yaxis := trace_yaxis_obj.matches) is not None
                            and matching_yaxis.replace("y", "yaxis") == yaxis
                        )
                        or (trace.yaxis.replace("y", "yaxis") == yaxis)
                    )
                    and (
                        len(
                            (
                                x_trace := trace.x
                                if len(trace.x) > 0
                                and isinstance(trace.x[0], datetime.date)
                                else to_pandas_datetime(trace.x).date
                            )
                        )
                        > 0
                    )
                    and (
                        visible_mask := (x_trace < self.layout.xaxis.range[1])  # type: ignore
                        & (x_trace > self.layout.xaxis.range[0])  # type: ignore
                    ).any()
                ]
            )
            for yaxis in yaxes
        }

        trace_limits = {
            f"{yaxis}_range": (
                np.nanmin(limits[:, 0]) if not np.isnan(limits[:, 0]).all() else None,
                np.nanmax(limits[:, 1]) if not np.isnan(limits[:, 1]).all() else None,
            )
            for yaxis, limits in trace_limits_full.items()
            if len(limits) > 0
        }

        padded_trace_limits = {
            yaxis_range: (
                y_min - (y_max - y_min) * y_padding,
                y_max + (y_max - y_min) * y_padding,
            )
            if y_max is not None and y_min is not None
            else (
                y_min * (1 - y_padding) if y_min is not None else None,
                y_max * (1 + y_padding) if y_max is not None else None,
            )
            for yaxis_range, (y_min, y_max) in trace_limits.items()
        }

        self.update_layout(padded_trace_limits)

        return self

    def __call__(
        self,
        save: bool = True,
        show: bool = True,
    ) -> Self:
        if save:
            self.save(
                filename=self._description,
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
        layout: Mapping = {},
        x_datetime: bool = False,
        x_spacing: Mapping[str, float] = {},
        y_spacing: Mapping[str, float] = {},
        line_title_offsets: tuple[float, float] = (22.5, 22.5),
        line_title_styles: Mapping = dict(
            font_weight=700,
            font_size=12,
        ),
        plot_title_styles: Mapping = dict(),
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
            * max_yaxis,
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
        for row_idx, row_title in enumerate((subplot_config.titles.rows or [])[::-1]):
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
                edge="bottom" if not subplot_config.titles.cols_top else "top",
                x_domain=(
                    x_domains[col_idx][0],
                    x_domains[col_idx][1],
                ),
                y_domain=(
                    y_domains[0 if not subplot_config.titles.cols_top else -1][0],
                    y_domains[0 if not subplot_config.titles.cols_top else -1][1],
                ),
                offset=line_title_offsets[1],
                **line_title_styles,
            )

        for row_idx, row_titles in enumerate((subplot_config.titles.plots or [])[::-1]):
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
                else:
                    scene_str = ""

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
                                subplot_config.main_axis_configs.xaxis.mode
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

    # def add_rug(
    #     self,
    #     rug_type: Literal[
    #         "scatter", "violin", "box", "strip", "historgram", "ecdf"
    #     ] = "scatter",
    #     rug_height: Optional[float] = None,
    #     *args,
    #     **kwargs,
    # ) -> Self:
    #     raise NotImplementedError("Rug not implemented for SubPlot")
    #     return self


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


def get_domain_fraction(
    axis_idx: int,
    max_yaxis: int,
) -> float:
    if max_yaxis <= 2:
        return 1

    return 1 - (max_yaxis - axis_idx - 1) * 0.1


def get_domains(
    spacing: float,
    num_axes: int,
    fraction: float = 1,
) -> list[list[float]]:
    gap = (1 - spacing * (num_axes - 1)) / num_axes
    domains = [
        [
            max((gap + spacing) * idx * fraction, 0),
            min((gap + spacing) * idx * fraction + gap * fraction, 1),
        ]
        for idx in range(num_axes)
    ]

    return domains


def sort_traces_by_axes(
    traces: Sequence[Trace],
) -> dict:
    traces_axes: dict[tuple[str, str], list[Trace]] = {}
    for trace in traces:
        if (trace.xaxis, trace.yaxis) in traces_axes:  # type: ignore
            traces_axes[(trace.xaxis, trace.yaxis)].append(trace)  # type: ignore
        else:
            traces_axes[(trace.xaxis, trace.yaxis)] = [trace]  # type: ignore

    return traces_axes
