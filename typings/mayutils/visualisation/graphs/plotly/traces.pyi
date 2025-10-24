import plotly.graph_objects as go
from mayutils.objects.colours import Colour as Colour
from mayutils.objects.datetime import DateTime as DateTime
from mayutils.objects.types import RecursiveDict as RecursiveDict
from mayutils.visualisation.graphs.plotly.utilities import (
    map_categorical_array as map_categorical_array,
    melt_dataframe as melt_dataframe,
)
from numpy.typing import ArrayLike as ArrayLike
from pandas import DataFrame, Series
from plotly.basedatatypes import BaseTraceType as Trace
from typing import Literal, Self

class Null(go.Scatter):
    def __init__(self, x_datetime: bool = False, *args, **kwargs) -> None: ...

class Line(go.Scatter):
    def __init__(
        self,
        label_name: bool | str = False,
        textposition: str = "middle right",
        meta: str = "line",
        *args,
        **kwargs,
    ) -> None: ...
    @classmethod
    def from_series(cls, series: Series, *args, **kwargs) -> Self: ...
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
    ) -> tuple[Self, ...]: ...
    @classmethod
    def from_bounds_dataframe(
        cls, df: DataFrame, *args, **kwargs
    ) -> tuple[Self, ...]: ...

class Ecdf(Line):
    def __init__(
        self,
        x: ArrayLike,
        y: ArrayLike | None = None,
        y_shift: float = 0,
        norm: Literal["probability", "percentage", "count"] = "probability",
        mode: Literal["standard", "reversed", "complementary"] = "standard",
        fill: Literal["tozeroy", "tonexty", "toself"] = "toself",
        left_inclusive: bool = False,
        *args,
        **kwargs,
    ) -> None: ...

class Kde(Line):
    def __init__(
        self, x: ArrayLike, bandwidth: float | None = None, *args, **kwargs
    ) -> None: ...

class Scatter(go.Scatter):
    def __init__(self, *args, **kwargs) -> None: ...

class Icicle(go.Icicle):
    @classmethod
    def from_dict(cls, icicle_dict: RecursiveDict[str, float], **kwargs) -> Self: ...

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
    ) -> None: ...

class Bar3d(go.Mesh3d):
    def __init__(
        self,
        x: ArrayLike,
        y: ArrayLike,
        z: ArrayLike,
        w: ArrayLike | None = None,
        showscale: bool = True,
        alphahull: float = 1,
        flatshading: bool = True,
        dx: float = 1,
        dy: float = 1,
        z0: float = 0,
        x_start: float = 0,
        y_start: float = 0,
        z_start: float = 0,
        x_mapping: ArrayLike | None = None,
        y_mapping: ArrayLike | None = None,
        *args,
        **kwargs,
    ) -> None: ...
    @classmethod
    def from_dataframe(
        cls,
        df: DataFrame,
        value_weights: bool = False,
        x_mapping: ArrayLike | None = None,
        y_mapping: ArrayLike | None = None,
        **kwargs,
    ) -> Self: ...

def merge_cuboids(*cuboids: Cuboid) -> go.Mesh3d: ...
def is_trace_3d(trace: Trace) -> bool: ...
