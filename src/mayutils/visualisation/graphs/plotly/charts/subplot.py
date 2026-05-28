from collections.abc import Mapping
from typing import Any, cast

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from plotly.subplots import make_subplots

from mayutils.visualisation.graphs.plotly.charts import (
    PlotConfig,
    SubPlotConfig,
    TracesConfig,
    get_domain_fraction,
    pop_axis_config_title,
)
from mayutils.visualisation.graphs.plotly.charts.plot import Plot
from mayutils.visualisation.graphs.plotly.templates import (
    axis_structure_dict,
    non_primary_axis_structure_dict,
)
from mayutils.visualisation.graphs.plotly.traces import (
    Null,
    is_trace_3d,
)


class SubPlot(Plot):
    def __init__(
        self,
        config: SubPlotConfig,
        /,
        *,
        description: str,
        layout: Mapping[str, Any] | None = None,
        fill_nulls: bool = True,
        x_spacing: float | None = None,
        y_spacing: float | None = None,
        title_styles: Mapping[str, Any] | None = None,
        line_title_offsets: tuple[float, float] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        if layout is None:
            layout = {}

        self._specs: list[list[dict[str, str | int | float]]] = [
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
            for row_configs in config.plots
        ]

        super().__init__(
            PlotConfig.empty(),
            description=description,
            layout={},
            data=make_subplots(
                rows=len(config.plots),
                cols=len(config.plots[0]),
                specs=cast("list[list[dict[str, str | int | float] | None]]", self._specs),
            ),
            **kwargs,
        )
        self._config = config
        self.update_layout(
            dict(layout),
        )

        self._x_domains, self._y_domains = self._config.get_domains(
            x_spacing=x_spacing,
            y_spacing=y_spacing,
        )
        self.add_titles(
            title_styles=title_styles,
            line_title_offsets=line_title_offsets,
        )
        self.add_plots(
            fill_nulls=fill_nulls,
        )

        self.modifications()

    def add_titles(  # noqa: C901
        self,
        *,
        title_styles: Mapping[str, Any] | None = None,
        line_title_offsets: tuple[float, float] | None = None,
    ) -> None:
        if title_styles is None:
            line_title_styles: dict[str, Any] = {}
            plot_title_styles: dict[str, Any] = {}
        else:
            line_title_styles = title_styles.get("line", {})
            plot_title_styles = title_styles.get("plot", {})

        line_title_styles = {"font_weight": 700, "font_size": 12} | line_title_styles

        if line_title_offsets is None:
            line_title_offsets = (22.5, 22.5)

        xaxis_title = pop_axis_config_title(self._config.main_axis_configs.xaxis.config)
        yaxes_titles = [
            pop_axis_config_title(self._config.main_axis_configs.yaxes[idx].config)
            for idx in range(len(self._config.main_axis_configs.yaxes))
        ]

        if self._config.titles.rows is not None:
            self.adjust_layout(
                ["margin", "l"],
                callback=lambda margin_l: (margin_l or 0) + 20,
                fallback=True,
            )
        for row_idx, row_title in enumerate((self._config.titles.rows or [])[::-1]):
            self.add_title(
                row_title,
                edge="left",
                x_domain=(
                    self._x_domains[0][0],
                    self._x_domains[0][1],
                ),
                y_domain=(
                    self._y_domains[row_idx][0],
                    self._y_domains[row_idx][1],
                ),
                offset=line_title_offsets[0],
                **line_title_styles,
            )

        if self._config.titles.cols is not None:
            self.adjust_layout(
                ["margin", "b"],
                callback=lambda margin_b: (margin_b or 0) + 20,
                fallback=True,
            )
        for col_idx, col_title in enumerate(self._config.titles.cols or []):
            self.add_title(
                col_title,
                edge="bottom" if not self._config.titles.cols_top else "top",
                x_domain=(
                    self._x_domains[col_idx][0],
                    self._x_domains[col_idx][1],
                ),
                y_domain=(
                    self._y_domains[0 if not self._config.titles.cols_top else -1][0],
                    self._y_domains[0 if not self._config.titles.cols_top else -1][1],
                ),
                offset=line_title_offsets[1],
                **line_title_styles,
            )

        for row_idx, row_titles in enumerate((self._config.titles.plots or [])[::-1]):
            for col_idx, plot_title in enumerate(row_titles):
                self.add_title(
                    plot_title or "",
                    edge="top",
                    x_domain=(
                        self._x_domains[col_idx][0],
                        self._x_domains[col_idx][1],
                    ),
                    y_domain=(
                        self._y_domains[row_idx][0],
                        self._y_domains[row_idx][1],
                    ),
                    offset=0,
                    **plot_title_styles,
                )

        self.update_layout(
            title_text=self._config.titles.main,
        )

        if xaxis_title is not None:
            self.add_title(
                xaxis_title,
                edge="bottom",
                x_domain=(0, self._x_domains[-1][-1]),
                offset=30 if self._config.titles.cols is None else 40,
            )

        for axis_idx, yaxis_title in enumerate(yaxes_titles):
            if yaxis_title is not None:
                self.add_title(
                    yaxis_title,
                    edge="left" if axis_idx == 0 else "right",
                    offset=30 if self._config.titles.rows is None or axis_idx != 0 else 40,
                    x_domain=(
                        0,
                        get_domain_fraction(
                            axis_idx=axis_idx,
                            max_yaxis=self._config.max_yaxis,
                        ),
                    ),
                    y_domain=(0, self._y_domains[-1][-1]),
                )

    def add_plots(
        self,
        *,
        fill_nulls: bool = True,
    ) -> None:
        x_datetime = self._config.infer_x_datetime()

        scene_count = 0
        for row_idx, (row_plot_configs, row_specs) in enumerate(zip(self._config.plots, self._specs, strict=False)):
            for col_idx, (plot_config, plot_spec) in enumerate(zip(row_plot_configs, row_specs, strict=False)):
                used_plot_config = (
                    PlotConfig(
                        yaxes_configs=(
                            TracesConfig.from_trace(
                                Null(x_datetime=x_datetime),
                                yaxis_config={},
                            ),
                        ),
                    )
                    if plot_config is None
                    else plot_config
                )

                is_scene: bool = plot_spec.get("type", False) == "surface"
                if is_scene:
                    scene_count += 1
                    scene_str = str(scene_count) if scene_count != 1 else ""
                else:
                    scene_str = ""

                xaxis_num = col_idx + row_idx * len(self._config.plots[0]) + 1 - scene_count
                xaxis_str = str(xaxis_num) if xaxis_num != 1 else ""

                self.update_layout(
                    {
                        "scene": {
                            "domain": {
                                "x": self._x_domains[col_idx],
                                "y": self._y_domains[::-1][row_idx],
                            }
                        },
                    }
                    if is_scene
                    else {
                        f"xaxis{xaxis_str}": {
                            **axis_structure_dict,
                            **self._config.main_axis_configs.xaxis.config,
                            **used_plot_config.xaxis_config,
                            "matches": "x" if self._config.main_axis_configs.xaxis.mode != "independent" else None,
                            "domain": self._x_domains[col_idx],
                            "showticklabels": (self._config.main_axis_configs.xaxis.mode != "collapsed")
                            or (row_idx == len(self._config.plots) - 1),
                        },
                    }
                )

                for axis_idx in range(self._config.max_yaxis):
                    yaxis_num = self._config.plot_count * axis_idx + xaxis_num
                    yaxis_str = str(yaxis_num) if yaxis_num != 1 else ""
                    iaxis_num = self._config.plot_count * axis_idx + 1
                    iaxis_str = str(iaxis_num) if iaxis_num != 1 else ""

                    y_axis_details = self._config.main_axis_configs.yaxes[axis_idx]

                    if not is_scene:
                        self.update_layout(
                            {
                                f"yaxis{yaxis_str}": {
                                    **(
                                        axis_structure_dict
                                        if axis_idx == 0
                                        else {
                                            **non_primary_axis_structure_dict,
                                            "position": get_domain_fraction(
                                                axis_idx=axis_idx,
                                                max_yaxis=self._config.max_yaxis,
                                            ),
                                            "overlaying": f"y{xaxis_str}",
                                            "anchor": f"x{xaxis_str}" if axis_idx == 1 and y_axis_details.mode != "collapsed" else "free",
                                        }
                                    ),
                                    "matches": f"y{iaxis_str}" if y_axis_details.mode != "independent" else None,
                                    "domain": self._y_domains[::-1][row_idx],
                                    "showticklabels": (y_axis_details.mode != "collapsed") or (col_idx == 0),
                                    **y_axis_details.config,
                                },
                            },
                        )

                    if len(used_plot_config.yaxes_configs) > axis_idx:
                        traces_config = used_plot_config.yaxes_configs[axis_idx]
                        if not is_scene:
                            self.update_layout({f"yaxis{yaxis_str}": traces_config.yaxis_config})
                        traces = traces_config.traces
                    else:
                        traces = (
                            (
                                Null(
                                    x_datetime=x_datetime,
                                ),
                            )
                            if fill_nulls and not is_scene
                            else ()
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
