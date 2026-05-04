# NOTE: Some import statements are intentionally written as alias imports, i.e.
#       `import package.subpackage as subpackage`
#       This is necessary for subpackages for which no stubs have been created yet.
#       -> For these imports, DO NOT CHANGE the import statements to `from package import subpackage`.
#       Once stubs for these subpackages are created, the import statements can
#       be changed to their respective `from package import subpackage` form.

# Import of subpackages for which _no_ stubs have been created yet:
import plotly.graph_objs.parcats.legendgrouptitle as legendgrouptitle
import plotly.graph_objs.parcats.line as line

# Import of subpackages for which stubs have been created:
# -/-
#
# Direct import of names this subpackage exports:








__all__ = [
    "Dimension",
    "Domain",
    "Labelfont",
    "Legendgrouptitle",
    "Line",
    "Stream",
    "Tickfont",
    "legendgrouptitle",
    "line",
]

from typing import Any
from plotly.basedatatypes import BaseTraceHierarchyType

class Dimension(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Domain(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Labelfont(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Legendgrouptitle(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Line(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Stream(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Tickfont(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

