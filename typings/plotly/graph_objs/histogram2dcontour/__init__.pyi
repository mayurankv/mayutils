# NOTE: Some import statements are intentionally written as alias imports, i.e.
#       `import package.subpackage as subpackage`
#       This is necessary for subpackages for which no stubs have been created yet.
#       -> For these imports, DO NOT CHANGE the import statements to `from package import subpackage`.
#       Once stubs for these subpackages are created, the import statements can
#       be changed to their respective `from package import subpackage` form.

# Import of subpackages for which _no_ stubs have been created yet:
import plotly.graph_objs.histogram2dcontour.colorbar as colorbar
import plotly.graph_objs.histogram2dcontour.contours as contours
import plotly.graph_objs.histogram2dcontour.hoverlabel as hoverlabel
import plotly.graph_objs.histogram2dcontour.legendgrouptitle as legendgrouptitle

# Import of subpackages for which stubs have been created:
# -/-
#
# Direct import of names this subpackage exports:











__all__ = [
    "ColorBar",
    "Contours",
    "Hoverlabel",
    "Legendgrouptitle",
    "Line",
    "Marker",
    "Stream",
    "Textfont",
    "XBins",
    "YBins",
    "colorbar",
    "contours",
    "hoverlabel",
    "legendgrouptitle",
]

from typing import Any
from plotly.basedatatypes import BaseTraceHierarchyType

class ColorBar(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Contours(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Hoverlabel(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Legendgrouptitle(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Line(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Marker(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Stream(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Textfont(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class XBins(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class YBins(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

