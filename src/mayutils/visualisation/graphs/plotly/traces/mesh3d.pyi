# pyright: reportPropertyTypeMismatch=false
from typing import Any

import plotly.graph_objects as go
from numpy.typing import ArrayLike
from pandas import DataFrame

class Cuboid(go.Mesh3d):
    def __init__(
        self,
        x: tuple[float, float] = ...,
        y: tuple[float, float] = ...,
        z: tuple[float, float] = ...,
        weight: float = 1,
        flatshading: bool = True,
        showscale: bool = False,
        alphahull: float = 1,
        cmin: float = 0,
        cmax: float = 1,
        *,
        colorscale: Any = ...,  # noqa: ANN401
        customdata: Any = ...,  # noqa: ANN401
        hovertemplate: str = ...,
        meta: Any = ...,  # noqa: ANN401
        name: str | int | None = ...,
        opacity: float | None = ...,
        scene: str | None = ...,
        showlegend: bool | None = ...,
        visible: bool | str | None = ...,
        **kwargs: Any,  # noqa: ANN401
    ) -> None: ...

class Bar3d(go.Mesh3d):
    def __init__(
        self,
        x: ArrayLike = ...,
        y: ArrayLike = ...,
        z: ArrayLike = ...,
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
        *,
        colorscale: Any = ...,  # noqa: ANN401
        cmin: float = ...,
        cmax: float = ...,
        name: str | int | None = ...,
        opacity: float | None = ...,
        scene: str | None = ...,
        showlegend: bool | None = ...,
        visible: bool | str | None = ...,
        **kwargs: Any,  # noqa: ANN401
    ) -> None: ...
    @classmethod
    def from_dataframe(
        cls,
        df: DataFrame,
        /,
        *,
        value_weights: bool = False,
        x_mapping: ArrayLike | None = None,
        y_mapping: ArrayLike | None = None,
        colorscale: Any = ...,  # noqa: ANN401
        cmin: float = ...,
        cmax: float = ...,
        name: str | int | None = ...,
        opacity: float | None = ...,
        scene: str | None = ...,
        showlegend: bool | None = ...,
        visible: bool | str | None = ...,
        **kwargs: Any,  # noqa: ANN401
    ) -> Bar3d: ...
