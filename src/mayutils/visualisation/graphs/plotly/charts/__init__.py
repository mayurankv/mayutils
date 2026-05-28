"""Configuration dataclasses and helpers for composing Plotly subplot layouts."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from math import ceil, isqrt
from typing import Any, Literal, Self, cast

from mayutils.core.extras import may_require_extras
from mayutils.objects.datetime import DateTime

with may_require_extras():
    import datetime

    from plotly.basedatatypes import BaseTraceType

AxisConfig = Mapping[str, Any]
Trace = BaseTraceType

DEFAULT_YAXIS_NUM = 1


@dataclass
class TracesConfig:
    """
    A group of traces that share a common y-axis configuration.

    Bundles one or more plotly traces with a shared y-axis layout so they can
    be composed into a ``PlotConfig`` subplot cell.

    Attributes
    ----------
    traces
        The plotly traces belonging to this group.
    yaxis_config
        Layout properties applied to the shared y-axis.

    See Also
    --------
    PlotConfig : Combines one or more ``TracesConfig`` with an x-axis.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.charts import TracesConfig
    >>> config = TracesConfig(traces=())
    """

    traces: tuple[Trace, ...]
    yaxis_config: AxisConfig = field(default_factory=lambda: cast("AxisConfig", {}))

    @classmethod
    def from_trace(
        cls,
        trace: Trace,
        /,
        *,
        yaxis_config: AxisConfig | None = None,
    ) -> "TracesConfig":
        """
        Create a ``TracesConfig`` from a single trace.

        Convenience constructor that wraps a lone trace into a one-element
        tuple so callers do not need to construct the tuple themselves.

        Parameters
        ----------
        trace
            The plotly trace to wrap.
        yaxis_config
            Optional y-axis layout overrides.

        Returns
        -------
        TracesConfig
            A new instance containing the single trace.

        See Also
        --------
        PlotConfig.from_trace : Shortcut that also wraps the x-axis config.

        Examples
        --------
        >>> from mayutils.visualisation.graphs.plotly.charts import TracesConfig
        >>> config = TracesConfig.from_trace.__doc__ is not None
        True
        """
        if yaxis_config is None:
            yaxis_config = {}

        return cls(
            traces=(trace,),
            yaxis_config=yaxis_config,
        )


@dataclass
class PlotConfig:
    """
    Configuration for a single subplot cell with its x-axis and y-axes.

    Holds one or more ``TracesConfig`` groups together with a shared x-axis
    configuration, representing a single cell in a subplot grid.

    Attributes
    ----------
    yaxes_configs
        One ``TracesConfig`` per y-axis in this cell.
    xaxis_config
        Layout properties applied to the x-axis.

    See Also
    --------
    TracesConfig : Groups traces that share a y-axis.
    SubPlotConfig : Arranges multiple ``PlotConfig`` cells in a grid.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.charts import PlotConfig
    >>> config = PlotConfig.empty()
    """

    yaxes_configs: tuple[TracesConfig, ...]
    xaxis_config: AxisConfig = field(default_factory=lambda: cast("AxisConfig", {}))

    @classmethod
    def empty(
        cls,
    ) -> "PlotConfig":
        """
        Create an empty ``PlotConfig`` with no traces or axis overrides.

        Useful as a placeholder for blank cells in a subplot grid where no
        data should be rendered.

        Returns
        -------
        PlotConfig
            An instance with empty y-axes configs and x-axis config.

        See Also
        --------
        PlotConfig.from_trace : Build from a single trace.

        Examples
        --------
        >>> from mayutils.visualisation.graphs.plotly.charts import PlotConfig
        >>> PlotConfig.empty().yaxes_configs
        ()
        """
        return cls(
            yaxes_configs=(),
            xaxis_config={},
        )

    @classmethod
    def from_trace(
        cls,
        trace: Trace,
        /,
        *,
        yaxis_config: AxisConfig | None = None,
        xaxis_config: AxisConfig | None = None,
    ) -> "PlotConfig":
        """
        Create a ``PlotConfig`` from a single trace.

        Wraps a single trace into a ``TracesConfig`` and then into a
        ``PlotConfig`` in one step, avoiding boilerplate nesting.

        Parameters
        ----------
        trace
            The plotly trace.
        yaxis_config
            Optional y-axis layout overrides.
        xaxis_config
            Optional x-axis layout overrides.

        Returns
        -------
        PlotConfig
            A new instance wrapping the trace.

        See Also
        --------
        PlotConfig.from_traces : Build from multiple traces sharing one y-axis.
        TracesConfig.from_trace : Lower-level single-trace constructor.

        Examples
        --------
        >>> from mayutils.visualisation.graphs.plotly.charts import PlotConfig
        >>> PlotConfig.from_trace.__doc__ is not None
        True
        """
        if yaxis_config is None:
            yaxis_config = {}
        if xaxis_config is None:
            xaxis_config = {}

        return cls(
            yaxes_configs=(
                TracesConfig.from_trace(
                    trace,
                    yaxis_config=yaxis_config,
                ),
            ),
            xaxis_config=xaxis_config,
        )

    @classmethod
    def from_traces(
        cls,
        *traces: Trace,
        yaxis_config: AxisConfig | None = None,
        xaxis_config: AxisConfig | None = None,
    ) -> "PlotConfig":
        """
        Create a ``PlotConfig`` from multiple traces sharing one y-axis.

        Groups several traces under a single ``TracesConfig`` with a common
        y-axis, then wraps them into a ``PlotConfig``.

        Parameters
        ----------
        *traces
            One or more plotly traces.
        yaxis_config
            Optional y-axis layout overrides.
        xaxis_config
            Optional x-axis layout overrides.

        Returns
        -------
        PlotConfig
            A new instance grouping all traces under a single y-axis.

        See Also
        --------
        PlotConfig.from_trace : Build from a single trace.

        Examples
        --------
        >>> from mayutils.visualisation.graphs.plotly.charts import PlotConfig
        >>> PlotConfig.from_traces.__doc__ is not None
        True
        """
        if yaxis_config is None:
            yaxis_config = {}
        if xaxis_config is None:
            xaxis_config = {}

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
    """
    Title configuration for a subplot grid.

    Stores main, row, column, and per-cell titles that are applied as
    annotations when rendering a ``SubPlotConfig`` grid.

    Attributes
    ----------
    main
        The overall chart title.
    rows
        Per-row annotation titles shown on the right.
    cols
        Per-column annotation titles shown at the top or bottom.
    plots
        Per-cell titles, as a nested tuple matching the grid shape.
    cols_top
        Whether column titles appear above the plot area.

    See Also
    --------
    SubPlotConfig : Uses ``Titles`` to annotate subplot grids.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.charts import Titles
    >>> titles = Titles(main="My Chart")
    """

    main: str = ""
    rows: tuple[str, ...] | None = None
    cols: tuple[str, ...] | None = None
    plots: tuple[tuple[str | None, ...], ...] | None = None
    cols_top: bool = False

    def __post_init__(
        self,
    ) -> None:
        r"""
        Replace newline characters with HTML line breaks in all title strings.

        Iterates over ``main``, ``rows``, ``cols``, and ``plots`` and converts
        every ``\n`` to ``<br>`` so plotly renders multi-line titles correctly.

        See Also
        --------
        SubPlotConfig.__post_init__ : Validates grid dimensions after titles
            are sanitised.

        Examples
        --------
        >>> from mayutils.visualisation.graphs.plotly.charts import Titles
        >>> Titles(main="line1\nline2").main
        'line1<br>line2'
        """
        self.main = self.main.replace("\n", "<br>")
        self.rows = self.rows if self.rows is None else tuple(row.replace("\n", "<br>") for row in self.rows)
        self.cols = self.cols if self.cols is None else tuple(col.replace("\n", "<br>") for col in self.cols)
        self.plots = (
            self.plots
            if self.plots is None
            else tuple(
                tuple(plot_title.replace("\n", "<br>") if plot_title is not None else "" for plot_title in row_titles)
                for row_titles in self.plots
            )
        )


@dataclass
class MainAxisConfig:
    """
    Axis behaviour and layout overrides shared across a subplot dimension.

    Controls how an axis is linked across subplot cells and carries any
    additional plotly layout properties for that axis.

    Attributes
    ----------
    config
        Layout properties forwarded to the plotly axis.
    mode
        How axes are linked across subplots: ``"independent"`` gives each
        subplot its own range, ``"shared"`` synchronises ranges, and
        ``"collapsed"`` merges axes into one.

    See Also
    --------
    MainAxisConfigs : Bundles x-axis and y-axes ``MainAxisConfig`` together.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.charts import MainAxisConfig
    >>> MainAxisConfig(mode="shared")
    MainAxisConfig(config={}, mode='shared')
    """

    config: AxisConfig = field(default_factory=lambda: cast("AxisConfig", {}))
    mode: Literal["independent", "shared", "collapsed"] = "collapsed"

    @classmethod
    def from_dict(
        cls,
        *,
        mode: Literal["independent", "shared", "collapsed"] = "collapsed",
        **kwargs: object,
    ) -> Self:
        """
        Build a ``MainAxisConfig`` from keyword arguments.

        Collects arbitrary axis layout properties into the ``config`` dict
        without requiring callers to construct the mapping manually.

        Parameters
        ----------
        mode
            Axis linking mode.
        **kwargs
            Additional axis layout properties.

        Returns
        -------
        MainAxisConfig
            A new instance with the given mode and config dict.

        See Also
        --------
        MainAxisConfigs : Holds the x and y ``MainAxisConfig`` instances.

        Examples
        --------
        >>> from mayutils.visualisation.graphs.plotly.charts import MainAxisConfig
        >>> MainAxisConfig.from_dict(mode="shared", title_text="Time")
        MainAxisConfig(config={'title_text': 'Time'}, mode='shared')
        """
        return cls(
            config=dict(
                **kwargs,
            ),
            mode=mode,
        )


@dataclass
class MainAxisConfigs:
    """
    Bundle of main axis configurations for x and y dimensions.

    Groups the x-axis and all y-axis ``MainAxisConfig`` instances so they can
    be passed as a single unit to ``SubPlotConfig``.

    Attributes
    ----------
    xaxis
        Configuration for the shared x-axis behaviour.
    yaxes
        Per-y-axis configurations; length is padded automatically by
        ``SubPlotConfig.__post_init__``.

    See Also
    --------
    MainAxisConfig : Individual axis configuration.
    SubPlotConfig : Consumes ``MainAxisConfigs`` when building a grid.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.charts import MainAxisConfigs
    >>> MainAxisConfigs().yaxes
    ()
    """

    xaxis: MainAxisConfig = field(default_factory=MainAxisConfig)
    yaxes: tuple[MainAxisConfig, ...] = ()


@dataclass
class SubPlotConfig:
    """
    Full specification of a subplot grid layout.

    Combines a 2-D grid of ``PlotConfig`` cells with shared axis settings and
    title annotations, providing everything needed to render a multi-panel chart.

    Attributes
    ----------
    plots
        2-D tuple of ``PlotConfig`` cells (``None`` for empty cells).
    main_axis_configs
        Shared axis behaviour across the grid.
    titles
        Titles for the overall chart, rows, columns, and individual cells.

    See Also
    --------
    PlotConfig : Configuration for a single subplot cell.
    Titles : Title annotations applied to the grid.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.charts import SubPlotConfig, PlotConfig
    >>> SubPlotConfig(plots=((PlotConfig.empty(),),))
    SubPlotConfig(plots=...
    """

    plots: tuple[tuple[PlotConfig | None, ...], ...]
    main_axis_configs: MainAxisConfigs = field(default_factory=MainAxisConfigs)
    titles: Titles = field(default_factory=Titles)

    def __post_init__(
        self,
    ) -> None:
        """
        Validate grid dimensions, title lengths, and pad y-axis configs.

        Ensures the grid is non-empty and rectangular, checks that title
        tuples match the grid shape, and extends ``yaxes`` to cover all cells.

        Raises
        ------
        ValueError
            If the grid is empty, rows have inconsistent lengths, or title
            tuple lengths do not match the grid dimensions.

        See Also
        --------
        Titles.__post_init__ : Sanitises title strings before this validation.

        Examples
        --------
        >>> from mayutils.visualisation.graphs.plotly.charts import SubPlotConfig, PlotConfig
        >>> cfg = SubPlotConfig(plots=((PlotConfig.empty(),),))
        >>> cfg.titles.plots is not None
        True
        """
        if len(self.plots) == 0:
            msg = "Plots is empty"
            raise ValueError(msg)
        if any(len(self.plots[0]) != len(row) for row in self.plots[1:]):
            msg = "Subplot layout has inconsistent row lengths"
            raise ValueError(msg)
        if self.titles.rows is not None and len(self.titles.rows) != len(self.plots):
            msg = f"Row titles are of length {len(self.titles.rows)} whilst plots have {len(self.plots)} rows"
            raise ValueError(msg)
        if self.titles.cols is not None and len(self.titles.cols) != len(self.plots[0]):
            msg = f"Column titles are of length {len(self.titles.cols)} whilst plots have {len(self.plots[0])} columns"
            raise ValueError(msg)
        if self.titles.plots is not None and len(self.titles.plots) != len(self.plots):
            msg = f"Subplot titles have {len(self.titles.plots)} rows whilst there are {len(self.plots)} subplot rows"
            raise ValueError(msg)
        if self.titles.plots is not None and len(self.titles.plots[0]) != len(self.plots[0]):
            msg = f"Subplot titles have {len(self.titles.plots[0])} columns whilst there are {len(self.plots[0])} subplot columns"
            raise ValueError(msg)

        if self.titles.plots is None:
            self.titles.plots = tuple(tuple("" for _ in range(len(self.plots[0]))) for _ in range(len(self.plots)))

        self.main_axis_configs.yaxes = (self.main_axis_configs.yaxes + tuple(MainAxisConfig() for _ in range(self.max_yaxis)))[
            : self.max_yaxis
        ]

    @classmethod
    def flat(
        cls,
        plots: tuple[PlotConfig | None, ...],
        /,
        *,
        cols: int | None = None,
        main_axis_configs: MainAxisConfigs | None = None,
        titles: Titles | None = None,
    ) -> Self:
        """
        Arrange a flat sequence of plots into a grid with automatic row wrapping.

        Distributes cells row-by-row into a rectangular grid, padding with
        ``None`` where necessary to fill the last row.

        Parameters
        ----------
        plots
            Flat sequence of plot configs (``None`` for empty cells).
        cols
            Number of columns; defaults to a near-square layout.
        main_axis_configs
            Optional shared axis behaviour.
        titles
            Optional title annotations.

        Returns
        -------
        SubPlotConfig
            A grid-shaped subplot configuration.

        See Also
        --------
        SubPlotConfig : Direct constructor accepting a 2-D grid.

        Examples
        --------
        >>> from mayutils.visualisation.graphs.plotly.charts import SubPlotConfig, PlotConfig
        >>> grid = SubPlotConfig.flat((PlotConfig.empty(),), cols=1)
        """
        if cols is None:
            cols = isqrt(len(plots) - 1) + 1
        if main_axis_configs is None:
            main_axis_configs = MainAxisConfigs()
        if titles is None:
            titles = Titles()

        rows = ceil(len(plots) / cols)

        extended_plots = list(plots) + [None] * (cols * rows - len(plots))

        return cls(
            plots=tuple(tuple(extended_plots[idx : idx + cols]) for idx in range(0, len(extended_plots), cols)),
            main_axis_configs=main_axis_configs,
            titles=titles,
        )

    @property
    def max_yaxis(
        self,
    ) -> int:
        return max(
            len(plot_config.yaxes_configs) if plot_config is not None else 0
            for row_plot_configs in self.plots
            for plot_config in row_plot_configs
        )

    @property
    def plot_count(
        self,
    ) -> int:
        return len(self.plots) * len(self.plots[0])

    def get_domains(
        self,
        *,
        x_spacing: float | None = None,
        y_spacing: float | None = None,
    ) -> tuple[list[list[float]], list[list[float]]]:
        default_spacing = {
            "x": {
                "collapsed": 0.01,
                "shared": 0.06,
                "independent": 0.06,
            },
            "y": {
                "collapsed": 0.025,
                "shared": 0.08,
                "independent": 0.08,
            },
        }

        x_spacing = (
            x_spacing
            if x_spacing is not None
            else (
                default_spacing["x"]["collapsed"]
                if all(yaxis_info.mode == "collapsed" for yaxis_info in self.main_axis_configs.yaxes)
                else (
                    default_spacing["x"]["independent"]
                    if any(yaxis_info.mode == "independent" for yaxis_info in self.main_axis_configs.yaxes)
                    else default_spacing["x"]["shared"]
                )
            )
        )
        y_spacing = (
            y_spacing
            if y_spacing is not None
            else (
                default_spacing["y"]["collapsed"]
                if self.main_axis_configs.xaxis.mode == "collapsed"
                else (
                    default_spacing["y"]["independent"]
                    if self.main_axis_configs.xaxis.mode == "independent"
                    else default_spacing["y"]["shared"]
                )
            )
        )

        max_yaxis = max(
            len(plot_config.yaxes_configs) if plot_config is not None else 0
            for row_plot_configs in self.plots
            for plot_config in row_plot_configs
        )

        x_domains = get_domains(
            spacing=x_spacing * max_yaxis,
            num_axes=len(self.plots[0]),
            fraction=get_domain_fraction(
                axis_idx=1,
                max_yaxis=max_yaxis,
            )
            if max_yaxis > DEFAULT_YAXIS_NUM + 1
            else 1,
        )
        y_domains = get_domains(
            spacing=y_spacing + (0.025 if self.titles.plots is not None else 0),
            num_axes=len(self.plots),
        )

        return x_domains, y_domains

    def infer_x_datetime(
        self,
    ) -> bool:
        for row_configs in self.plots:
            for plot_config in row_configs:
                if plot_config is None:
                    continue
                for traces_config in plot_config.yaxes_configs:
                    for trace in traces_config.traces:
                        x = getattr(trace, "x", None)
                        if x is not None and len(x) > 0:
                            is_datetime = isinstance(x[0], (datetime.date, datetime.datetime))

                            if is_datetime:
                                return True

                            try:
                                DateTime.parse(x[0])
                                is_datetime = True
                            except ValueError:
                                pass

                            if is_datetime:
                                return True

        return False


def pop_axis_config_title(
    config: Mapping[str, Any],
    /,
) -> str | None:
    """
    Extract and remove the title string from an axis config mapping.

    Looks for ``title_text``, then a string ``title``, then ``title.text``,
    popping the first match found.

    Parameters
    ----------
    config
        Axis configuration mapping.

    Returns
    -------
    str or None
        The extracted title, or ``None`` if no title key is present.

    See Also
    --------
    MainAxisConfig : Stores axis configs that may contain titles.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.charts import pop_axis_config_title
    >>> pop_axis_config_title({"title_text": "Price"})
    'Price'
    """
    config = dict(config)

    title: str | None = config.pop("title_text", None)

    if title is not None:
        return title

    title = config.get("title", {})

    if isinstance(title, str):
        return config.pop("title")

    return config.get("title", {}).pop("text", None)


def get_domain_fraction(
    *,
    axis_idx: int,
    max_yaxis: int,
) -> float:
    """
    Compute the domain fraction for a y-axis when multiple axes are stacked.

    When there are more than two y-axes the domain shrinks by 10 % for each
    additional axis to make room for extra tick labels.

    Parameters
    ----------
    axis_idx
        Zero-based index of the current y-axis.
    max_yaxis
        Total number of y-axes in the subplot cell.

    Returns
    -------
    float
        A value in (0, 1] representing the usable fraction of the plot width.

    See Also
    --------
    get_domains : Divides a dimension into evenly spaced domain intervals.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.charts import get_domain_fraction
    >>> get_domain_fraction(axis_idx=0, max_yaxis=2)
    1
    """
    if max_yaxis <= 2:  # noqa: PLR2004
        return 1

    return 1 - (max_yaxis - axis_idx - 1) * 0.1


def get_domains(
    *,
    spacing: float,
    num_axes: int,
    fraction: float = 1,
) -> list[list[float]]:
    """
    Divide the normalised [0, 1] range into evenly spaced axis domains.

    Calculates start and end boundaries for each axis domain, leaving uniform
    gaps of ``spacing`` between neighbouring intervals.

    Parameters
    ----------
    spacing
        Gap between adjacent domains, as a fraction of the total range.
    num_axes
        Number of axes to allocate domains for.
    fraction
        Multiplicative scaling factor applied to all domain boundaries.

    Returns
    -------
    list[list[float]]
        A list of ``[start, end]`` pairs, one per axis.

    See Also
    --------
    get_domain_fraction : Computes the fraction to pass here for multi-y-axis cells.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.charts import get_domains
    >>> get_domains(spacing=0.0, num_axes=1)
    [[0, 1]]
    """
    gap = (1 - spacing * (num_axes - 1)) / num_axes
    return [
        [
            max((gap + spacing) * idx * fraction, 0),
            min((gap + spacing) * idx * fraction + gap * fraction, 1),
        ]
        for idx in range(num_axes)
    ]


def sort_traces_by_axes(
    traces: Sequence[Trace],
    /,
) -> dict[tuple[str, str], list[Trace]]:
    """
    Group traces by their ``(xaxis, yaxis)`` assignment.

    Iterates over the provided traces and buckets them into a dictionary
    keyed by their axis pair so downstream code can process each subplot cell.

    Parameters
    ----------
    traces
        Sequence of plotly traces to categorise.

    Returns
    -------
    dict[tuple[str, str], list[Trace]]
        Mapping from ``(xaxis, yaxis)`` identifier pairs to lists of traces.

    See Also
    --------
    PlotConfig : Holds per-cell trace and axis information.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.charts import sort_traces_by_axes
    >>> sort_traces_by_axes(())
    {}
    """
    traces_axes: dict[tuple[str, str], list[Trace]] = {}
    for trace in traces:
        xaxis = cast("str", trace.xaxis)  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]  # ty:ignore[unresolved-attribute]
        yaxis = cast("str", trace.yaxis)  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]  # ty:ignore[unresolved-attribute]
        if (xaxis, yaxis) in traces_axes:
            traces_axes[(xaxis, yaxis)].append(trace)
        else:
            traces_axes[(xaxis, yaxis)] = [trace]

    return traces_axes


from mayutils.visualisation.graphs.plotly.charts.plot import Plot  # noqa: E402
from mayutils.visualisation.graphs.plotly.charts.subplot import SubPlot  # noqa: E402

__all__ = [
    "AxisConfig",
    "MainAxisConfig",
    "MainAxisConfigs",
    "Plot",
    "PlotConfig",
    "SubPlot",
    "SubPlotConfig",
    "Titles",
    "TracesConfig",
    "get_domain_fraction",
    "get_domains",
    "pop_axis_config_title",
    "sort_traces_by_axes",
]
