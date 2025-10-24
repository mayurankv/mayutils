from _typeshed import Incomplete
from mayutils.objects.colours import Colour as Colour
from pathlib import Path
from pptx.shapes.autoshape import Shape as Shape
from pptx.slide import (
    Slide as Slide,
    SlideLayout as SlideLayout,
    SlideLayouts as SlideLayouts,
    Slides as Slides,
)
from pptx.util import Length as BaseLength
from typing import Self

class Length(BaseLength):
    @classmethod
    def from_float(cls, value: float) -> Self: ...

class Presentation:
    template: Incomplete
    internal: Incomplete
    blank_layout: Incomplete
    def __init__(self, template: Path | str) -> None: ...
    @property
    def layouts(self) -> SlideLayouts: ...
    @property
    def height(self) -> Length: ...
    @height.setter
    def height(self, value: Length) -> None: ...
    @property
    def width(self) -> Length: ...
    @width.setter
    def width(self, value: Length) -> None: ...
    @property
    def slides(self) -> Slides: ...
    def slide(self, slide_number: int) -> Slide: ...
    def new_slide(self, layout: SlideLayout | None = None) -> Self: ...
    def empty(self) -> Self: ...
    def delete_slide(self, slide_number: int) -> Self: ...
    def copy_slide(self, slide_number: int) -> Self: ...
    def move_slide(self, slide_number: int, to_position: int) -> Self: ...
    def reorder_slides(self, new_order: list[int]) -> Self: ...
    def insertion_spacing(
        self,
        height: Length | None = None,
        width: Length | None = None,
        x_shift: Length | None = None,
        y_shift: Length | None = None,
    ) -> dict: ...
    def insert_textbox(
        self,
        slide_number: int | None = None,
        height: Length | None = None,
        width: Length | None = None,
        x_shift: Length | None = None,
        y_shift: Length | None = None,
        **kwargs,
    ) -> Shape: ...
    def insert_text(
        self,
        text: str,
        textbox: Shape,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        strikethrough: bool = False,
        font_size: int | None = None,
        font_family: str | None = None,
        colour: Colour | str | None = None,
        background_colour: Colour | str | None = None,
        link: str | None = None,
    ) -> Self: ...
    def save(self, file_path: Path | str) -> None: ...
