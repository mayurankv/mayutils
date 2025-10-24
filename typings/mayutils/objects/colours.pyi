from _typeshed import Incomplete
from dataclasses import dataclass
from mayutils.objects.classes import (
    readonlyclassonlyproperty as readonlyclassonlyproperty,
)
from typing import Literal, Self

reverse_colourmap: dict[str, str]
MAIN_COLOURSCALE: Incomplete
SIMPLE_COLOURS: Incomplete
BASE_COLOURSCALE: Incomplete
CONTINUOUS_COLORSCALE: Incomplete
DIVERGENT_COLOURSCALE: Incomplete
OPACITIES: Incomplete

@dataclass
class Colour:
    r: float
    g: float
    b: float
    a: float = ...
    @readonlyclassonlyproperty
    def css_map(cls) -> dict[str, str]: ...
    def __post_init__(self) -> None: ...
    def round(self) -> Self: ...
    def values(self) -> tuple[float, float, float, float]: ...
    @classmethod
    def parse(cls, colour: str) -> Self: ...
    def set_opacity(self, opacity: float) -> Self: ...
    def show(self) -> None: ...
    def to_str(
        self,
        opacity: float | None = None,
        method: Literal[
            "hex",
            "hex3",
            "rgb",
            "rgba",
            "rgba?",
            "hsv",
            "hsl",
            "hsla",
            "hsla?",
            "css",
            "cmyk",
            "grayscale",
        ] = "rgba",
    ) -> str: ...
    def __repr_html__(self) -> str: ...
    def to_hsv(self) -> tuple[float, float, float]: ...
    def to_hls(self) -> tuple[float, float, float]: ...
    def to_cmyk(self) -> tuple[float, float, float, float]: ...
    def to_grayscale(self) -> float: ...
    @classmethod
    def blend(cls, foreground: Self, background: Self) -> Self: ...

def hex_to_rgba(hex_colour: str, alpha: float = 1.0) -> str: ...

TRANSPARENT: Incomplete
SPECTRUM: Incomplete
