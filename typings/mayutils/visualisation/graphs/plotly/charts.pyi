import plotly.graph_objects as go
from dataclasses import dataclass, field
from mayutils.export.images import IMAGES_FOLDER as IMAGES_FOLDER
from mayutils.objects.colours import Colour as Colour, TRANSPARENT as TRANSPARENT
from mayutils.objects.datetime import Interval as Interval
from mayutils.objects.functions import set_inline as set_inline
from mayutils.visualisation.graphs.plotly.templates import (
    axis_dict as axis_dict,
    non_primary_axis_dict as non_primary_axis_dict,
    shuffled_colourscale as shuffled_colourscale,
)
from mayutils.visualisation.graphs.plotly.traces import (
    Bar3d as Bar3d,
    Ecdf as Ecdf,
    Line as Line,
    Null as Null,
    Scatter as Scatter,
    is_trace_3d as is_trace_3d,
)
from pathlib import Path
from plotly.basedatatypes import BaseTraceType as Trace
from typing import Any, Literal, Mapping, Self, Sequence, final

AxisConfig = dict

@dataclass
class TracesConfig:
    traces: tuple[Trace, ...]
    yaxis_config: AxisConfig = field(default_factory=AxisConfig)
    @classmethod
    def from_trace(
        cls, trace: Trace, yaxis_config: AxisConfig = ...
    ) -> TracesConfig: ...

@dataclass
class PlotConfig:
    yaxes_configs: tuple[TracesConfig, ...]
    xaxis_config: AxisConfig = field(default_factory=AxisConfig)
    @classmethod
    def empty(cls) -> PlotConfig: ...
    @classmethod
    def from_trace(
        cls,
        trace: Trace,
        yaxis_config: AxisConfig = ...,
        xaxis_config: AxisConfig = ...,
    ) -> PlotConfig: ...
    @classmethod
    def from_traces(
        cls,
        *traces: Trace,
        yaxis_config: AxisConfig = ...,
        xaxis_config: AxisConfig = ...,
    ) -> PlotConfig: ...

@dataclass
class Titles:
    main: str = ...
    rows: tuple[str, ...] | None = ...
    cols: tuple[str, ...] | None = ...
    plots: tuple[tuple[str | None, ...], ...] | None = ...
    cols_top: bool = ...
    def __post_init__(self) -> None: ...

@dataclass
class MainAxisConfig:
    config: AxisConfig = field(default_factory=AxisConfig)
    mode: Literal["independent", "shared", "collapsed"] = ...
    @classmethod
    def from_dict(cls, *args, **kwargs) -> Self: ...

@dataclass
class MainAxisConfigs:
    xaxis: MainAxisConfig = field(default_factory=MainAxisConfig)
    yaxes: tuple[MainAxisConfig, ...] = ...

@dataclass
class SubPlotConfig:
    plots: tuple[tuple[PlotConfig | None, ...], ...]
    main_axis_configs: MainAxisConfigs = field(default_factory=MainAxisConfigs)
    titles: Titles = field(default_factory=Titles)
    def __post_init__(self) -> None: ...
    @classmethod
    def flat(
        cls, plots: tuple[PlotConfig | None, ...], cols: int | None, **kwargs
    ) -> SubPlotConfig: ...

class Plot(go.Figure):
    def __init__(
        self,
        description: str,
        plot_config: PlotConfig,
        layout: Mapping = {},
        *args,
        **kwargs,
    ) -> None: ...
    @classmethod
    def from_traces(
        cls,
        *traces: Trace,
        description: str,
        xaxis_config: AxisConfig = ...,
        yaxis_config: AxisConfig = ...,
        **kwargs,
    ) -> Self: ...
    @classmethod
    def from_figure(cls, fig: go.Figure, description: str) -> Self: ...
    @classmethod
    def from_existing(cls, plot: Plot, description: str) -> Self: ...
    @classmethod
    def empty(cls, description: str) -> Self: ...
    @classmethod
    def as_dropdown(cls, description: str, **plots: Self) -> Self: ...
    def to_figure(self) -> go.Figure: ...
    def add_trace(self, trace, *args, **kwargs) -> Self: ...
    def add_annotation(self, *args, **kwargs) -> Self: ...
    def add_shape(self, *args, **kwargs) -> Self: ...
    def add_vrect(self, *args, **kwargs) -> Self: ...
    def add_vline(self, *args, **kwargs) -> Self: ...
    def add_hline(self, *args, **kwargs) -> Self: ...
    data: Any
    def empty_traces(self, *args, **kwargs) -> Self: ...
    def update_layout(self, *args, **kwargs) -> Self: ...
    def update_traces(self, *args, **kwargs) -> Self: ...
    def add_title(
        self,
        title: str,
        edge: Literal["left", "right", "top", "bottom"] = "right",
        offset: float = 30,
        x_domain: tuple[float, float] = (0, 1),
        y_domain: tuple[float, float] = (0, 1),
        *args,
        **kwargs,
    ) -> Self: ...
    def shift_title(self, offset: int) -> Self: ...
    def show(
        self, show: bool = True, layout: Mapping = {}, *args, **kwargs
    ) -> None: ...
    def copy(self, description: str | None = None) -> Plot: ...
    def save(
        self,
        filename: str,
        image_formats: Sequence[str] = ["png"],
        scale: int | None = 5,
        template: str | None = None,
        *args,
        **kwargs,
    ) -> Path: ...
    def modifications(self) -> Self: ...
    def add_histogram_gaussians(self, *args, **kwargs) -> Self: ...
    @final
    def add_rug(
        self,
        rug_type: Literal[
            "scatter", "violin", "box", "strip", "historgram", "ecdf"
        ] = "scatter",
        rug_height: float | None = None,
        *args,
        **kwargs,
    ) -> Self: ...
    def add_defaults(self, **kwargs) -> Self: ...
    def add_interval(self, interval: Interval | None, **kwargs) -> Self: ...
    def hide_traces(self, trace_names: Sequence[str]) -> Self: ...
    def __call__(self, save: bool = True, show: bool = True) -> Self: ...

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
        line_title_styles: Mapping = ...,
        plot_title_styles: Mapping = ...,
        fill_nulls: bool = True,
        *args,
        **kwargs,
    ) -> None: ...

def pop_axis_config_title(config: dict) -> str | None: ...
def get_domain_fraction(axis_idx: int, max_yaxis: int) -> float: ...
def get_domains(
    spacing: float, num_axes: int, fraction: float = 1
) -> list[list[float]]: ...
def sort_traces_by_axes(traces: Sequence[Trace]) -> dict: ...
