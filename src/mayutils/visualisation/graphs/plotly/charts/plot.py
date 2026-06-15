"""
Plotly figure wrapper with fluent chaining and layout composition.

Provides the :class:`Plot` class, a thin wrapper around
:class:`plotly.graph_objects.Figure` that adds fluent chaining, multi-y-axis
layout composition, and convenience methods for common chart enhancements.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable, Iterator, Mapping, Sequence, Sized
from typing import TYPE_CHECKING, Any, Literal, Self, cast, final

from mayutils.core.extras import may_require_extras
from mayutils.environment.logging import Logger
from mayutils.export.images import IMAGES_FOLDER
from mayutils.objects.colours import TRANSPARENT, Colour
from mayutils.objects.functions import set_inline
from mayutils.objects.paths import resolve_save_path
from mayutils.visualisation.graphs.plotly.charts import (
    DEFAULT_YAXIS_NUM,
    AxisConfig,
    PlotConfig,
    Trace,
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

with may_require_extras():
    import numpy as np
    import plotly.graph_objects as go
    from plotly.graph_objects import Layout

if TYPE_CHECKING:
    from pathlib import Path

    from numpy.typing import NDArray
    from pandas import Series

    from mayutils.objects.datetime import Date, DateTime, Interval

logger = Logger.spawn()

TRACE_IDENTIFIERS = {
    TraceType.BAR3D: Bar3d,
    TraceType.LINE: Line,
    TraceType.ECDF: Ecdf,
    TraceType.NULL: Null,
    TraceType.SCATTER: Scatter,
    "histogram": go.Histogram,
}


class Plot(go.Figure):
    """
    Plotly figure with fluent chaining and multi-y-axis support.

    Wraps :class:`plotly.graph_objects.Figure` to add a fluent builder API,
    automatic multi-y-axis domain management, and convenience methods for
    common chart enhancements such as rug plots, KDEs, and density overlays.

    Parameters
    ----------
    config
        Axis and trace configuration for the plot.
    description
        Human-readable description used as the default file-save name.
    layout
        Initial Plotly layout or mapping of layout properties.
    modification_kwargs
        Extra keyword arguments forwarded to :meth:`modifications`.
    **kwargs
        Forwarded to :class:`plotly.graph_objects.Figure`.

    See Also
    --------
    SubPlot : Multi-cell grid built from several ``Plot`` instances.
    PlotConfig : Dataclass that bundles axis configs with traces.

    Examples
    --------
    >>> plot = Plot(PlotConfig.empty(), description="empty")
    """

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
        """
        Initialise the plot from a configuration object.

        Builds the Plotly figure, applies axis configs for each y-axis group,
        adds all traces, and runs post-creation modifications.

        Parameters
        ----------
        config
            Axis and trace configuration for the plot.
        description
            Human-readable description used as the default file-save name.
        layout
            Initial Plotly layout or mapping of layout properties.
        modification_kwargs
            Extra keyword arguments forwarded to :meth:`modifications`.
        **kwargs
            Forwarded to :class:`plotly.graph_objects.Figure`.

        See Also
        --------
        Plot.from_traces : Shortcut that builds a ``PlotConfig`` internally.

        Examples
        --------
        >>> plot = Plot(PlotConfig.empty(), description="demo")
        """
        if layout is None:
            layout = Layout()
        elif not isinstance(layout, Layout):
            layout = Layout(dict(layout))

        if modification_kwargs is None:
            modification_kwargs = {}

        self._config = config
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
        """
        Human-readable description of the plot.

        Returns the description string provided at construction, which is also
        used as the default filename when saving.

        Returns
        -------
        str
            The description string.

        See Also
        --------
        Plot.save : Uses the description as the default save name.

        Examples
        --------
        >>> plot = Plot.empty(description="demo")
        >>> plot.description
        'demo'
        """
        return self._description

    @property
    def num_traces(
        self,
    ) -> int:
        """
        Number of traces currently in the figure.

        Returns the count of all trace objects attached to the figure,
        including hidden or auxiliary traces.

        Returns
        -------
        int
            The trace count.

        See Also
        --------
        Plot.trace : Retrieve a single trace by index.

        Examples
        --------
        >>> plot = Plot.empty(description="demo")
        >>> plot.num_traces
        0
        """
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
        """
        Build a plot from one or more traces sharing a single y-axis.

        Convenience constructor that internally builds a :class:`PlotConfig`
        from the supplied traces and axis overrides.

        Parameters
        ----------
        *traces
            Plotly trace objects to display.
        description
            Human-readable description used as the default file-save name.
        xaxis_config
            Optional x-axis layout overrides.
        yaxis_config
            Optional y-axis layout overrides.
        layout
            Initial Plotly layout or mapping of layout properties.
        **kwargs
            Forwarded to :class:`Plot`.

        Returns
        -------
        Self
            A new ``Plot`` instance.

        See Also
        --------
        Plot.from_figure : Build from an existing ``go.Figure``.
        PlotConfig.from_traces : Lower-level config builder.

        Examples
        --------
        >>> trace = go.Scatter(x=[1, 2, 3], y=[4, 5, 6])
        >>> plot = Plot.from_traces(trace, description="demo")
        """
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
        """
        Wrap an existing Plotly figure in a ``Plot``.

        Creates a new ``Plot`` whose data and layout come from the supplied
        :class:`plotly.graph_objects.Figure`.

        Parameters
        ----------
        fig
            The Plotly figure to wrap.
        description
            Human-readable description used as the default file-save name.

        Returns
        -------
        Self
            A new ``Plot`` instance.

        See Also
        --------
        Plot.from_existing : Wrap an existing ``Plot`` instance.

        Examples
        --------
        >>> plot = Plot.from_figure(go.Figure(), description="wrapped")
        """
        return cls(
            PlotConfig.empty(),
            description=description,
            data=fig,
        )

    @classmethod
    def from_existing(
        cls,
        plot: Plot,
        /,
        *,
        description: str,
    ) -> Self:
        """
        Copy an existing ``Plot`` into a new instance.

        Delegates to :meth:`from_figure`, transferring data and layout while
        allowing a new description.

        Parameters
        ----------
        plot
            The source ``Plot`` to copy.
        description
            Human-readable description for the new instance.

        Returns
        -------
        Self
            A new ``Plot`` instance.

        See Also
        --------
        Plot.copy : Instance-level copy that preserves the description.

        Examples
        --------
        >>> existing_plot = Plot.empty(description="original")
        >>> plot = Plot.from_existing(existing_plot, description="copy")
        >>> plot.description
        'copy'
        """
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
        """
        Create an empty plot with no traces.

        Useful as a starting point when traces will be added incrementally
        via :meth:`add_trace` or the fluent builder methods.

        Parameters
        ----------
        description
            Human-readable description used as the default file-save name.

        Returns
        -------
        Self
            An empty ``Plot`` instance.

        See Also
        --------
        Plot.from_traces : Build a plot with traces in one call.

        Examples
        --------
        >>> plot = Plot.empty(description="blank")
        """
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
        """
        Combine multiple plots into a single figure with a dropdown selector.

        Each supplied plot becomes a selectable frame. The dropdown menu
        switches between frames so the viewer can toggle between different
        data views within one figure.

        Parameters
        ----------
        description
            Human-readable description used as the default file-save name.
        **plots
            Named plots whose keys become dropdown labels.

        Returns
        -------
        Self
            A new ``Plot`` with dropdown-based frame selection.

        See Also
        --------
        Plot.add_button : Add a custom toggle button to the figure.

        Examples
        --------
        >>> plot_a = Plot.from_traces(go.Scatter(x=[1, 2], y=[3, 4]), description="A")
        >>> plot_b = Plot.from_traces(go.Scatter(x=[1, 2], y=[5, 6]), description="B")
        >>> plot = Plot.as_dropdown("comparison", a=plot_a, b=plot_b)
        """
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
        """
        Convert to a plain Plotly figure.

        Returns a new :class:`plotly.graph_objects.Figure` that carries the
        same data and layout but drops the ``Plot``-specific API.

        Returns
        -------
        go.Figure
            A standard Plotly figure.

        See Also
        --------
        Plot.from_figure : The inverse operation.

        Examples
        --------
        >>> plot = Plot.empty(description="demo")
        >>> fig = plot.to_figure()
        """
        return go.Figure(data=self)

    def empty_traces(
        self,
    ) -> Self:
        """
        Remove all traces from the figure.

        Clears the data list in place, leaving the layout and description
        intact for subsequent re-population.

        Returns
        -------
        Self
            The instance for fluent chaining.

        See Also
        --------
        Plot.empty : Class-level constructor for a traceless plot.

        Examples
        --------
        >>> plot = Plot.from_traces(go.Scatter(x=[1, 2], y=[3, 4]), description="demo")
        >>> plot = plot.empty_traces()
        >>> plot.num_traces
        0
        """
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
        """
        Add an axis-edge title annotation to the figure.

        Places a title annotation at the specified edge of the given domain
        rectangle, useful for labelling secondary y-axes or subplot regions.

        Parameters
        ----------
        title
            The text to display.
        edge
            Which edge of the domain to attach the title to.
        offset
            Pixel offset from the edge.
        x_domain
            Horizontal domain fraction range as ``(start, end)``.
        y_domain
            Vertical domain fraction range as ``(start, end)``.
        **kwargs
            Forwarded to :meth:`plotly.graph_objects.Figure.add_annotation`.

        Returns
        -------
        Self
            The instance for fluent chaining.

        See Also
        --------
        Plot.shift_title : Shift the main title vertically.

        Examples
        --------
        >>> plot = Plot.empty(description="demo")
        >>> plot = plot.add_title("Secondary Y")
        """
        with may_require_extras():
            from plotly._subplots import (  # ty:ignore[unresolved-import]
                _build_subplot_title_annotations,  # pyright: ignore[reportPrivateUsage]
            )

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
        """
        Apply an arbitrary callable to the plot for fluent chaining.

        Calls *func* with the plot instance and returns ``self``, allowing
        ad-hoc transformations to be embedded in a method chain.

        Parameters
        ----------
        func
            A callable that receives and mutates the plot instance.

        Returns
        -------
        Self
            The instance for fluent chaining.

        See Also
        --------
        Plot.adjust_layout : Targeted layout property callback.

        Examples
        --------
        >>> plot = Plot.empty(description="demo")
        >>> plot = plot.pipe(lambda p: p.update_layout(title="Hi"))
        """
        func(self)

        return self

    def get_layout_value(
        self,
        props: Sequence[str],
        /,
        *,
        fallback: bool = False,
    ) -> Any:  # noqa: ANN401
        """
        Read a nested layout property by path.

        Traverses the layout using *props* as successive attribute names.
        When *fallback* is ``True`` and the value is ``None``, retries
        against the active template layout.

        Parameters
        ----------
        props
            Attribute path, e.g. ``["margin", "t"]``.
        fallback
            When ``True``, fall back to the template layout if the
            value is ``None``.

        Returns
        -------
            The resolved layout value, or ``None``.

        See Also
        --------
        Plot.adjust_layout : Modify a nested layout property in-place.

        Examples
        --------
        >>> plot = Plot.empty(description="demo").update_layout({"margin_t": 20})
        >>> plot.get_layout_value(["margin", "t"])
        20
        """
        current_value = get_layout_value(self.layout, props=props)

        if current_value is None and fallback:
            template_layout = get_template_layout(get_template())
            current_value = get_layout_value(template_layout, props=props)

        return current_value

    def adjust_layout(
        self,
        props: Sequence[str],
        /,
        *,
        callback: Callable[[Any | None], Any],
        fallback: bool = False,
    ) -> Self:
        """
        Adjust a nested layout property via a callback function.

        Reads the current value at the nested property path, optionally
        falling back to the template layout, then writes back the value
        returned by *callback*.

        Parameters
        ----------
        props
            Sequence of nested property names (e.g. ``["title", "pad", "b"]``).
        callback
            Function that receives the current value and returns the new value.
        fallback
            If ``True`` and the property is not set on the figure, read from
            the active template layout instead.

        Returns
        -------
        Self
            The instance for fluent chaining.

        Raises
        ------
        TypeError
            If the resolved value is a :class:`Layout` instance.

        See Also
        --------
        Plot.shift_title : Common use case that adjusts title padding.

        Examples
        --------
        >>> plot = Plot.empty(description="demo").update_layout({"margin_t": 20})
        >>> plot = plot.adjust_layout(["margin", "t"], callback=lambda v: (v or 0) + 20)
        >>> plot.layout.margin.t
        40
        """
        current_value = self.get_layout_value(
            props,
            fallback=fallback,
        )

        if isinstance(current_value, Layout):
            msg = "Do not adjust Layout instance directly"
            raise TypeError(msg)

        self.update_layout(
            {
                "_".join(props): callback(current_value),
            }
        )

        return self

    def shift_title(
        self,
        offset: int,
    ) -> Self:
        """
        Shift the main title downward by increasing top padding.

        Adjusts both the title bottom padding and the top margin by *offset*
        pixels so the title moves without clipping.

        Parameters
        ----------
        offset
            Number of pixels to shift the title downward.

        Returns
        -------
        Self
            The instance for fluent chaining.

        See Also
        --------
        Plot.adjust_layout : General-purpose layout adjustment.

        Examples
        --------
        >>> plot = Plot.empty(description="demo")
        >>> plot = plot.shift_title(20)
        """
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
        """
        Display the figure with sensible default display configuration.

        Wraps the parent ``show`` method, disabling tips and the Plotly logo
        by default and optionally overriding width, height, or layout.

        Parameters
        ----------
        renderer
            Plotly renderer name (e.g. ``"browser"``).
        validate
            Whether to validate the figure before rendering.
        width
            Override width in pixels.
        height
            Override height in pixels.
        config
            Extra Plotly display config merged on top of defaults.
        layout
            Additional layout overrides applied to a copy of the figure.
        **kwargs
            Forwarded to :meth:`plotly.graph_objects.Figure.show`.

        See Also
        --------
        Plot.save : Persist the figure to disk instead of displaying.

        Examples
        --------
        >>> plot.show(width=800, height=600)  # doctest: +SKIP
        """
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
        """
        Create a shallow copy of the plot.

        Returns a new ``Plot`` with the same data and layout. An optional
        *description* overrides the original.

        Parameters
        ----------
        description
            New description; defaults to the current one if not given.

        Returns
        -------
        Self
            A new ``Plot`` instance.

        See Also
        --------
        Plot.from_existing : Class-level equivalent.

        Examples
        --------
        >>> plot = Plot.empty(description="original")
        >>> new_plot = plot.copy(description="variant")
        >>> new_plot.description
        'variant'
        """
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
        """
        Save the figure to disk as one or more image files.

        Resolves the output path, applies a white save template, and writes
        the image in each requested format via Plotly's ``write_image``.

        Parameters
        ----------
        path
            Destination path; ``None`` uses the default images folder and
            the plot description as the filename.
        formats
            Image format suffixes (e.g. ``["png", "svg"]``). Inferred from
            *path* when empty.
        scale
            Resolution multiplier for raster formats.
        template
            Plotly template string applied before writing.
        overwrite
            Whether to overwrite an existing file at the same path.
        **kwargs
            Forwarded to :meth:`plotly.graph_objects.Figure.write_image`.

        Returns
        -------
        Path
            The resolved output path.

        See Also
        --------
        Plot.show : Display the figure interactively instead of saving.

        Examples
        --------
        >>> plot.save("chart.png")  # doctest: +SKIP
        """
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
        """
        Iterate over the traces in the figure.

        Yields each :class:`~plotly.basedatatypes.BaseTraceType` in insertion
        order, enabling ``for trace in plot`` patterns.

        Returns
        -------
        Iterator[Trace]
            An iterator over the figure's traces.

        See Also
        --------
        Plot.trace : Access a single trace by index.

        Examples
        --------
        >>> plot = Plot.from_traces(go.Scatter(x=[1, 2], y=[3, 4]), description="demo")
        >>> list(plot)
        [Scatter({
            'x': [1, 2], 'y': [3, 4], 'yaxis': 'y'
        })]
        """
        return iter(self.data)

    def set_bound_group_colours(
        self,
        *,
        fill_opacity: float = 0.1,
    ) -> Self:
        """
        Synchronise fill colours of bound-group traces with their parent line.

        Finds legend groups prefixed with ``_bounds_`` and sets the fill
        colour of each bound trace to match the line colour of its parent
        trace at the specified opacity.

        Parameters
        ----------
        fill_opacity
            Opacity applied to the fill when no existing fill opacity is found.

        Returns
        -------
        Self
            The instance for fluent chaining.

        See Also
        --------
        Plot.set_trace_colours : Colour synchronisation for non-bound traces.

        Examples
        --------
        >>> import plotly.graph_objects as go
        >>> from mayutils.visualisation.graphs.plotly.charts.plot import Plot
        >>> plot = Plot.empty(description="demo")
        >>> plot = plot.add_trace(go.Scatter(x=[1, 2], y=[3, 4], legendgroup="_bounds_A"))
        >>> plot = plot.add_trace(go.Scatter(x=[1, 2, 1], y=[3, 5, 3], legendgroup="_bounds_A", fill="toself"))
        >>> plot.trace(1).fillcolor is None
        True
        >>> plot = plot.set_bound_group_colours(fill_opacity=0.2)
        >>> plot.trace(1).fillcolor
        'rgba(171, 99, 250, 0.2)'
        """
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
        """
        Apply consistent marker, line, and fill colours across traces.

        Ensures histograms, KDEs, lines, and ECDFs have their marker outline,
        text font, and fill colours synchronised with the colour-scale.

        Parameters
        ----------
        fill_opacity
            Default opacity for ECDF and KDE fill areas.

        Returns
        -------
        Self
            The instance for fluent chaining.

        See Also
        --------
        Plot.set_bound_group_colours : Colour sync for bound-group traces.

        Examples
        --------
        >>> from mayutils.visualisation.graphs.plotly.charts.plot import Plot
        >>> from mayutils.visualisation.graphs.plotly.traces import Line
        >>> plot = Plot.from_traces(Line(x=[1, 2], y=[3, 4], line={"color": "red"}), description="demo")
        >>> plot = plot.set_trace_colours()
        >>> plot.trace(0).textfont.color
        'red'
        """
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
        """
        Run all post-creation colour modifications.

        Convenience method that calls :meth:`set_trace_colours` and
        :meth:`set_bound_group_colours` in sequence.

        Parameters
        ----------
        fill_opacity
            Opacity forwarded to both colour-setting methods.

        Returns
        -------
        Self
            The instance for fluent chaining.

        See Also
        --------
        Plot.set_trace_colours : Per-trace colour synchronisation.
        Plot.set_bound_group_colours : Bound-group colour synchronisation.

        Examples
        --------
        >>> from mayutils.visualisation.graphs.plotly.charts.plot import Plot
        >>> from mayutils.visualisation.graphs.plotly.traces import Line
        >>> plot = Plot.from_traces(Line(x=[1, 2], y=[3, 4], line={"color": "blue"}), description="demo")
        >>> plot = plot.modifications()
        >>> plot.trace(0).textfont.color
        'blue'
        """
        self.set_trace_colours(fill_opacity=fill_opacity)
        self.set_bound_group_colours(fill_opacity=fill_opacity)

        return self

    def add_histogram_gaussians(
        self,
    ) -> Self:
        """
        Overlay fitted Gaussian curves on every histogram trace.

        For each histogram in the figure, fits a normal distribution to its
        data and adds a dashed line trace showing the probability density.

        Returns
        -------
        Self
            The instance for fluent chaining.

        See Also
        --------
        Plot.add_kde_to_histogram : Overlay KDE curves instead of Gaussians.

        Examples
        --------
        >>> plot = Plot.from_traces(go.Histogram(x=np.random.normal(size=1000)), description="demo")
        >>> plot = plot.add_histogram_gaussians()
        """
        with may_require_extras():
            from scipy.stats import norm

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
    def add_rug(  # noqa: C901, PLR0912
        self,
        *,
        rug_type: Literal["scatter", "violin", "box", "strip", "histogram", "ecdf"] = "scatter",
        rug_height: float | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        """
        Add a rug plot beneath histograms and KDE traces.

        Creates a secondary y-axis region below the main plot and populates
        it with per-trace rug representations. The method is idempotent and
        will not add rugs a second time.

        Parameters
        ----------
        rug_type
            Visual representation for each rug (e.g. ``"scatter"``,
            ``"violin"``, ``"box"``).
        rug_height
            Fraction of the figure height reserved for the rug region.
            Defaults to 0.15 for scatter and 0.3 for other types.
        **kwargs
            Forwarded to the underlying rug trace constructor.

        Returns
        -------
        Self
            The instance for fluent chaining.

        Raises
        ------
        NotImplementedError
            If *rug_type* is ``"histogram"``.
        ValueError
            If *rug_type* is not recognised.

        See Also
        --------
        Plot.add_kde_to_histogram : Another histogram enhancement.

        Examples
        --------
        >>> plot = Plot.from_traces(go.Histogram(x=np.random.normal(size=1000)), description="demo")
        >>> plot = plot.add_rug(rug_type="violin")
        """
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
        """
        Retrieve a single trace by its integer index.

        Provides direct index-based access to the underlying data tuple,
        which is more explicit than subscripting the figure directly.

        Parameters
        ----------
        idx
            Zero-based index of the desired trace.

        Returns
        -------
        Trace
            The trace at the given index.

        See Also
        --------
        Plot.get_traces_by_type : Filter traces by their type identifier.

        Examples
        --------
        >>> plot = Plot.from_traces(go.Scatter(x=[1, 2], y=[3, 4]), description="demo")
        >>> plot.trace(0)
        Scatter({
            'x': [1, 2], 'y': [3, 4], 'yaxis': 'y'
        })
        """
        return self.data[idx]

    def get_traces_by_type(
        self,
        trace_type: str,
        /,
    ) -> Iterator[tuple[int, Trace]]:
        """
        Yield ``(index, trace)`` pairs matching a trace type identifier.

        Looks up the trace class in :data:`TRACE_IDENTIFIERS` and matches
        by ``isinstance`` or by comparing the ``meta`` attribute.

        Parameters
        ----------
        trace_type
            String key or :class:`TraceType` value identifying the trace kind.

        Returns
        -------
        Iterator[tuple[int, Trace]]
            Pairs of ``(index, trace)`` for every matching trace.

        See Also
        --------
        Plot.trace : Access a single trace by index.

        Examples
        --------
        >>> plot = Plot.from_traces(
        ...     go.Histogram(x=np.random.normal(size=1000)),
        ...     go.Scatter(x=np.random.randn(100), y=np.random.randn(100), mode="markers"),
        ...     description="demo",
        ... )
        >>> histogram_traces = list(plot.get_traces_by_type("histogram"))
        >>> len(histogram_traces)
        1
        """
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
        """
        Append a toggle button to an update-menu in the figure layout.

        Inserts the button mapping into the specified update-menu, creating
        the menu if it does not yet exist.

        Parameters
        ----------
        button
            A Plotly update-menu button specification.
        menu_index
            Index of the update-menu to append to.

        Returns
        -------
        Self
            The instance for fluent chaining.

        See Also
        --------
        Plot.add_histogram_to_2d_scatter : Uses this to add a density toggle.

        Examples
        --------
        >>> plot = Plot.empty(description="demo")
        >>> plot = plot.add_button({"label": "Toggle", "method": "restyle", "args": [{"visible": True}]})
        """
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
        """
        Add a toggleable 2-D density histogram over existing scatter traces.

        Groups scatter traces by their axis assignment, computes a
        :class:`~plotly.graph_objects.Histogram2d` for each group, and adds a
        toggle button to show or hide the density layer.

        Parameters
        ----------
        colour
            Base colour for the density colour-scale; defaults to red.
        index_used
            Numeric index used for the colour-axis and bin-group identifiers
            to avoid collisions with existing axes.
        **kwargs
            Forwarded to :class:`plotly.graph_objects.Histogram2d`.

        Returns
        -------
        Self
            The instance for fluent chaining.

        See Also
        --------
        Plot.add_default_extras : Calls this method automatically.

        Examples
        --------
        >>> plot = Plot.from_traces(
        ...     go.Scatter(x=np.random.randn(100), y=np.random.randn(100), mode="markers"),
        ...     description="demo",
        ... )
        >>> plot = plot.add_histogram_to_2d_scatter(colour=Colour.parse("blue"))
        """
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
        """
        Overlay kernel density estimate curves on every histogram trace.

        Adds a :class:`~mayutils.visualisation.graphs.plotly.traces.Kde` trace
        for each histogram, inheriting the histogram's colour and axis.

        Parameters
        ----------
        **kwargs
            Overrides merged on top of the default KDE styling (opacity,
            line width, fill, etc.) and forwarded to :class:`Kde`.

        Returns
        -------
        Self
            The instance for fluent chaining.

        See Also
        --------
        Plot.add_histogram_gaussians : Parametric Gaussian overlay instead.
        Plot.add_default_extras : Calls this method automatically.

        Examples
        --------
        >>> plot = Plot.from_traces(go.Histogram(x=np.random.randn(1000)), description="demo")
        >>> plot = plot.add_kde_to_histogram(opacity=0.7)
        """
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
        """
        Add toggle buttons to switch 3-D bar traces to a 2-D heatmap view.

        If the figure contains any :class:`Bar3d` traces, two update-menu
        buttons are added: one restores the 3-D bar representation and the
        other re-styles all traces as a heatmap.

        Returns
        -------
        Self
            The instance for fluent chaining.

        See Also
        --------
        Plot.add_default_extras : Calls this method automatically.
        Plot.add_button : Low-level button insertion.

        Examples
        --------
        >>> plot = Plot.from_traces(
        ...     Bar3d(x=[0, 1, 2], y=[0, 1, 2], z=[5, 10, 15]),
        ...     description="demo",
        ... )
        >>> plot = plot.add_heatmap_alternative_to_3d_bar()
        """
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
        """
        Apply all standard chart enhancements in one call.

        Sequentially adds a 2-D density overlay for scatter plots, KDE
        curves for histograms, and a heatmap toggle for 3-D bars.

        Returns
        -------
        Self
            The instance for fluent chaining.

        See Also
        --------
        Plot.add_histogram_to_2d_scatter : Density overlay.
        Plot.add_kde_to_histogram : KDE curves.
        Plot.add_heatmap_alternative_to_3d_bar : Heatmap toggle.

        Examples
        --------
        >>> plot = Plot.from_traces(
        ...     go.Scatter(x=np.random.randn(100), y=np.random.randn(100), mode="markers"),
        ...     go.Histogram(x=np.random.randn(1000)),
        ...     description="demo",
        ... )
        >>> plot = plot.add_default_extras()
        """
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
        """
        Highlight a date interval with a translucent vertical rectangle.

        Draws a :meth:`~plotly.graph_objects.Figure.add_vrect` spanning the
        interval's start and end dates. Does nothing when *interval* is
        ``None``.

        Parameters
        ----------
        interval
            The date or datetime interval to highlight, or ``None`` to skip.
        **kwargs
            Overrides merged on top of the default styling and forwarded to
            :meth:`~plotly.graph_objects.Figure.add_vrect`.

        Returns
        -------
        Self
            The instance for fluent chaining.

        See Also
        --------
        Plot.adjust_layout : General-purpose layout tweaks.

        Examples
        --------
        >>> from mayutils.objects.datetime import Interval
        >>> plot = Plot.from_traces(go.Scatter(x=[datetime.date(2020, 1, 1), datetime.date(2020, 1, 2)], y=[1, 2]), description="demo")
        >>> interval = Interval(start=datetime.date(2020, 1, 1), end=datetime.date(2020, 1, 2))
        >>> plot = plot.add_interval(interval)
        """
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
        """
        Hide named traces by setting them to legend-only visibility.

        Iterates over the provided trace names and marks each matching trace
        as ``"legendonly"`` so it is hidden from the plot but still toggleable.

        Parameters
        ----------
        names
            Trace names to hide.

        Returns
        -------
        Self
            The instance for fluent chaining.

        See Also
        --------
        Plot.get_traces_by_type : Retrieve traces for programmatic filtering.

        Examples
        --------
        >>> plot = Plot.from_traces(
        ...     go.Scatter(x=[1, 2], y=[3, 4], name="Trace A"),
        ...     go.Scatter(x=[1, 2], y=[5, 6], name="Trace B"),
        ...     description="demo",
        ... )
        >>> plot = plot.hide_traces(["Trace A", "Trace B"])
        >>> plot.trace(0).visible
        'legendonly'
        >>> plot.trace(1).visible
        'legendonly'
        """
        for name in names:
            self.update_traces(
                visible="legendonly",
                selector={"name": name},
            )

        return self

    def set_visible_y_range(  # noqa: C901
        self,
        *,
        y_padding: float = 0.05,
    ) -> Self:
        """
        Restrict each y-axis range to values visible within the current x-axis range.

        Scans all traces, filters each trace's y-data to the current x-axis
        window, and updates every y-axis range (with padding) to fit only the
        visible data.

        Parameters
        ----------
        y_padding
            Fractional padding added above and below the visible y-range.

        Returns
        -------
        Self
            The instance for fluent chaining.

        Raises
        ------
        ValueError
            If the x-axis range has not been set on the layout.

        See Also
        --------
        Plot.adjust_layout : General-purpose layout adjustment.

        Examples
        --------
        >>> plot = Plot.from_traces(
        ...     go.Scatter(
        ...         x=[datetime.date(2020, 1, 1), datetime.date(2020, 1, 2), datetime.date(2020, 1, 3), datetime.date(2020, 1, 4)],
        ...         y=[10, 20, 30, 40],
        ...     ),
        ...     go.Scatter(
        ...         x=[datetime.date(2020, 1, 1), datetime.date(2020, 1, 2), datetime.date(2020, 1, 3), datetime.date(2020, 1, 4)],
        ...         y=[15, 25, 35, 45],
        ...         yaxis="y2",
        ...     ),
        ...     layout={"xaxis_range": [datetime.date(2020, 1, 2), datetime.date(2020, 1, 3)]},
        ...     description="demo",
        ... )
        >>> plot = plot.set_visible_y_range(y_padding=0.1)
        """
        with may_require_extras():
            from pandas import Series
            from pandas import to_datetime as to_pandas_datetime

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
        """
        Save and/or display the plot in a single call.

        Convenience shortcut that optionally saves the figure to disk and
        displays it interactively, returning ``self`` for further chaining.

        Parameters
        ----------
        save
            If ``True``, save the figure to the default path.
        show
            If ``True``, display the figure interactively.

        Returns
        -------
        Self
            The instance for fluent chaining.

        See Also
        --------
        Plot.save : Save without displaying.
        Plot.show : Display without saving.

        Examples
        --------
        >>> plot(save=True, show=False)  # doctest: +SKIP
        """
        if save:
            self.save(None)

        if show:
            self.show()

        return self
