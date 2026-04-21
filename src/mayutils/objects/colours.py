"""Colour primitives, named palettes, and interoperability helpers.

This module exposes a :class:`Colour` dataclass that stores RGBA channel
values and provides parsing from and serialisation to the most common
colour encodings (hex, CSS functional notation, HSV, HSL, CMYK,
greyscale, named CSS colours, and ``python-pptx`` RGB values). Several
module-level constants expose curated palettes used throughout the
``mayutils`` plotting stack: ``MAIN_COLOURSCALE`` is the canonical
qualitative palette, ``SIMPLE_COLOURS`` is a reduced categorical
palette, ``CONTINUOUS_COLORSCALE`` and ``DIVERGENT_COLOURSCALE`` are
plotly-compatible position/colour pairs for continuous and diverging
scales, and ``OPACITIES`` lists standard alpha tiers. The helper
:func:`hex_to_rgba` is retained for lightweight conversion without
constructing a :class:`Colour` instance.
"""

from colorsys import rgb_to_hls, rgb_to_hsv
from dataclasses import dataclass
from typing import Literal, Self

from mayutils.core.extras import may_require_extras
from mayutils.objects.classes import (
    readonlyclassonlyproperty,
)

with may_require_extras():
    from PIL.ImageColor import colormap, getrgb
    from pptx.dml.color import RGBColor

reverse_colourmap: dict[str, str] = {value: key for key, value in colormap.items() if isinstance(value, str)}


MAIN_COLOURSCALE = {
    "quartz": "#FFCCFF",
    "pink": "#FF97FF",
    "bubblegum": "#FF85FF",
    "cherry": "#FF6692",
    "red": "#EF553B",
    "copper": "#CF4915",
    "coral": "#FFA15A",
    "orange": "#FF9C12",
    "peach": "#FFBD8E",
    "amber": "#FECB52",
    "yellow": "#FFE989",
    "lime": "#B6E880",
    "green": "#3BDB5F",
    "teal": "#00cc96",
    "mint": "#73DBB6",
    "cyan": "#30D5DB",
    "sky": "#19d3f3",
    "blue": "#636efa",
    "periwinkle": "#9299FD",
    "purple": "#ab63fa",
    "mauve": "#C592FD",
    "lavender": "#DEBFFF",
}
SIMPLE_COLOURS = {
    "lightgreen": "#73DBB6",
    "darkgreen": "#3BDB5F",
    "cyan": "#30D5DB",
    "blue": "#9299FD",
    "yellow": "#FFE989",
    "orange": "#FFBD8E",
    "red": "#F58B78",
    "purple": "#C592FD",
    "lightpink": "#FFCCFF",
    "pink": "#FF85FF",
}
BASE_COLOURSCALE = list(MAIN_COLOURSCALE.values())
CONTINUOUS_COLORSCALE: list[list[float | str]] = [
    [0.0, "#0d0887"],
    [0.1111111111111111, "#46039f"],
    [0.2222222222222222, "#7201a8"],
    [0.3333333333333333, "#9c179e"],
    [0.4444444444444444, "#bd3786"],
    [0.5555555555555556, "#d8576b"],
    [0.6666666666666666, "#ed7953"],
    [0.7777777777777778, "#fb9f3a"],
    [0.8888888888888888, "#fdca26"],
    [1.0, "#f0f921"],
]
DIVERGENT_COLOURSCALE: list[list[float | str]] = [
    [0.0, "#8e0152"],
    [0.1, "#c51b7d"],
    [0.2, "#de77ae"],
    [0.3, "#f1b6da"],
    [0.4, "#fde0ef"],
    [0.5, "#f7f7f7"],
    [0.6, "#e6f5d0"],
    [0.7, "#b8e186"],
    [0.8, "#7fbc41"],
    [0.9, "#4d9221"],
    [1.0, "#276419"],
]

OPACITIES = {
    "primary": 1.0,
    "secondary": 0.5,
    "tertiary": 0.4,
    "quaternary": 0.3,
}


