from typing import Any

from plotly.basedatatypes import BaseTraceType


class Mesh3d(BaseTraceType):
    def __init__(
        self,
        arg: dict[str, Any] | None = ...,
        *,
        x: Any = ...,
        y: Any = ...,
        z: Any = ...,
        i: Any = ...,
        j: Any = ...,
        k: Any = ...,
        intensity: Any = ...,
        alphahull: float = ...,
        flatshading: bool = ...,
        showscale: bool = ...,
        colorscale: Any = ...,
        cmin: float = ...,
        cmax: float = ...,
        customdata: Any = ...,
        hovertemplate: str = ...,
        meta: Any = ...,
        name: str | int | None = ...,
        opacity: float | None = ...,
        scene: str | None = ...,
        showlegend: bool | None = ...,
        visible: bool | str | None = ...,
        **kwargs: Any,
    ) -> None: ...
