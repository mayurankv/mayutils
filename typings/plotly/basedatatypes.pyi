import os
from collections import OrderedDict
from collections.abc import Callable, Generator, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Self, Any

from plotly._subplots import SubplotDomain, SubplotXY
from plotly.callbacks import BoxSelector, InputDeviceState, LassoSelector, Points
from plotly.graph_objs import Figure, Layout
from plotly.graph_objs.layout import Annotation

Undefined = ...

class BaseFigure:
    _bracket_re = ...
    _valid_underscore_properties = ...
    _set_trace_uid = ...
    _allow_disable_validation = ...
    def __init__(
        self,
        data: Sequence[BaseTraceType] | Sequence[dict[str, Any]] | BaseTraceType | BaseFigure | dict[str, Any] = ...,
        layout_plotly: BaseLayoutType | dict[str, Any] = ...,
        frames: Sequence[BaseFrameHierarchyType] | dict[str, Any] = ...,
        skip_invalid: bool = ...,
        **kwargs: Any,
    ) -> None: ...
    def __reduce__(self) -> tuple[type[BaseFigure], tuple[dict[str, Any]]]: ...
    def __setitem__(self, prop: str, value: Any) -> None: ...
    def __setattr__(self, prop: str, value: Any) -> None: ...
    def __getitem__(self, prop: str) -> Any: ...
    def __iter__(self) -> Iterator[str]:  # -> Iterator[Literal['data', 'layout', 'frames']]:
        ...
    def __contains__(self, prop: str) -> bool: ...
    def __eq__(self, other: object) -> bool: ...
    def update(
        self,
        dict1: dict[str, Any] = ...,
        overwrite: bool = ...,
        **kwargs: Any,
    ) -> Self:  # -> Self:
        ...
    def pop(self, key: str, dflt: Any | None = ...) -> Any: ...
    @property
    def data(self) -> Sequence[BaseTraceType]: ...
    @data.setter
    def data(self, new_data: Sequence[BaseTraceType]) -> None: ...
    def select_traces(
        self,
        selector: dict[str, Any] | Callable[[BaseTraceType], bool] | int | str | None = ...,
        row: int | None = ...,
        col: int | None = ...,
        secondary_y: bool | None = ...,
    ) -> Generator[BaseTraceType]: ...
    def for_each_trace(
        self,
        fn: Callable[[BaseTraceType], Any],
        selector: dict[str, Any] | Callable[[BaseTraceType], bool] | int | str | None = ...,
        row: int | None = ...,
        col: int | None = ...,
        secondary_y: bool | None = ...,
    ) -> Self:  # -> Self:
        ...
    def update_traces(
        self,
        patch: dict[str, Any] | None = ...,
        selector: dict[str, Any] | Callable[[BaseTraceType], bool] | int | str | None = ...,
        row: int | None = ...,
        col: int | None = ...,
        secondary_y: bool | None = ...,
        overwrite: bool = ...,
        **kwargs: Any,
    ) -> Self:  # -> Self:
        ...
    def update_layout(
        self,
        dict1: dict[str, Any] = ...,
        overwrite: bool = ...,
        **kwargs: Any,
    ) -> Self:  # -> Self:
        ...
    def plotly_restyle(
        self,
        restyle_data: dict[str, Any | Sequence[Any]],
        trace_indexes: int | Sequence[int] | None = ...,
        **kwargs: Any,
    ) -> None: ...
    def add_trace(
        self,
        trace: BaseTraceType | dict[str, Any],
        row: int | str | None = ...,
        col: int | str | None = ...,
        secondary_y: bool | None = ...,
        exclude_empty_subplots: bool = ...,
    ) -> Self:  # -> Self:
        ...
    def add_traces(
        self,
        data: Sequence[BaseTraceType | dict[str, Any]],
        rows: Sequence[int] | int | None = ...,
        cols: Sequence[int] | int | None = ...,
        secondary_ys: Sequence[bool] | None = ...,
        exclude_empty_subplots: bool = ...,
    ) -> Self:  # -> Self:
        ...
    def print_grid(self) -> None: ...
    def append_trace(
        self,
        trace: BaseTraceType,
        row: int,
        col: int,
    ) -> None: ...
    def get_subplot(
        self,
        row: int,
        col: int,
        secondary_y: bool = ...,
    ) -> (
        BaseLayoutHierarchyType | SubplotDomain | SubplotXY | None
    ):  # -> Scene | Polar | Ternary | Mapbox | SubplotDomain | SubplotXY | None:
        ...
    @property
    def layout(self) -> Layout:  # -> Layout:
        ...
    @layout.setter
    def layout(self, new_layout: Layout) -> None: ...
    def plotly_relayout(
        self,
        relayout_data: dict[str, Any],
        **kwargs: Any,
    ) -> None: ...
    @property
    def frames(self) -> Sequence[BaseFrameHierarchyType]:  # -> tuple[plotly.graph_objs.Frame]
        ...
    @frames.setter
    def frames(self, new_frames: Sequence[BaseFrameHierarchyType]) -> None: ...
    def plotly_update(
        self,
        restyle_data: dict[str, Any] = ...,
        relayout_data: dict[str, Any] = ...,
        trace_indexes: int | Sequence[int] | None = ...,
        **kwargs: Any,
    ) -> None: ...
    @contextmanager
    def batch_update(self) -> Generator[None, Any]: ...
    @contextmanager
    def batch_animate(
        self,
        duration: int | float = ...,
        easing: str = ...,
    ) -> Generator[None, Any]: ...
    def to_dict(self) -> dict[str, Any]: ...
    def to_plotly_json(self) -> dict[str, Any]: ...
    def to_ordered_dict(self, skip_uid: bool = ...) -> OrderedDict[str, Any]: ...
    def show(
        self,
        renderer: str | None = ...,
        validate: bool = ...,
        width: int | float = ...,
        height: int | float = ...,
        config: dict[str, Any] = ...,
    ) -> None: ...
    def to_json(
        self,
        validate: bool = ...,
        pretty: bool = ...,
        remove_uids: bool = ...,
        engine: str | None = ...,
    ) -> str: ...
    def full_figure_for_development(
        self,
        warn: bool = ...,
        as_dict: bool = ...,
    ) -> Figure: ...
    def write_json(
        self,
        file: Path | os.PathLike[str],
        pretty: bool = ...,
        remove_uids: bool = ...,
        engine: str | None = ...,
    ) -> None: ...
    def to_html(
        self,
        config: dict[str, Any] | None = ...,
        auto_play: bool = ...,
        include_plotlyjs: bool | str = ...,
        include_mathjax: bool | str = ...,
        post_script: str | Sequence[str] | None = ...,
        full_html: bool = ...,
        animation_opts: dict[str, Any] | None = ...,
        default_width: int | float | str = ...,
        default_height: int | float | str = ...,
        validate: bool = ...,
        div_id: str | None = ...,
    ) -> str: ...
    def write_html(
        self,
        file: Path | os.PathLike[str],
        config: dict[str, Any] | None = ...,
        auto_play: bool = ...,
        include_plotlyjs: bool | str = ...,
        include_mathjax: bool | str = ...,
        post_script: str | Sequence[str] | None = ...,
        full_html: bool = ...,
        animation_opts: dict[str, Any] | None = ...,
        default_width: int | float | str = ...,
        default_height: int | float | str = ...,
        validate: bool = ...,
        auto_open: bool = ...,
        div_id: str | None = ...,
    ) -> None: ...
    def to_image(
        self,
        format: str | None = ...,
        width: int | None = ...,
        height: int | None = ...,
        scale: int | float | None = ...,
        validate: bool = ...,
        engine: str = ...,
    ) -> bytes: ...
    def write_image(
        self,
        file: Path | os.PathLike[str],
        format: str | None = ...,
        width: int | None = ...,
        height: int | None = ...,
        scale: int | float | None = ...,
        validate: bool = ...,
        engine: str = ...,
    ) -> None: ...
    def add_vline(
        self,
        x: int | float,
        row: int | str | None = ...,
        col: int | str | None = ...,
        exclude_empty_subplots: bool = ...,
        annotation: Annotation | dict[str, Any] = ...,
        **kwargs: Any,
    ) -> Self:  # -> Self:
        ...
    def add_hline(
        self,
        y: int | float,
        row: int | str | None = ...,
        col: int | str | None = ...,
        exclude_empty_subplots: bool = ...,
        annotation: Annotation | dict[str, Any] = ...,
        **kwargs: Any,
    ) -> Self:  # -> Self:
        ...
    def add_vrect(
        self,
        x0: int | float,
        x1: int | float,
        row: int | str | None = ...,
        col: int | str | None = ...,
        exclude_empty_subplots: bool = ...,
        annotation: Annotation | dict[str, Any] = ...,
        **kwargs: Any,
    ) -> Self:  # -> Self:
        ...
    def add_hrect(
        self,
        y0: int | float,
        y1: int | float,
        row: int | str | None = ...,
        col: int | str | None = ...,
        exclude_empty_subplots: bool = ...,
        annotation: Annotation | dict[str, Any] = ...,
        **kwargs: Any,
    ) -> Self:  # -> Self:
        ...
    def set_subplots(
        self,
        rows: int = ...,
        cols: int = ...,
        shared_xaxes: bool | str = ...,
        shared_yaxes: bool | str = ...,
        start_cell: str = ...,
        print_grid: bool = ...,
        horizontal_spacing: float = ...,
        vertical_spacing: float = ...,
        subplot_titles: list[str] | None = ...,
        column_widths: list[float] | None = ...,
        row_heights: list[float] | None = ...,
        specs: list[list[dict[str, str | bool | int | float] | None]] | None = ...,
        insets: list[dict[str, tuple[int, int] | str | float]] | None = ...,
        column_titles: list[str] | None = ...,
        row_titles: list[str] | None = ...,
        x_title: str | None = ...,
        y_title: str | None = ...,
        figure: BaseFigure | None = ...,
        **kwargs: Any,
    ) -> Self: ...

