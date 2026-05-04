from typing import Any

from plotly.basedatatypes import BaseTraceType


class Icicle(BaseTraceType):
    def __init__(
        self,
        arg: dict[str, Any] | None = ...,
        *,
        ids: Any = ...,
        labels: Any = ...,
        parents: Any = ...,
        values: Any = ...,
        branchvalues: str | None = ...,
        customdata: Any = ...,
        hovertemplate: str = ...,
        marker: Any = ...,
        meta: Any = ...,
        name: str | int | None = ...,
        opacity: float | None = ...,
        showlegend: bool | None = ...,
        visible: bool | str | None = ...,
        **kwargs: Any,
    ) -> None: ...
