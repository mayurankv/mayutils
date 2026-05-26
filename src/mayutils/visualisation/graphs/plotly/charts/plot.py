import datetime
from collections.abc import Callable, Iterator, Mapping, Sequence, Sized
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self, cast, final

from mayutils.core.extras import may_require_extras
from mayutils.environment.logging import Logger
from mayutils.export.images import IMAGES_FOLDER
from mayutils.objects.colours import TRANSPARENT, Colour
from mayutils.objects.datetime import Date, DateTime, Interval
from mayutils.objects.functions import set_inline
from mayutils.objects.paths import resolve_save_path
from mayutils.visualisation.graphs.plotly.charts import (
    AxisConfig,
    PlotConfig,
    get_domain_fraction,
    sort_traces_by_axes,
)
from mayutils.visualisation.graphs.plotly.templates import (
    get_default_template_name,
    get_layout_value,
    get_template,
    get_template_layout,
    non_primary_axis_dict,
    shuffled_colourscale,
)
from mayutils.visualisation.graphs.plotly.traces import (
    Bar3d,
    Ecdf,
    Kde,
    Line,
    Null,
    Scatter,
    TraceType,
    is_trace_3d,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray


with may_require_extras():
    import numpy as np
    import plotly.graph_objects as go
    from pandas import Series
    from pandas import to_datetime as to_pandas_datetime
    from plotly._subplots import _build_subplot_title_annotations  # pyright: ignore[reportPrivateUsage]  # ty:ignore[unresolved-import]
    from plotly.basedatatypes import BaseTraceType as Trace
    from plotly.graph_objects import Layout
    from scipy.stats import norm

logger = Logger.spawn()

DEFAULT_YAXIS_NUM = 1

TRACE_IDENTIFIERS = {
    TraceType.BAR3D: Bar3d,
    TraceType.LINE: Line,
    TraceType.ECDF: Ecdf,
    TraceType.NULL: Null,
    TraceType.SCATTER: Scatter,
    "histogram": go.Histogram,
}


class Plot(go.Figure):
    def __init__(  # noqa: C901, PLR0912
        self,
        config: PlotConfig,
        /,
        *,
        description: str,
        layout: Mapping[str, Any] | Layout | None = None,
        modification_kwargs: Mapping[str, Any] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        if layout is None:
            layout = Layout()
        elif not isinstance(layout, Layout):
            layout = Layout(dict(layout))

        if modification_kwargs is None:
            modification_kwargs = {}

        self._description = description

        super().__init__(
            layout=layout,
            **kwargs,
        )

        self.update_layout(
            xaxis=config.xaxis_config,
        )
        max_yaxis = len(config.yaxes_configs)

        if max_yaxis > DEFAULT_YAXIS_NUM:
            self.update_layout({"yaxis2": non_primary_axis_dict})

        if max_yaxis > DEFAULT_YAXIS_NUM + 1:
            self.update_layout(
                xaxis={
                    "domain": [
                        0,
                        get_domain_fraction(
                            axis_idx=1,
                            max_yaxis=max_yaxis,
                        ),
                    ]
                },
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

        for axis_idx, traces_config in enumerate(config.yaxes_configs):
            yaxis = f"yaxis{'' if axis_idx == 0 else str(axis_idx + 1)}"
            self.update_layout(
                {yaxis: traces_config.yaxis_config},
            )

            try:
                if axis_idx != 0:
                    axis_title: str = getattr(self.layout, yaxis).title.text

                    self.add_title(
                        axis_title,
                        x_domain=(0, 1 - (max_yaxis - axis_idx - 1) * 0.1),
                    )
                    getattr(self.layout, yaxis).title.text = ""
                    getattr(self.layout, yaxis).position = get_domain_fraction(axis_idx=axis_idx, max_yaxis=max_yaxis)
            except AttributeError:
                pass

            for trace in traces_config.traces:
                if not (
                    is_trace_3d(trace)
                    or isinstance(
                        trace,
                        (
                            go.Icicle,
                            go.Pie,
                        ),
                    )
                ):
                    try:
                        trace.yaxis = yaxis.replace("yaxis", "y")
                    except AttributeError as err:
                        msg = (
                            f"Could not set y-axis for trace {trace}. This may be because the trace type does not support multiple y-axes."
                        )
                        logger.warning(msg, exc_info=err)

                self.add_trace(
                    trace=trace,
                )

        if self.layout.title.text is not None:
            self.layout.title.text = self.layout.title.text.replace("\n", "<br>")

        self.modifications(
            **modification_kwargs,
        )

    @property
    def description(
        self,
    ) -> str:
        return self._description

    @property
    def num_traces(
        self,
    ) -> int:
        return len(self.data)

    @classmethod
    def from_traces(
        cls,
        *traces: Trace,
        description: str,
        xaxis_config: AxisConfig | None = None,
        yaxis_config: AxisConfig | None = None,
        layout: Mapping[str, Any] | Layout | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        if xaxis_config is None:
            xaxis_config = {}
        if yaxis_config is None:
            yaxis_config = {}

        return cls(
            PlotConfig.from_traces(
                *traces,
                yaxis_config=yaxis_config,
                xaxis_config=xaxis_config,
            ),
            description=description,
            layout=layout,
            **kwargs,
        )

    @classmethod
    def from_figure(
        cls,
        fig: go.Figure,
        /,
        *,
        description: str,
    ) -> Self:
        return cls(
            PlotConfig.empty(),
            description=description,
            data=fig,
        )

    @classmethod
    def from_existing(
        cls,
        plot: "Plot",
        /,
        *,
        description: str,
    ) -> Self:
        return cls.from_figure(
            plot,
            description=description,
        )

    @classmethod
    def empty(
        cls,
        *,
        description: str,
    ) -> Self:
        return cls(
            PlotConfig.empty(),
            description=description,
        )

    @classmethod
    def as_dropdown(
        cls,
        description: str,
        **plots: Self,
    ) -> Self:
        first_plot = next(iter(plots.values()))
        layout: Layout = first_plot.layout.update(  # ty:ignore[invalid-assignment]
            updatemenus=[
                {
                    "buttons": [
                        {
                            "label": label,
                            "method": "animate",
                            "args": [
                                [label],
                                {
                                    "mode": "immediate",
                                    "frame": {
                                        "duration": 0,
                                        "redraw": True,
                                    },
                                    "transition": {"duration": 0},
                                },
                            ],
                        }
                        for label in plots
                    ],
                    "type": "dropdown",
                    "direction": "down",
                }
            ],
        )

        fig = go.Figure(
            data=first_plot.data,
            layout=layout,
            frames=[
                go.Frame(
                    data=plot.data,
                    layout=plot.layout.update(
                        (
                            {
                                "shapes": (
                                    go.layout.Shape(
                                        type="rect",
                                        line={"color": "rgba(0,0,0,0)", "width": 0},
                                        fillcolor="rgba(0,0,0,0)",
                                    ),
                                )
                            }
                            if not hasattr(plot.layout, "shapes") or plot.layout.shapes == ()
                            else {}
                        )
                        | (
                            {
                                "annotations": (
                                    go.layout.Annotation(
                                        xref="paper",
                                        yref="paper",
                                        text="",
                                        showarrow=False,
                                    ),
                                )
                            }
                            if not hasattr(plot.layout, "annotations") or plot.layout.annotations == ()
                            else {}
                        )
                        | {
                            "xaxis": {
                                "autorange": False,
                                "range": getattr(plot.layout.xaxis, "range", None)
                                or (
                                    np.nanmin(vals),
                                    np.nanmax(vals),
                                )
                                if (
                                    vals := [
                                        v
                                        for trace in plot.data
                                        if (x := getattr(trace, "x", None)) is not None and isinstance(x, Sized) and len(x) > 0
                                        for v in np.asarray(x).ravel()
                                    ]
                                )
                                else (None, None),
                            },
                            "yaxis": {
                                "autorange": False,
                                "range": getattr(plot.layout.yaxis, "range", None)
                                or (
                                    np.nanmin(vals),
                                    np.nanmax(vals),
                                )
                                if (
                                    vals := [
                                        v
                                        for trace in plot.data
                                        if (y := getattr(trace, "y", None)) is not None and isinstance(y, Sized) and len(y) > 0
                                        for v in np.asarray(y).ravel()
                                    ]
                                )
                                else (None, None),
                            },
                        }
                    ),
                    name=label,
                )
                for label, plot in plots.items()
            ],
        )

        return cls.from_figure(
            fig,
            description=description,
        )

    def to_figure(
        self,
    ) -> go.Figure:
        return go.Figure(data=self)

    def empty_traces(
        self,
    ) -> Self:
        self.data = []

        return self

    def add_title(
        self,
        title: str,
        /,
        *,
        edge: Literal["left", "right", "top", "bottom"] = "right",
        offset: float = 30,
        x_domain: tuple[float, float] = (0, 1),
        y_domain: tuple[float, float] = (0, 1),
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        annotations = _build_subplot_title_annotations(
            subplot_titles=[title],
            list_of_domains=[x_domain, y_domain],
            title_edge=edge,
            offset=offset,
        )

        for annotation in annotations:
            self.add_annotation(
                **{
                    **annotation,
                    **kwargs,
                },
            )

        return self

    def pipe(
        self,
        func: Callable[[Self], Self],
    ) -> Self:
        func(self)

        return self

    def adjust_layout(
        self,
        props: Sequence[str],
        /,
        *,
        callback: Callable[[Any | None], Any],
        fallback: bool = False,
    ) -> Self:
        current_value = get_layout_value(self.layout, props=props)

        if current_value is None and fallback:
            template_layout = get_template_layout(get_template())
            current_value = get_layout_value(template_layout, props=props)

        if isinstance(current_value, Layout):
            msg = "Do not adjust Layout instance directly"
            raise TypeError(msg)

        self.update_layout({"".join(props): callback(current_value)})

        return self

    def shift_title(
        self,
        offset: int,
    ) -> Self:
        self.adjust_layout(
            ["title", "pad", "b"],
            callback=lambda current_value: (current_value or 0) + offset,
        ).adjust_layout(
            ["margin", "t"],
            callback=lambda current_value: (current_value or 0) + offset,
        )

        return self

    def show(  # pyright: ignore[reportIncompatibleMethodOverride] # ty:ignore[invalid-method-override]
        self,
        *,
        renderer: str | None = None,
        validate: bool = True,
        width: float | None = None,
        height: float | None = None,
        config: Mapping[str, Any] | None = None,
        layout: Mapping[str, Any] | Layout | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        default_config: dict[str, Any] = {
            "showTips": False,
            "displaylogo": False,
            "displayModeBar": "hover",
        }

        final_config = default_config | dict(config or {})

        if layout is None and (width is not None or height is not None):
            layout = Layout()

        if layout is not None and not isinstance(layout, Layout):
            layout = Layout(dict(layout))

        if layout is not None:
            layout = layout.update({"width": width, "height": height})  # ty:ignore[invalid-assignment]

        fig = self.copy().update_layout(layout) if layout is not None else self  # pyright: ignore[reportArgumentType]  # ty:ignore[invalid-argument-type]

        go.Figure.show(
            self=fig,
            renderer=renderer,
            validate=validate,
            config=final_config,
            **kwargs,
        )

    def copy(
        self,
        description: str | None = None,
    ) -> Self:
        return type(self).from_existing(
            self,
            description=description or self.description,
        )

    def save(
        self,
        path: Path | str | None,
        /,
        *,
        formats: Sequence[str] = (),
        scale: int | None = 5,
        template: str | None = None,
        overwrite: bool = True,
        **kwargs: Any,  # noqa: ANN401
    ) -> Path:
        resolved, image_formats = resolve_save_path(
            path,
            suffixes=formats,
            overwrite=overwrite,
            default_directory=IMAGES_FOLDER,
            default_name=self.description,
            default_suffix="png",
        )

        if template is None:
            template = f"{get_default_template_name()}+plotly_white+save+save_white"

        for image_format in image_formats:
            self.copy().update_layout(
                template=template,
            ).write_image(
                file=resolved.with_suffix(suffix=f".{image_format}"),
                format=image_format,
                scale=scale,
                **kwargs,
            )

        return resolved.with_suffix(suffix=f".{next(iter(image_formats))}") if len(image_formats) == 0 else resolved.parent

    def __iter__(  # pyright: ignore[reportIncompatibleMethodOverride]  # ty:ignore[invalid-method-override]
        self,
    ) -> Iterator[Trace]:
        return iter(self.data)

    def set_bound_group_colours(
        self,
        *,
        fill_opacity: float = 0.1,
    ) -> Self:
        bound_groups: dict[str | int, tuple[tuple[str | None, int], list[Trace]]] = {}
        for idx, trace in enumerate(self):
            if (
                hasattr(trace, "legendgroup")
                and trace.legendgroup
                and isinstance(trace.legendgroup, str)
                and trace.legendgroup.startswith("_bounds_")
            ):
                if trace.legendgroup not in bound_groups:
                    bound_groups[trace.legendgroup] = ((None, 0), [])

                if trace.fill == "toself":
                    bound_groups[trace.legendgroup][1].append(trace)
                else:
                    bound_groups[trace.legendgroup] = ((trace.line.color, idx), bound_groups[trace.legendgroup][1])

        for (line_colour, idx), bound_traces in bound_groups.values():
            if line_colour is None:
                colour = Colour.parse(shuffled_colourscale[idx % len(shuffled_colourscale)])

                opacity = (
                    Colour.parse(bound_traces[0].fillcolor).a  # ty:ignore[invalid-argument-type]
                    if len(bound_traces) > 0 and hasattr(bound_traces[0], "fillcolor") and bound_traces[0].fillcolor is not None
                    else fill_opacity
                )
                for bound_trace in bound_traces:
                    bound_trace.fillcolor = colour.to_str(opacity=opacity)

        return self

    def set_trace_colours(
        self,
        *,
        fill_opacity: float = 0.1,
    ) -> Self:

        for idx, trace in enumerate(self):
            if isinstance(trace, go.Histogram) or trace.meta == TraceType.KDE:
                trace.marker.line.color = trace.marker.color or shuffled_colourscale[idx % len(shuffled_colourscale)]

            if trace.meta in {TraceType.LINE, TraceType.ECDF, TraceType.KDE}:
                trace.textfont.color = trace.line.color or trace.marker.color or shuffled_colourscale[idx % len(shuffled_colourscale)]
                if trace.meta in {TraceType.ECDF, TraceType.KDE}:
                    opacity = Colour.parse(trace.fillcolor).a if trace.fillcolor is not None else trace.opacity or fill_opacity
                    trace.fillcolor = Colour.parse(trace.textfont.color).to_str(opacity=opacity)

        return self

    def modifications(
        self,
        *,
        fill_opacity: float = 0.1,
    ) -> Self:
        self.set_trace_colours(fill_opacity=fill_opacity)
        self.set_bound_group_colours(fill_opacity=fill_opacity)

        return self

    def add_histogram_gaussians(
        self,
    ) -> Self:
        for idx, trace in enumerate(self):
            if isinstance(trace, go.Histogram):
                self.add_trace(
                    trace=Line(
                        x=(
                            gaussian_x := np.linspace(
                                start=min(trace.x),
                                stop=max(trace.x),
                                num=500,
                            )
                        ),
                        y=norm.pdf(
                            x=gaussian_x,
                            loc=(fit := norm.fit(data=trace.x))[0],
                            scale=fit[1],
                        ),
                        line={
                            "color": trace.marker.line.color,
                            "width": 0.8,
                            "dash": "dash",
                        },
                        opacity=0.9,
                        name=((str(trace.name) + " Gaussian") if trace.name else f"trace {idx} Gaussian"),
                        xaxis=trace.xaxis,
                        yaxis=trace.yaxis,
                        legendgroup=trace.legendgroup
                        or getattr(
                            set_inline(
                                parent_object=trace,
                                property_name="legendgroup",
                                value=idx,
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
        *,
        rug_type: Literal["scatter", "violin", "box", "strip", "histogram", "ecdf"] = "scatter",
        rug_height: float | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        if getattr(self, "_added_rugs", False):
            return self

        rug_count = 0
        traces: list[Trace] = []
        for idx, trace in enumerate(self):
            if isinstance(trace, go.Histogram):
                x = trace.x
            elif trace.meta == TraceType.KDE:
                x = trace.customdata
            else:
                continue
            rug_count += 1
            if rug_type == "scatter":
                traces.append(
                    go.Scatter(
                        x=x,
                        y=([rug_count] * len(x)),
                        xaxis="x1",
                        yaxis="y2",
                        mode="markers",
                        name=((str(trace.name) + " Rug") if trace.name else f"trace {idx} Rug"),
                        legendgroup=trace.legendgroup
                        or getattr(
                            set_inline(
                                parent_object=trace,
                                property_name="legendgroup",
                                value=idx,
                            ),
                            "legendgroup",
                            idx,
                        ),
                        showlegend=False,
                        marker={
                            "color": trace.marker.line.color,
                            "symbol": "line-ns-open",
                        },
                        **kwargs,
                    )
                )
            elif rug_type == "strip":
                traces.append(
                    go.Box(
                        x=x,
                        y=([rug_count] * len(x)),
                        xaxis="x1",
                        yaxis="y2",
                        orientation="h",
                        name=((str(trace.name) + " Rug") if trace.name else f"trace {idx} Rug"),
                        legendgroup=trace.legendgroup
                        or getattr(
                            set_inline(
                                parent_object=trace,
                                property_name="legendgroup",
                                value=idx,
                            ),
                            "legendgroup",
                            idx,
                        ),
                        showlegend=False,
                        line={
                            "color": TRANSPARENT.to_str(),
                        },
                        fillcolor=TRANSPARENT.to_str(),
                        marker={
                            "color": trace.marker.line.color,
                            "size": 4,
                        },
                        notched=True,
                        boxpoints="all",
                        hoveron="points",
                        width=0.6,
                        opacity=0.6,
                        jitter=0.6,
                        pointpos=0,
                        **kwargs,
                    )
                )
            elif rug_type == "box":
                traces.append(
                    go.Box(
                        x=x,
                        y=([rug_count] * len(x)),
                        xaxis="x1",
                        yaxis="y2",
                        orientation="h",
                        name=((str(trace.name) + " Rug") if trace.name else f"trace {idx} Rug"),
                        legendgroup=trace.legendgroup
                        or getattr(
                            set_inline(
                                parent_object=trace,
                                property_name="legendgroup",
                                value=idx,
                            ),
                            "legendgroup",
                            idx,
                        ),
                        showlegend=False,
                        line={
                            "color": trace.marker.line.color,
                        },
                        marker={
                            "color": trace.marker.line.color,
                            "size": 4,
                        },
                        notched=True,
                        boxpoints=kwargs.pop("points", kwargs.pop("boxpoints", "suspectedoutliers")),
                        width=0.4,
                        opacity=0.6,
                        jitter=0.6,
                        **kwargs,
                    )
                )
            elif rug_type == "violin":
                traces.append(
                    go.Violin(  # pyright: ignore[reportArgumentType]
                        x=x,
                        y=([rug_count] * len(x)),
                        xaxis="x1",
                        yaxis="y2",
                        orientation="h",
                        name=((str(trace.name) + " Rug") if trace.name else f"trace {idx} Rug"),
                        legendgroup=trace.legendgroup
                        or getattr(
                            set_inline(
                                parent_object=trace,
                                property_name="legendgroup",
                                value=idx,
                            ),
                            "legendgroup",
                            idx,
                        ),
                        showlegend=False,
                        line={
                            "color": trace.marker.line.color,
                        },
                        marker={
                            "color": trace.marker.line.color,
                            "size": 5,
                        },
                        scalegroup="added_rug",
                        points=kwargs.pop("points", "suspectedoutliers"),
                        opacity=0.6,
                        jitter=0.6,
                        width=1,
                        side="positive",
                        **kwargs,
                    )
                )
            elif rug_type == "histogram":
                msg = "Histogram not implemented"
                raise NotImplementedError(msg)
            elif rug_type == "ecdf":
                traces.append(
                    Ecdf(
                        x=x,
                        y_shift=rug_count,
                        xaxis="x1",
                        yaxis="y2",
                        name=((str(trace.name) + " Rug") if trace.name else f"trace {idx} Rug"),
                        legendgroup=trace.legendgroup
                        or getattr(
                            set_inline(
                                parent_object=trace,
                                property_name="legendgroup",
                                value=idx,
                            ),
                            "legendgroup",
                            idx,
                        ),
                        showlegend=False,
                        line={
                            "color": trace.marker.line.color,
                        },
                        fill="toself",
                        **kwargs,
                    )
                )
            else:
                msg = f"Rug type {rug_type} is unknown"
                raise ValueError(msg)

        if rug_count > 0:
            height = rug_height or (0.15 if rug_type == "scatter" else 0.3)

            self.update_layout(
                yaxis1={
                    "domain": [height + 0.1, 1],
                },
                yaxis2={
                    "anchor": "x1",
                    "dtick": 1,
                    "showticklabels": False,
                    "domain": [0, height],
                    "fixedrange": True,
                    "showline": True,
                    "showgrid": False,
                    "minor": {"showgrid": False},
                },
            )

            self.add_traces(data=traces)
            self.modifications()

            self._added_rugs = True

        return self

    def trace(
        self,
        idx: int,
        /,
    ) -> Trace:
        return self.data[idx]

    def get_traces_by_type(
        self,
        trace_type: str,
        /,
    ) -> Iterator[tuple[int, Trace]]:
        trace_cls = TRACE_IDENTIFIERS.get(trace_type)

        return (
            (idx, trace)
            for idx, trace in enumerate(self)
            if (trace_cls is not None and isinstance(trace, trace_cls))
            or (getattr(trace, "meta", None) == trace_type and isinstance(trace_type, TraceType))
        )

    def add_button(
        self,
        button: Mapping[str, Any],
        /,
        *,
        menu_index: int = 0,
    ) -> Self:
        existing_menus: list[dict[str, Any]] = [menu.to_plotly_json() for menu in (self.layout.updatemenus or ())]

        if menu_index < len(existing_menus):
            existing_menus[menu_index].setdefault("buttons", [{}]).append(dict(button))
        else:
            existing_menus.append({"buttons": [{}, dict(button)]})

        self.update_layout(updatemenus=existing_menus)

        return self

    def add_histogram_to_2d_scatter(
        self,
        *,
        colour: Colour | None = None,
        index_used: int = 99,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        if colour is None:
            colour = Colour.parse("red")

        kwargs = {
            "opacity": 0.5,
            "hoverinfo": "skip",
            "showlegend": False,
            "visible": False,
        } | kwargs

        trace_count_before = self.num_traces

        self.add_traces(
            data=[
                go.Histogram2d(  # pyright: ignore[reportArgumentType]
                    x=np.concatenate([trace.x for trace in traces]),  # ty:ignore[unresolved-attribute]
                    y=np.concatenate([trace.y for trace in traces]),  # ty:ignore[unresolved-attribute]
                    xaxis=xaxis,
                    yaxis=yaxis,
                    bingroup=index_used,
                    coloraxis=f"coloraxis{index_used}",
                    **kwargs,
                )
                for (xaxis, yaxis), traces in sort_traces_by_axes(
                    [trace for _, trace in self.get_traces_by_type(TraceType.SCATTER)]
                ).items()
            ]
        ).update_layout(
            {
                f"coloraxis{index_used}": {
                    "colorscale": [
                        [0.0, colour.to_str(opacity=0.0)],
                        [0.1, colour.to_str(opacity=0.1)],
                        [0.2, colour.to_str(opacity=0.2)],
                        [0.5, colour.to_str(opacity=0.5)],
                        [1.0, colour.to_str(opacity=1.0)],
                    ],
                    "colorbar": {"title_text": "Density"},
                }
            }
        )

        density_indices = list(range(trace_count_before, self.num_traces))
        if density_indices:
            self.add_button(
                {
                    "label": "Toggle Density",
                    "method": "restyle",
                    "args": [{"visible": True}, density_indices],
                    "args2": [{"visible": False}, density_indices],
                }
            )

        return self

    def add_kde_to_histogram(
        self,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        kwargs = {
            "opacity": 0.9,
            "showlegend": False,
            "label_name": False,
            "line_width": 0.8,
            "fill": None,
        } | kwargs

        self.add_traces(
            data=[
                Kde(
                    x=trace.x,  # ty:ignore[unresolved-attribute]
                    line_color=trace.marker.line.color,  # ty:ignore[unresolved-attribute]
                    name=(str(trace.name) + " KDE") if trace.name else f"trace {idx} KDE",  # ty:ignore[unresolved-attribute]
                    xaxis=trace.xaxis,  # ty:ignore[unresolved-attribute]
                    yaxis=trace.yaxis,  # ty:ignore[unresolved-attribute]
                    legendgroup=trace.legendgroup  # ty:ignore[unresolved-attribute]
                    or getattr(
                        set_inline(
                            parent_object=trace,
                            property_name="legendgroup",
                            value=idx,
                        ),
                        "legendgroup",
                        idx,
                    ),
                    **kwargs,
                )
                for idx, trace in self.get_traces_by_type("histogram")
            ],
        )

        return self

    def add_heatmap_alternative_to_3d_bar(
        self,
    ) -> Self:
        bar3d_indices = {idx for idx, _ in self.get_traces_by_type(TraceType.BAR3D)}

        if not bar3d_indices:
            return self

        self.add_button(
            {
                "label": "3D Bar",
                "method": "restyle",
                "args": [
                    {
                        "type": ["mesh3d"] * self.num_traces,
                        "x": [trace.x for trace in self],  # ty:ignore[unresolved-attribute]
                        "y": [trace.y for trace in self],  # ty:ignore[unresolved-attribute]
                        "z": [trace.z for trace in self],  # ty:ignore[unresolved-attribute]
                    },
                ],
            },
        ).add_button(
            {
                "label": "Heatmap",
                "method": "restyle",
                "args": [
                    {
                        "type": ["heatmap"] * self.num_traces,
                        "x": [trace.customdata[::8, 0] for trace in self],  # ty:ignore[unresolved-attribute]
                        "y": [trace.customdata[::8, 1] for trace in self],  # ty:ignore[unresolved-attribute]
                        "z": [trace.customdata[::8, 2] for trace in self],  # ty:ignore[unresolved-attribute]
                    },
                ],
            },
        )

        return self

    def add_default_extras(
        self,
    ) -> Self:
        self.add_histogram_to_2d_scatter()
        self.add_kde_to_histogram()
        self.add_heatmap_alternative_to_3d_bar()

        return self

    def add_interval(
        self,
        interval: Interval[Date] | Interval[DateTime] | None,
        /,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        if interval is None:
            return self

        kwargs = {"line_width": 0, "opacity": 0.1} | kwargs

        self.add_vrect(
            x0=interval.start.as_base,  # ty:ignore[invalid-argument-type] # pyright: ignore[reportArgumentType]
            x1=interval.end.as_base,  # ty:ignore[invalid-argument-type] # pyright: ignore[reportArgumentType]
            **kwargs,
        )

        return self

    def hide_traces(
        self,
        names: Sequence[str],
        /,
    ) -> Self:
        for name in names:
            self.update_traces(
                visible="legendonly",
                selector={"name": name},
            )

        return self

    def set_visible_y_range(
        self,
        *,
        y_padding: float = 0.05,
    ) -> Self:
        xaxis_range: tuple[Any, Any] | None = getattr(self.layout.xaxis, "range", None)
        if xaxis_range is None:
            msg = "X-axis range must be set to determine visible y-axis range"
            raise ValueError(msg)

        yaxes = sorted([prop for prop in self.layout if prop.startswith("yaxis")])

        observed_idxs: set[int] = set()
        full_trace_limits: dict[str, NDArray[np.float64]] = {}
        for yaxis in yaxes:
            trace_limits: list[tuple[float, float]] = []
            for idx, trace in enumerate(self):
                if idx in observed_idxs:
                    continue

                if trace.visible not in [None, True]:
                    observed_idxs.add(idx)
                    continue

                y = np.asarray(trace.y, dtype=np.float64) if trace.y is not None else None
                if not isinstance(
                    trace.y, (np.ndarray, Series, list, tuple)
                ):  # TODO(@mayurankv): Can this be made more general?  # noqa: TD003
                    observed_idxs.add(idx)
                    continue

                trace_yaxes_name = trace.yaxis.replace("y", "yaxis") if trace.yaxis is not None else "yaxis"
                trace_yaxis_object = getattr(
                    self.layout,
                    trace_yaxes_name,
                    None,
                )

                if trace_yaxis_object is None:
                    observed_idxs.add(idx)
                    continue

                matching_yaxis_name = (
                    matching_yaxis.replace("y", "yaxis") if (matching_yaxis := trace_yaxis_object.matches) is not None else None
                )
                if yaxis not in {matching_yaxis_name, trace_yaxes_name}:
                    continue

                x = np.asarray(
                    trace.x
                    if len(trace.x) > 0 and isinstance(trace.x[0], (datetime.date, datetime.datetime))
                    else cast("Series", to_pandas_datetime(trace.x)).date
                )
                if len(x) == 0:
                    observed_idxs.add(idx)
                    continue

                visible_mask: NDArray[np.bool_] = (x < xaxis_range[1]) & (x > xaxis_range[0])
                if not visible_mask.any():
                    observed_idxs.add(idx)
                    continue

                y_visible = cast("NDArray[np.float64]", y)[visible_mask]
                if y_visible.shape == (0,) or np.isnan(y_visible).all():
                    observed_idxs.add(idx)
                    continue

                trace_limits.append((np.nanmin(y_visible), np.nanmax(y_visible)))

            full_trace_limits[yaxis] = (
                np.asarray(trace_limits, dtype=np.float64) if len(trace_limits) > 0 else np.empty(shape=(0, 2), dtype=np.float64)
            )

        overall_trace_limits = {
            f"{yaxis}_range": (
                np.nanmin(limits[:, 0]) if not np.isnan(limits[:, 0]).all() else None,
                np.nanmax(limits[:, 1]) if not np.isnan(limits[:, 1]).all() else None,
            )
            for yaxis, limits in full_trace_limits.items()
            if limits.shape[0] > 0
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
            for yaxis_range, (y_min, y_max) in overall_trace_limits.items()
        }

        self.update_layout(padded_trace_limits)

        return self

    def __call__(
        self,
        *,
        save: bool = True,
        show: bool = True,
    ) -> Self:
        if save:
            self.save(None)

        if show:
            self.show()

        return self