class BasePlotlyType:
    _mapped_properties = ...
    _parent_path_str = ...
    _path_str = ...
    _valid_props = ...
    def __init__(
        self,
        plotly_name: str,
        **kwargs: Any,
    ) -> None: ...
    @property
    def plotly_name(self) -> str | None: ...
    @property
    def parent(self) -> BasePlotlyType | BaseFigure: ...
    @property
    def figure(self) -> BaseFigure | None: ...
    def __reduce__(self) -> tuple[type[BasePlotlyType], tuple[dict[str, Any]]]: ...
    def __getitem__(self, prop: str) -> Any: ...
    def __contains__(self, prop: str) -> bool: ...
    def __setitem__(self, prop: str, value: Any) -> None: ...
    def __setattr__(self, prop: str, value: Any) -> None: ...
    def __iter__(self) -> Iterator[str]: ...
    def __eq__(self, other: object) -> bool: ...
    def update(
        self,
        dict1: dict[str, Any] = ...,
        overwrite: bool = ...,
        **kwargs: Any,
    ) -> Self:  # -> Self:
        ...
    def pop(self, key: str, dflt: Any) -> Any: ...
    def on_change(
        self,
        callback: Callable[..., None],
        args: list[str | tuple[int | str]],
        append: bool = ...,
    ) -> None: ...
    def to_plotly_json(self) -> dict[str, Any]: ...
    def to_json(
        self,
        validate: bool = ...,
        pretty: bool = ...,
        remove_uids: bool = ...,
        engine: str | None = ...,
    ) -> str: ...

