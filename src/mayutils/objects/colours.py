from dataclasses import dataclass
from typing import Literal, Optional, Self
from PIL.ImageColor import getrgb, colormap
from colorsys import rgb_to_hsv, rgb_to_hls

from mayutils.objects.classes import (
    readonlyclassonlyproperty,
)

reverse_colourmap: dict[str, str] = {value: key for key, value in colormap.items()}  # type: ignore


@dataclass
class Colour:
    r: float
    g: float
    b: float
    a: float = 1.0

    @readonlyclassonlyproperty
    def css_map(
        cls,
    ) -> dict[str, str]:
        return reverse_colourmap

    def __post_init__(self):
        if not (0 <= self.r <= 255):
            raise ValueError(f"r out of range [0,255]: {self.r}")
        if not (0 <= self.g <= 255):
            raise ValueError(f"g out of range [0,255]: {self.g}")
        if not (0 <= self.b <= 255):
            raise ValueError(f"b out of range [0,255]: {self.b}")
        if not (0.0 <= self.a <= 1.0):
            raise ValueError(f"a out of range [0,1]: {self.a}")

    def round(
        self,
    ) -> Self:
        self.r = round(self.r)
        self.g = round(self.g)
        self.b = round(self.b)
        self.a = round(self.a)

        return self

    def values(
        self,
    ) -> tuple[float, float, float, float]:
        return (
            self.r,
            self.g,
            self.b,
            self.a,
        )

    @classmethod
    def parse(
        cls,
        colour: str,
    ) -> Self:
        split = colour.split(",")
        opacity = 1.0
        if not split[0].startswith("cmyk") and len(split) == 4:
            opacity = float(split[3].split(")")[0].strip())
            colour = ",".join([split[0].replace("a", ""), split[1], split[2] + ")"])

        rgb = getrgb(colour)
        opacity = rgb[3] if len(rgb) == 4 else opacity

        return cls(*rgb[:3], a=opacity)

    def set_opacity(
        self,
        opacity: float,
    ) -> Self:
        if not (0.0 <= opacity <= 1.0):
            raise ValueError(f"a out of range [0,1]: {opacity}")

        self.a = opacity

        return self

    def to_str(
        self,
        opacity: Optional[float] = None,
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
    ) -> str:
        r, g, b, a = self.values()
        a = a if opacity is None else opacity

        if method.startswith("rgb"):
            if method == "rgb" or (method == "rgba?" and a == 1):
                return f"rgb({r}, {g}, {b})"
            elif method == "rgba" or (method == "rgba?" and a < 1):
                return f"rgba({r}, {g}, {b}, {a})"
        elif method.startswith("hex"):
            if method == "hex" or (method == "hexa?" and a == 1):
                return f"#{r:02x}{g:02x}{b:02x}"
            elif method == "hexa" or (method == "hexa?" and a < 1):
                return f"#{r:02x}{g:02x}{b:02x}{int(round(a * 255)):02x}"
            elif method == "hex3":
                shortened = [val // 17 if val % 17 == 0 else None for val in [r, g, b]]
                if None in shortened:
                    raise ValueError(
                        "Colour is not valid 3 character hex code (each r,g,b channel must be divisible by 17)"
                    )
                return "#" + "".join(f"{val:x}" for val in shortened)
        elif method.startswith("hsv"):
            h, s, v = self.to_hsv()
            if method == "hsv" or (method == "hsva?" and a == 1):
                return f"hsv({h * 360}, {s * 100}%, {v * 100}%)"
            elif method == "hsva" or (method == "hsva?" and a < 1):
                return f"hsva({h * 360}, {s * 100}%, {v * 100}%, {a})"
        elif method.startswith("hsl"):
            h, l, s = self.to_hls()  # noqa: E741
            if method == "hsl" or (method == "hsla?" and a == 1):
                return f"hsl({h * 360}, {s * 100}%, {l * 100}%)"
            elif method == "hsla" or (method == "hsla?" and a < 1):
                return f"hsl({h * 360}, {s * 100}%, {l * 100}%, {a})"
        elif method == "cmyk":
            c, m, y, k = self.to_cmyk()
            return f"cmyk({c * 100}%, {m * 100}%, {y * 100}%, {k * 100}%)"
        elif method == "grayscale":
            gs = self.to_grayscale()
            return f"{gs}"
        elif method == "css":
            hex = self.to_str(method="hex").lower()
            css = Colour.css_map.get(hex, None)
            if css is not None:
                return css
            else:
                raise ValueError(
                    f"Colour {hex} is not a known css colour. See `Colour.css_map` for all possibilities."
                )

        raise ValueError(f"Unknown method {method} passed.")

    def __str__(
        self,
    ) -> str:
        return self.to_str()

    def to_hsv(
        self,
    ) -> tuple[float, float, float]:
        return rgb_to_hsv(*[val / 255 for val in self.values()[:3]])

    def to_hls(
        self,
    ) -> tuple[float, float, float]:
        return rgb_to_hls(*[val / 255 for val in self.values()[:3]])

    def to_cmyk(
        self,
    ) -> tuple[float, float, float, float]:
        r, g, b, a = [val / 255 for val in self.values()]

        k = 1 - max([r, g, b])
        if k != 1:
            c = (1 - r - k) / (1 - k)
            m = (1 - g - k) / (1 - k)
            y = (1 - b - k) / (1 - k)
        else:
            c, m, y = 0, 0, 0

        return c, m, y, k

    def to_grayscale(
        self,
    ) -> float:
        r, g, b = self.values()[:3]
        gs = 0.2989 * r + 0.5870 * g + 0.1140 * b

        return gs

    @classmethod
    def blend(
        cls,
        foreground: Self,
        background: Self,
    ) -> Self:
        if background.a != 1:
            raise ValueError("Background colour must have 0 opacity")

        r, g, b, a = foreground.values()
        r2, g2, b2 = background.values()[:3]

        blended = cls(
            r=r * a + r2 * (1 - a),
            g=g * a + g2 * (1 - a),
            b=b * a + b2 * (1 - a),
        )

        return blended


def hex_to_rgba(
    hex_colour: str,
    alpha: float = 1.0,
) -> str:
    hex_colour = hex_colour.lstrip("#")
    length = len(hex_colour)

    if len(hex_colour) in (6, 8):
        values = [int(hex_colour[i : i + 2], 16) for i in range(0, length, 2)]

        if len(hex_colour) == 8:  # If alpha is provided in hex
            alpha = round(values.pop() / 255, 2)

        return f"rgba({values[0]}, {values[1]}, {values[2]}, {alpha})"
    else:
        raise ValueError("Invalid hex colour format. Use #RRGGBB or #RRGGBBAA")
