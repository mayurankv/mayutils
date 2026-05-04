# NOTE: Some import statements are intentionally written as alias imports, i.e.
#       `import package.subpackage as subpackage`
#       This is necessary for subpackages for which no stubs have been created yet.
#       -> For these imports, DO NOT CHANGE the import statements to `from package import subpackage`.
#       Once stubs for these subpackages are created, the import statements can
#       be changed to their respective `from package import subpackage` form.

# Import of subpackages for which _no_ stubs have been created yet:
import plotly.graph_objs.table.cells as cells
import plotly.graph_objs.table.header as header
import plotly.graph_objs.table.hoverlabel as hoverlabel
import plotly.graph_objs.table.legendgrouptitle as legendgrouptitle

# Import of subpackages for which stubs have been created:
# -/-
#
# Direct import of names this subpackage exports:







__all__ = [
    "Cells",
    "Domain",
    "Header",
    "Hoverlabel",
    "Legendgrouptitle",
    "Stream",
    "cells",
    "header",
    "hoverlabel",
    "legendgrouptitle",
]

from typing import Any
from plotly.basedatatypes import BaseTraceHierarchyType

class Cells(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Domain(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Header(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Hoverlabel(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Legendgrouptitle(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Stream(BaseTraceHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

