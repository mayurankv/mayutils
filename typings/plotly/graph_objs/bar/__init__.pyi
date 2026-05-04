# NOTE: Some import statements are intentionally written as alias imports, i.e.
#       `import package.subpackage as subpackage`
#       This is necessary for subpackages for which no stubs have been created yet.
#       -> For these imports, DO NOT CHANGE the import statements to `from package import subpackage`.
#       Once stubs for these subpackages are created, the import statements can
#       be changed to their respective `from package import subpackage` form.

# Import of subpackages for which _no_ stubs have been created yet:
import plotly.graph_objs.bar.hoverlabel as hoverlabel
import plotly.graph_objs.bar.legendgrouptitle as legendgrouptitle
import plotly.graph_objs.bar.marker as marker

# Import of subpackages for which stubs have been created:
import plotly.graph_objs.bar.selected as selected
import plotly.graph_objs.bar.unselected as unselected

# Direct import of names this subpackage exports:
from plotly.graph_objs.bar._error_x import ErrorX
from plotly.graph_objs.bar._error_y import ErrorY






from plotly.graph_objs.bar._stream import Stream



__all__ = [
    "ErrorX",
    "ErrorY",
    "Hoverlabel",
    "Insidetextfont",
    "Legendgrouptitle",
    "Marker",
    "Outsidetextfont",
    "Selected",
    "Stream",
    "Textfont",
    "Unselected",
    "hoverlabel",
    "legendgrouptitle",
    "marker",
    "selected",
    "unselected",
]

from typing import Any
from plotly.basedatatypes import BaseTraceHierarchyType

class ErrorX(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class ErrorY(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Hoverlabel(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Insidetextfont(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Legendgrouptitle(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Marker(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Outsidetextfont(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Selected(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Textfont(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Unselected(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

