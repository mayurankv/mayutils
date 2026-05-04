from plotly.graph_objs.choropleth._marker import Marker

__all__ = [
    "Marker",
]

from typing import Any
from plotly.basedatatypes import BaseTraceHierarchyType

class Marker(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

