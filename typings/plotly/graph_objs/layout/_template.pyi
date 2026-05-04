from typing import Any

from plotly.basedatatypes import BaseLayoutHierarchyType


class Template(BaseLayoutHierarchyType):
    def __init__(
        self,
        arg: dict[str, Any] | None = ...,
        *,
        data: Any = ...,
        layout: Any = ...,
        **kwargs: Any,
    ) -> None: ...
    @property
    def data(self) -> Any: ...
    @data.setter
    def data(self, val: Any) -> None: ...
    @property
    def layout(self) -> Any: ...
    @layout.setter
    def layout(self, val: Any) -> None: ...
