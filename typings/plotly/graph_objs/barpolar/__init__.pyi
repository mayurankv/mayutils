# NOTE: Some import statements are intentionally written as alias imports, i.e.
#       `import package.subpackage as subpackage`
#       This is necessary for subpackages for which no stubs have been created yet.
#       -> For these imports, DO NOT CHANGE the import statements to `from package import subpackage`.
#       Once stubs for these subpackages are created, the import statements can
#       be changed to their respective `from package import subpackage` form.

# Import of subpackages for which _no_ stubs have been created yet:
import plotly.graph_objs.barpolar.hoverlabel as hoverlabel  # no stub created yet
import plotly.graph_objs.barpolar.legendgrouptitle as legendgrouptitle  # no stub created yet
import plotly.graph_objs.barpolar.marker as marker  # no stub created yet
import plotly.graph_objs.barpolar.selected as selected  # no stub created yet
import plotly.graph_objs.barpolar.unselected as unselected  # no stub created yet

# Import of subpackages for which stubs have been created:
# -/-
#
# Direct import of names this subpackage exports:







__all__ = [
    "Hoverlabel",
    "Legendgrouptitle",
    "Marker",
    "Selected",
    "Stream",
    "Unselected",
    "hoverlabel",
    "legendgrouptitle",
    "marker",
    "selected",
    "unselected",
]

from typing import Any
from plotly.basedatatypes import BaseTraceHierarchyType

class Hoverlabel(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Legendgrouptitle(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Marker(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Selected(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Stream(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Unselected(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