@dataclass
class Colour:
    """Mutable RGBA colour with parsing, conversion, and rich display helpers.

    The instance stores the three 8-bit colour channels alongside a
    floating-point alpha channel and validates their ranges at
    construction time. Instances act as the canonical bridge between
    string-based colour encodings (hex, CSS functional, named CSS) and
    the numeric representations required by plotly, matplotlib and
    ``python-pptx``.

    Parameters
    ----------
    r : float
        Red intensity on the ``[0, 255]`` scale. Values nearer ``255``
        push the output toward pure red.
    g : float
        Green intensity on the ``[0, 255]`` scale. Values nearer ``255``
        push the output toward pure green.
    b : float
        Blue intensity on the ``[0, 255]`` scale. Values nearer ``255``
        push the output toward pure blue.
    a : float, default 1.0
        Alpha (opacity) on the ``[0, 1]`` scale, where ``0`` is fully
        transparent and ``1`` is fully opaque. Controls how the colour
        composites over a background in :meth:`blend` and in any
        ``rgba``/``hexa`` serialisation.

    Raises
    ------
    ValueError
        If any of ``r``, ``g``, ``b`` is outside ``[0, 255]`` or ``a``
        is outside ``[0, 1]``.

    Examples
    --------
    >>> Colour.parse("rgba(255, 0, 0, 0.5)").to_str()
    'rgba(255, 0, 0, 0.5)'
    """

    r: float
    g: float
    b: float
    a: float = 1.0

    @readonlyclassonlyproperty
    def css_map(
        self,
    ) -> dict[str, str]:
        """Lookup from lower-case hex string to the matching CSS colour name.

        The mapping is derived once from :data:`PIL.ImageColor.colormap`
        by inverting it so that ``to_str(method="css")`` can resolve a
        canonical CSS name for a given hex value.

        Returns
        -------
        dict[str, str]
            Hex strings in the form ``"#rrggbb"`` mapped to their CSS
            name such as ``"red"``. Only entries whose underlying value
            is a string (i.e. a real hex colour) are included.
        """
        return reverse_colourmap

    def __post_init__(
        self,
    ) -> None:
        """Validate channel ranges immediately after dataclass construction.

        Runs automatically as part of the dataclass-generated
        ``__init__`` and ensures that no instance can be created with
        out-of-range values that would silently produce invalid
        downstream colour strings.

        Raises
        ------
        ValueError
            If ``r``, ``g`` or ``b`` lies outside ``[0, 255]``, or if
            ``a`` lies outside ``[0, 1]``.
        """
        if not (0 <= self.r <= 256 - 1):
            msg = f"r out of range [0,255]: {self.r}"
            raise ValueError(msg)
        if not (0 <= self.g <= 256 - 1):
            msg = f"g out of range [0,255]: {self.g}"
            raise ValueError(msg)
        if not (0 <= self.b <= 256 - 1):
            msg = f"b out of range [0,255]: {self.b}"
            raise ValueError(msg)
        if not (0.0 <= self.a <= 1.0):
            msg = f"a out of range [0,1]: {self.a}"
            raise ValueError(msg)

    def round(
        self,
    ) -> Self:
        """Round each channel in place to the nearest integer.

        Useful after arithmetic operations such as :meth:`blend` that
        can produce fractional channel values which are not meaningful
        for 8-bit hex serialisation.

        Returns
        -------
        Colour
            The same instance (``self``) with ``r``, ``g``, ``b`` and
            ``a`` replaced by their rounded equivalents, enabling
            method chaining.
        """
        self.r = round(number=self.r)
        self.g = round(number=self.g)
        self.b = round(number=self.b)
        self.a = round(number=self.a)

        return self

    def values(
        self,
    ) -> tuple[float, float, float, float]:
        """Expose the four channels as a plain tuple.

        Provides positional access to the channel values for callers
        that want to unpack or iterate over them without touching
        dataclass attributes.

        Returns
        -------
        tuple[float, float, float, float]
            The ``(r, g, b, a)`` quadruple, with ``r``, ``g``, ``b`` in
            ``[0, 255]`` and ``a`` in ``[0, 1]``.
        """
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
        /,
    ) -> Self:
        """Construct a :class:`Colour` from any common string encoding.

        Delegates the bulk of the parsing to
        :func:`PIL.ImageColor.getrgb` while adding handling for the
        ``rgba(r, g, b, a)`` form with an explicit floating-point alpha
        channel, which PIL does not accept natively.

        Parameters
        ----------
        colour : str
            Colour string to parse. Accepts hex (``"#rrggbb"``),
            functional ``rgb(...)`` / ``rgba(...)``, CSS names such as
            ``"red"`` and any other form supported by
            :func:`PIL.ImageColor.getrgb`. When an ``rgba`` form with a
            four-value comma-separated payload is supplied the fourth
            value is interpreted as the alpha channel in ``[0, 1]``.

        Returns
        -------
        Colour
            A new instance populated with the parsed channel values.
            The alpha defaults to ``1.0`` when not supplied and is
            promoted to the PIL-returned alpha byte when present.
        """
        alpha_length = 4

        split = colour.split(sep=",")
        opacity = 1.0
        if not split[0].startswith("cmyk") and len(split) == alpha_length:
            opacity = float(split[3].split(")")[0].strip())
            colour = ",".join([split[0].replace("a", ""), split[1], split[2] + ")"])

        rgb = getrgb(colour)
        opacity = rgb[3] if len(rgb) == alpha_length else opacity  # ty:ignore[index-out-of-bounds]

        return cls(
            r=rgb[0],
            g=rgb[1],
            b=rgb[2],
            a=opacity,
        )

    def set_opacity(
        self,
        opacity: float,
        /,
    ) -> Self:
        """Replace the alpha channel in place.

        Mutates the instance so that the same :class:`Colour` object
        can be threaded through builders that want different opacities
        without allocating a new instance each time.

        Parameters
        ----------
        opacity : float
            New alpha value on the ``[0, 1]`` scale. Lower values make
            the colour more transparent when composited.

        Returns
        -------
        Colour
            The same instance with its ``a`` attribute updated, to
            allow chained calls.

        Raises
        ------
        ValueError
            If ``opacity`` is outside ``[0, 1]``.
        """
        if not (0.0 <= opacity <= 1.0):
            msg = f"a out of range [0,1]: {opacity}"
            raise ValueError(msg)

        self.a = opacity

        return self

    def _html_show(
        self,
        size: int = 50,
        /,
    ) -> str:
        """Build a minimal HTML swatch showing the colour.

        Produces a self-contained ``<div>`` whose background is painted
        using the instance's ``rgba(...)`` serialisation, suitable for
        embedding in Jupyter rich display output.

        Parameters
        ----------
        size : int, default 50
            Side length of the square swatch in CSS pixels. The same
            value is applied to both width and height.

        Returns
        -------
        str
            HTML string containing a single inline-styled ``<div>``
            element rendered in the requested colour.
        """
        return f'<div style="width:{size}px;height:{size}px;background-color:{self.to_str()};"></div>'

    def show(
        self,
    ) -> None:
        """Display the colour as a swatch in the active environment.

        Preferentially uses IPython's rich HTML display so the swatch
        renders inline in Jupyter. When IPython is not importable,
        falls back to matplotlib and draws a 1x1 inch axes patch
        coloured with the instance's hex value.

        Notes
        -----
        This method has no return value and performs only side
        effects. The fallback rendering discards alpha because
        matplotlib's ``set_facecolor`` is given the ``method="hex"``
        form of the colour.
        """
        try:
            from IPython.core.display import HTML  # noqa: PLC0415
            from IPython.display import display  # pyright: ignore[reportUnknownVariableType] # noqa: PLC0415

            display(HTML(data=self._html_show()))
        except ImportError:
            import matplotlib.pyplot as plt  # noqa: PLC0415

            fig, ax = plt.subplots(  # pyright: ignore[reportUnknownMemberType]
                figsize=(1, 1),
                dpi=100,
            )
            fig.patch.set_visible(False)
            ax.set_facecolor(color=self.to_str(method="hex"))

            ax.set_xticks(ticks=[])  # pyright: ignore[reportUnknownMemberType]
            ax.set_yticks(ticks=[])  # pyright: ignore[reportUnknownMemberType]
            ax.set_xlim(left=0, right=1)
            ax.set_ylim(bottom=0, top=1)
            for spine in ax.spines.values():
                spine.set_visible(False)

            plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

            plt.show()  # pyright: ignore[reportUnknownMemberType]

    def to_str(  # noqa: C901, PLR0911, PLR0912
        self,
        *,
        opacity: float | None = None,
        method: Literal[
            "hex",
            "hex3",
            "hexa",
            "hexa?",
            "rgb",
            "rgba",
            "rgba?",
            "hsv",
            "hsva",
            "hsva?",
            "hsl",
            "hsla",
            "hsla?",
            "css",
            "cmyk",
            "grayscale",
        ] = "rgba",
    ) -> str:
        """Serialise the colour to a string in one of several encodings.

        Acts as the primary dispatch point for converting the instance
        to any of the textual colour forms understood by CSS, plotly,
        the HTML ``style`` attribute and similar consumers. Variants
        suffixed with ``?`` emit the alpha component only when it is
        strictly less than one, mirroring common CSS short-hand rules.

        Parameters
        ----------
        opacity : float or None, default None
            When provided, overrides the instance's alpha channel for
            this call only. Leaves the stored ``a`` untouched. Callers
            use this to render the same colour at multiple opacities
            without mutating the instance.
        method : str, default ``"rgba"``
            Selects the output encoding. Accepted values are:

            - ``"hex"`` — six-digit ``#rrggbb`` without alpha.
            - ``"hex3"`` — three-digit ``#rgb`` short hex (only valid
              when every channel is divisible by ``17``).
            - ``"hexa"`` — eight-digit ``#rrggbbaa`` with alpha.
            - ``"hexa?"`` — six-digit hex when opaque, eight-digit hex
              otherwise.
            - ``"rgb"`` / ``"rgba"`` — CSS functional notation without
              or with the alpha channel.
            - ``"rgba?"`` — ``rgb(...)`` when opaque, ``rgba(...)``
              otherwise.
            - ``"hsv"`` / ``"hsva"`` / ``"hsva?"`` — HSV functional
              notation (hue in degrees, saturation and value as
              percentages), optionally with alpha.
            - ``"hsl"`` / ``"hsla"`` / ``"hsla?"`` — HSL functional
              notation using ``rgb_to_hls`` (hue in degrees, saturation
              and lightness as percentages), optionally with alpha.
            - ``"css"`` — CSS colour name when the hex value matches a
              named entry in :attr:`css_map`.
            - ``"cmyk"`` — functional ``cmyk(c%, m%, y%, k%)``.
            - ``"grayscale"`` — BT.601 luminance rendered as its
              floating-point string representation.

        Returns
        -------
        str
            The serialised colour in the requested encoding.

        Raises
        ------
        ValueError
            If ``method`` is not one of the supported values, if
            ``method="hex3"`` is requested but one or more channels are
            not divisible by ``17``, or if ``method="css"`` is
            requested but the colour has no matching named entry in
            :attr:`css_map`.
        """
        r, g, b, a = self.values()
        a = a if opacity is None else opacity

        if method.startswith("rgb"):
            if method == "rgb" or (method == "rgba?" and a == 1):
                return f"rgb({r}, {g}, {b})"
            if method == "rgba" or (method == "rgba?" and a < 1):
                return f"rgba({r}, {g}, {b}, {a})"
        elif method.startswith("hex"):
            if method == "hex" or (method == "hexa?" and a == 1):
                return f"#{r:02x}{g:02x}{b:02x}"
            if method == "hexa" or (method == "hexa?" and a < 1):
                return f"#{r:02x}{g:02x}{b:02x}{round(a * 255):02x}"
            if method == "hex3":
                shortened = [val // 17 if val % 17 == 0 else None for val in [r, g, b]]
                if None in shortened:
                    msg = "Colour is not valid 3 character hex code (each r,g,b channel must be divisible by 17)"
                    raise ValueError(msg)

                return "#" + "".join(f"{val:x}" for val in shortened)
        elif method.startswith("hsv"):
            h, s, v = self.to_hsv()
            if method == "hsv" or (method == "hsva?" and a == 1):
                return f"hsv({h * 360}, {s * 100}%, {v * 100}%)"
            if method == "hsva" or (method == "hsva?" and a < 1):
                return f"hsva({h * 360}, {s * 100}%, {v * 100}%, {a})"
        elif method.startswith("hsl"):
            h, l, s = self.to_hls()  # noqa: E741
            if method == "hsl" or (method == "hsla?" and a == 1):
                return f"hsl({h * 360}, {s * 100}%, {l * 100}%)"
            if method == "hsla" or (method == "hsla?" and a < 1):
                return f"hsl({h * 360}, {s * 100}%, {l * 100}%, {a})"
        elif method == "cmyk":
            c, m, y, k = self.to_cmyk()
            return f"cmyk({c * 100}%, {m * 100}%, {y * 100}%, {k * 100}%)"
        elif method == "grayscale":
            gs = self.to_grayscale()
            return f"{gs}"
        elif method == "css":
            hex_str = self.to_str(method="hex").lower()
            css = Colour.css_map.get(hex_str, None)

            if css is not None:
                return css

            msg = f"Colour {hex_str} is not a known css colour. See `Colour.css_map` for all possibilities."
            raise ValueError(msg)

        msg = f"Unknown method {method} passed."
        raise ValueError(msg)

    def __str__(
        self,
    ) -> str:
        """Return the default string representation using ``rgba(...)`` form.

        Equivalent to calling :meth:`to_str` with its default
        ``method="rgba"`` argument, so ``str(colour)`` always produces
        a valid CSS functional string including the alpha channel.

        Returns
        -------
        str
            The ``rgba(r, g, b, a)`` serialisation of the instance.
        """
        return self.to_str()

    def __repr_html__(
        self,
    ) -> str:
        """Build a rich HTML representation for notebook environments.

        Combines the visual swatch produced by :meth:`_html_show` with
        the textual form returned by :meth:`to_str` so that both the
        hue and the exact value are visible in Jupyter-style displays.

        Returns
        -------
        str
            HTML string containing the swatch ``<div>`` followed by a
            ``<p>`` element holding the default ``rgba(...)`` form.
        """
        return self._html_show() + f"<p>{self.to_str()}</p>"

    def to_hsv(
        self,
    ) -> tuple[float, float, float]:
        """Convert the colour to the HSV colour model.

        Uses :func:`colorsys.rgb_to_hsv` after normalising the RGB
        channels from ``[0, 255]`` to ``[0, 1]``. The alpha channel is
        not part of the output because HSV is defined on RGB alone.

        Returns
        -------
        tuple[float, float, float]
            The ``(h, s, v)`` triple with each component in ``[0, 1]``,
            where ``h`` is the hue angle normalised to a unit interval,
            ``s`` is saturation and ``v`` is value (brightness).
        """
        return rgb_to_hsv(*[val / 255 for val in self.values()[:3]])

    def to_hls(
        self,
    ) -> tuple[float, float, float]:
        """Convert the colour to the HLS colour model.

        Uses :func:`colorsys.rgb_to_hls` after normalising the RGB
        channels from ``[0, 255]`` to ``[0, 1]``. The alpha channel is
        not part of the output because HLS is defined on RGB alone.

        Returns
        -------
        tuple[float, float, float]
            The ``(h, l, s)`` triple with each component in ``[0, 1]``,
            where ``h`` is the hue angle normalised to a unit interval,
            ``l`` is lightness and ``s`` is saturation.
        """
        return rgb_to_hls(*[val / 255 for val in self.values()[:3]])

    def to_cmyk(
        self,
    ) -> tuple[float, float, float, float]:
        """Convert the colour to the CMYK colour model.

        Uses the standard subtractive conversion from normalised RGB
        without ICC profile adjustment, which is adequate for screen
        and documentation use. If the computed key is ``1`` (pure
        black) the chromatic components collapse to zero to avoid
        division by zero.

        Returns
        -------
        tuple[float, float, float, float]
            The ``(c, m, y, k)`` quadruple with each component in
            ``[0, 1]``, where ``c``, ``m`` and ``y`` are the cyan,
            magenta and yellow proportions and ``k`` is the key
            (black) proportion.
        """
        r, g, b, _a = [val / 255 for val in self.values()]

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
        """Compute the perceptual luminance using BT.601 weights.

        Applies the ITU-R BT.601 coefficients ``(0.2989, 0.5870,
        0.1140)`` to the RGB channels, matching the luma calculation
        used by legacy standard-definition video and many greyscale
        conversion utilities.

        Returns
        -------
        float
            The scalar luminance on the ``[0, 255]`` scale. Higher
            values correspond to lighter colours.
        """
        r, g, b = self.values()[:3]
        return 0.2989 * r + 0.5870 * g + 0.1140 * b

    @classmethod
    def blend(
        cls,
        *,
        foreground: Self,
        background: Self,
    ) -> Self:
        """Alpha-composite a foreground colour over an opaque background.

        Implements the standard source-over compositing formula
        ``out = fg * a + bg * (1 - a)`` channel-by-channel. Because
        the formula assumes an opaque backdrop, the ``background``
        argument must have alpha equal to one; the resulting colour is
        always fully opaque.

        Parameters
        ----------
        foreground : Colour
            The overlay colour. Its alpha channel controls the mix
            ratio with the background.
        background : Colour
            The base colour underneath the overlay. Must be fully
            opaque because the formula does not accumulate alpha.

        Returns
        -------
        Colour
            A new instance whose RGB channels are the weighted
            combination of ``foreground`` and ``background`` and whose
            alpha is the default ``1.0``.

        Raises
        ------
        ValueError
            If ``background.a`` is not exactly ``1``.
        """
        if background.a != 1:
            msg = "Background colour must have 0 opacity"
            raise ValueError(msg)

        r, g, b, a = foreground.values()
        r2, g2, b2 = background.values()[:3]

        return cls(
            r=r * a + r2 * (1 - a),
            g=g * a + g2 * (1 - a),
            b=b * a + b2 * (1 - a),
        )

    @property
    def pptx_colour(
        self,
    ) -> RGBColor:
        """Build a ``python-pptx`` ``RGBColor`` from this instance.

        PowerPoint's object model uses the :class:`pptx.dml.color.RGBColor`
        wrapper to represent solid fill colours. This property
        constructs one from the current ``r``, ``g`` and ``b`` values.

        Returns
        -------
        pptx.dml.color.RGBColor
            Equivalent PowerPoint colour carrying only the RGB
            channels. The alpha component is dropped because
            ``RGBColor`` does not model transparency.
        """
        return RGBColor(
            r=self.r,
            g=self.g,
            b=self.b,
        )


def hex_to_rgba(
    hex_colour: str,
    /,
    *,
    alpha: float = 1.0,
) -> str:
    """Convert a hex colour string into a CSS ``rgba(...)`` string.

    Provides a lightweight conversion that does not require
    constructing a :class:`Colour` instance. Supports both the
    six-digit ``#rrggbb`` form (where the caller supplies alpha via
    ``alpha``) and the eight-digit ``#rrggbbaa`` form (where the alpha
    byte is read from the string and rescaled to ``[0, 1]``).

    Parameters
    ----------
    hex_colour : str
        Hex colour to convert, with or without a leading ``#``. The
        stripped payload must be exactly six or eight hex characters.
    alpha : float, default 1.0
        Fallback alpha value used when ``hex_colour`` contains only
        six hex digits. Ignored when the string already carries an
        alpha byte.

    Returns
    -------
    str
        A CSS-compatible ``rgba(r, g, b, a)`` string, with ``r``,
        ``g``, ``b`` as integers and ``a`` as a float.

    Raises
    ------
    ValueError
        If the stripped hex payload is neither six nor eight
        characters long.
    """
    alphahex_length = 8

    hex_colour = hex_colour.lstrip("#")
    length = len(hex_colour)

    if len(hex_colour) in (6, 8):
        values = [int(hex_colour[i : i + 2], 16) for i in range(0, length, 2)]

        if len(hex_colour) == alphahex_length:
            alpha = round(number=values.pop() / 255, ndigits=2)

        return f"rgba({values[0]}, {values[1]}, {values[2]}, {alpha})"

    msg = "Invalid hex colour format. Use #RRGGBB or #RRGGBBAA"
    raise ValueError(msg)


TRANSPARENT = Colour.parse("rgba(0,0,0,0)")
SPECTRUM = {name: Colour.parse(colour) for name, colour in MAIN_COLOURSCALE.items()}
