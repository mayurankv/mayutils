# NOTE: Some import statements are intentionally written as alias imports, i.e.
#       `import package.subpackage as subpackage`
#       This is necessary for subpackages for which no stubs have been created yet.
#       -> For these imports, DO NOT CHANGE the import statements to `from package import subpackage`.
#       Once stubs for these subpackages are created, the import statements can
#       be changed to their respective `from package import subpackage` form.

# Import of subpackages for which _no_ stubs have been created yet:
import plotly.graph_objs.layout.annotation as annotation
import plotly.graph_objs.layout.coloraxis as coloraxis
import plotly.graph_objs.layout.geo as geo
import plotly.graph_objs.layout.grid as grid
import plotly.graph_objs.layout.hoverlabel as hoverlabel
import plotly.graph_objs.layout.legend as legend
import plotly.graph_objs.layout.map as map  # noqa: A004
import plotly.graph_objs.layout.mapbox as mapbox
import plotly.graph_objs.layout.newshape as newshape
import plotly.graph_objs.layout.polar as polar
import plotly.graph_objs.layout.scene as scene
import plotly.graph_objs.layout.selection as selection
import plotly.graph_objs.layout.shape as shape
import plotly.graph_objs.layout.slider as slider
import plotly.graph_objs.layout.smith as smith
import plotly.graph_objs.layout.template as template
import plotly.graph_objs.layout.ternary as ternary
import plotly.graph_objs.layout.title as title
import plotly.graph_objs.layout.updatemenu as updatemenu
import plotly.graph_objs.layout.xaxis as xaxis
import plotly.graph_objs.layout.yaxis as yaxis

# Import of subpackages for which stubs have been created:
from plotly.graph_objs.layout import newselection

#
# Direct import of names this subpackage exports:


from plotly.graph_objs.layout._annotation import Annotation










from plotly.graph_objs.layout._margin import Margin











from plotly.graph_objs.layout._title import Title






__all__ = [
    "Activeselection",
    "Activeshape",
    "Annotation",
    "Coloraxis",
    "Colorscale",
    "Font",
    "Geo",
    "Grid",
    "Hoverlabel",
    "Image",
    "Legend",
    "Map",
    "Mapbox",
    "Margin",
    "Modebar",
    "Newselection",
    "Newshape",
    "Polar",
    "Scene",
    "Selection",
    "Shape",
    "Slider",
    "Smith",
    "Template",
    "Ternary",
    "Title",
    "Transition",
    "Uniformtext",
    "Updatemenu",
    "XAxis",
    "YAxis",
    "annotation",
    "coloraxis",
    "geo",
    "grid",
    "hoverlabel",
    "legend",
    "map",
    "mapbox",
    "newselection",
    "newshape",
    "polar",
    "scene",
    "selection",
    "shape",
    "slider",
    "smith",
    "template",
    "ternary",
    "title",
    "updatemenu",
    "xaxis",
    "yaxis",
]

from typing import Any
from plotly.basedatatypes import BaseLayoutHierarchyType

class Activeselection(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Activeshape(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Coloraxis(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Colorscale(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Font(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Geo(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Grid(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Hoverlabel(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Image(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Legend(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Map(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Mapbox(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Modebar(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Newselection(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Newshape(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Polar(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Scene(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Selection(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Shape(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Slider(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Smith(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Template(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Ternary(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Transition(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Uniformtext(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class Updatemenu(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class XAxis(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class YAxis(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

class newselection(BaseLayoutHierarchyType):
    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...

