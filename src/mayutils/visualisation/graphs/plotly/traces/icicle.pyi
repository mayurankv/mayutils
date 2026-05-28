# pyright: reportPropertyTypeMismatch=false
from typing import Any

import plotly.graph_objects as go

from mayutils.objects.types import RecursiveMapping

class Icicle(go.Icicle):
    def __init__(
        self,
        ids: Any = ...,  # noqa: ANN401
        labels: Any = ...,  # noqa: ANN401
        parents: Any = ...,  # noqa: ANN401
        values: Any = ...,  # noqa: ANN401
        branchvalues: str | None = ...,
        customdata: Any = ...,  # noqa: ANN401
        hovertemplate: str = ...,
        marker: Any = ...,  # noqa: ANN401
        meta: Any = ...,  # noqa: ANN401
        name: str | int | None = ...,
        opacity: float | None = ...,
        showlegend: bool | None = ...,
        visible: bool | str | None = ...,
        **kwargs: Any,  # noqa: ANN401
    ) -> None: ...
    @classmethod
    def from_dict(
        cls,
        icicle_dict: RecursiveMapping[str, float],
        *,
        ids: Any = ...,  # noqa: ANN401
        labels: Any = ...,  # noqa: ANN401
        parents: Any = ...,  # noqa: ANN401
        values: Any = ...,  # noqa: ANN401
        branchvalues: str | None = ...,
        customdata: Any = ...,  # noqa: ANN401
        hovertemplate: str = ...,
        marker: Any = ...,  # noqa: ANN401
        meta: Any = ...,  # noqa: ANN401
        name: str | int | None = ...,
        opacity: float | None = ...,
        showlegend: bool | None = ...,
        visible: bool | str | None = ...,
        **kwargs: Any,  # noqa: ANN401
    ) -> Icicle: ...

def build_icicle(
    icicle_dict: RecursiveMapping[str, float],
    /,
) -> tuple[list[str], list[str], list[str], list[float]]: ...
