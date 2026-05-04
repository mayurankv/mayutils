# NOTE: Some import statements are intentionally written as alias imports, i.e.
#       `import package.subpackage as subpackage`
#       This is necessary for subpackages for which no stubs have been created yet.
#       -> For these imports, DO NOT CHANGE the import statements to `from package import subpackage`.
#       Once stubs for these subpackages are created, the import statements can
#       be changed to their respective `from package import subpackage` form.

# Import of subpackages for which _no_ stubs have been created yet:
import plotly.graph_objs.waterfall.connector as connector
import plotly.graph_objs.waterfall.decreasing as decreasing
import plotly.graph_objs.waterfall.hoverlabel as hoverlabel
import plotly.graph_objs.waterfall.increasing as increasing
import plotly.graph_objs.waterfall.legendgrouptitle as legendgrouptitle
import plotly.graph_objs.waterfall.totals as totals

# Import of subpackages for which stubs have been created:
# -/-
#
# Direct import of names this subpackage exports:











__all__ = [
    "Connector",
    "Decreasing",
    "Hoverlabel",
    "Increasing",
    "Insidetextfont",
    "Legendgrouptitle",
    "Outsidetextfont",
    "Stream",
    "Textfont",
    "Totals",
    "connector",
    "decreasing",
    "hoverlabel",
    "increasing",
    "legendgrouptitle",
    "totals",
]

from typing import Any
from plotly.basedatatypes import BaseTraceHierarchyType

class Connector(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Decreasing(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Hoverlabel(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Increasing(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Insidetextfont(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Legendgrouptitle(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Outsidetextfont(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Stream(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Textfont(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Totals(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