class BaseLayoutHierarchyType(BasePlotlyType):
    def __init__(
        self,
        plotly_name: str,
        **kwargs: Any,
    ) -> None: ...

class BaseLayoutType(BaseLayoutHierarchyType):
    def __init__(
        self,
        plotly_name: str,
        **kwargs: Any,
    ) -> None: ...
    def __getattr__(self, prop: str) -> Any: ...
    def __getitem__(self, prop: str) -> Any: ...
    def __contains__(self, prop: str) -> bool: ...
    def __setitem__(self, prop: str, value: Any) -> None: ...
    def __setattr__(self, prop: str, value: Any) -> None: ...
    def __dir__(self) -> list[str]: ...

class BaseTraceHierarchyType(BasePlotlyType):
    def __init__(
        self,
        plotly_name: str,
        **kwargs: Any,
    ) -> None: ...

class BaseTraceType(BaseTraceHierarchyType):
    def __init__(
        self,
        plotly_name: str,
        **kwargs: Any,
    ) -> None: ...
    @property
    def xaxis(self) -> str | None: ...
    @xaxis.setter
    def xaxis(self, val: str | None) -> None: ...
    @property
    def yaxis(self) -> str | None: ...
    @yaxis.setter
    def yaxis(self, val: str | None) -> None: ...
    @property
    def type(self) -> str | None: ...
    @type.setter
    def type(self, val: str | None) -> None: ...
    @property
    def x(self) -> Any: ...
    @x.setter
    def x(self, val: Any) -> None: ...
    @property
    def y(self) -> Any: ...
    @y.setter
    def y(self, val: Any) -> None: ...
    @property
    def z(self) -> Any: ...
    @z.setter
    def z(self, val: Any) -> None: ...
    @property
    def meta(self) -> Any: ...
    @meta.setter
    def meta(self, val: Any) -> None: ...
    @property
    def customdata(self) -> Any: ...
    @customdata.setter
    def customdata(self, val: Any) -> None: ...
    @property
    def textfont(self) -> Any: ...
    @textfont.setter
    def textfont(self, val: Any) -> None: ...
    @property
    def line(self) -> Any: ...
    @line.setter
    def line(self, val: Any) -> None: ...
    @property
    def marker(self) -> Any: ...
    @marker.setter
    def marker(self, val: Any) -> None: ...
    @property
    def fillcolor(self) -> str | None: ...
    @fillcolor.setter
    def fillcolor(self, val: str | None) -> None: ...
    @property
    def opacity(self) -> float | None: ...
    @opacity.setter
    def opacity(self, val: float | None) -> None: ...
    @property
    def legendgroup(self) -> str | int | None: ...
    @legendgroup.setter
    def legendgroup(self, val: str | int | None) -> None: ...
    @property
    def fill(self) -> str | None: ...
    @fill.setter
    def fill(self, val: str | None) -> None: ...
    @property
    def name(self) -> str | int | None: ...
    @name.setter
    def name(self, val: str | int | None) -> None: ...
    @property
    def visible(self) -> bool | str | None: ...
    @visible.setter
    def visible(self, val: bool | str | None) -> None: ...
    @property
    def scene(self) -> str | None: ...
    @scene.setter
    def scene(self, val: str | None) -> None: ...
    @property
    def showlegend(self) -> bool | None: ...
    @showlegend.setter
    def showlegend(self, val: bool | None) -> None: ...
    @property
    def hoverinfo(self) -> str | None: ...
    @hoverinfo.setter
    def hoverinfo(self, val: str | None) -> None: ...
    @property
    def mode(self) -> str | None: ...
    @mode.setter
    def mode(self, val: str | None) -> None: ...
    @property
    def text(self) -> Any: ...
    @text.setter
    def text(self, val: Any) -> None: ...

    @property
    def uid(self) -> str | int | None: ...
    @uid.setter
    def uid(self, val: str | int | None) -> None: ...
    def on_hover(
        self,
        callback: Callable[[BaseTraceType, Points, InputDeviceState], None],
        append: bool = ...,
    ) -> None: ...
    def on_unhover(
        self,
        callback: Callable[[BaseTraceType, Points, InputDeviceState], None],
        append: bool = ...,
    ) -> None: ...
    def on_click(
        self,
        callback: Callable[[BaseTraceType, Points, InputDeviceState], None],
        append: bool = ...,
    ) -> None: ...
    def on_selection(
        self,
        callback: Callable[[BaseTraceType, Points, BoxSelector | LassoSelector], None],
        append: bool = ...,
    ) -> None: ...
    def on_deselect(
        self,
        callback: Callable[[BaseTraceType, Points], None],
        append: bool = ...,
    ) -> None: ...

class BaseFrameHierarchyType(BasePlotlyType):
    def __init__(
        self,
        plotly_name: str,
        **kwargs: Any,
    ) -> None: ...
    def on_change(
        self,
        callback: Callable[..., None],
        args: list[str | tuple[int | str]],
        append: bool = ...,
    ) -> None: ...
