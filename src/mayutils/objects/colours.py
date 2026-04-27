"""
Provide colour primitives, named palettes, and interoperability helpers.

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

See Also
--------
matplotlib.colors : General matplotlib colour conversion utilities.
plotly.colors : Plotly palette and colourscale primitives.
Colour : Core RGBA wrapper defined in this module.
hex_to_rgba : Lightweight hex-to-rgba conversion helper.

Examples
--------
>>> Colour.parse("#ff0000").to_str(method="hex")
'#ff0000'
>>> hex_to_rgba("#336699", alpha=0.5)
'rgba(51, 102, 153, 0.5)'
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

TRANSPARENT_RGBA = "rgba(0,0,0,0)"


@dataclass
class Colour:
    """
    Model a mutable RGBA colour with parsing, conversion, and display helpers.

    The instance stores the three 8-bit colour channels alongside a
    floating-point alpha channel and validates their ranges at
    construction time. Instances act as the canonical bridge between
    string-based colour encodings (hex, CSS functional, named CSS) and
    the numeric representations required by plotly, matplotlib and
    ``python-pptx``. Conversion methods cover HSV, HLS, CMYK and BT.601
    luminance; :meth:`blend` performs source-over alpha compositing so
    transparent colours can be flattened against an opaque backdrop.

    Attributes
    ----------
    r
        Red intensity on the ``[0, 255]`` scale. Values nearer ``255``
        push the output toward pure red.
    g
        Green intensity on the ``[0, 255]`` scale. Values nearer ``255``
        push the output toward pure green.
    b
        Blue intensity on the ``[0, 255]`` scale. Values nearer ``255``
        push the output toward pure blue.
    a
        Alpha (opacity) on the ``[0, 1]`` scale, where ``0`` is fully
        transparent and ``1`` is fully opaque. Controls how the colour
        composites over a background in :meth:`blend` and in any
        ``rgba``/``hexa`` serialisation.

    Raises
    ------
    ValueError
        If any of ``r``, ``g``, ``b`` is outside ``[0, 255]`` or ``a``
        is outside ``[0, 1]``.

    See Also
    --------
    matplotlib.colors.to_rgba : Parallel matplotlib parsing helper.
    plotly.colors : Plotly palette and colourscale primitives.
    hex_to_rgba : Functional hex-to-rgba string conversion.

    Examples
    --------
    >>> Colour.parse("rgba(255, 0, 0, 0.5)").to_str()
    'rgba(255, 0, 0, 0.5)'
    >>> Colour(r=0, g=128, b=255).to_str(method="hex")
    '#0080ff'
    """

    r: float
    g: float
    b: float
    a: float = 1.0

    @readonlyclassonlyproperty
    def css_map(
        self,
    ) -> dict[str, str]:
        """
        Expose the hex-to-CSS-name lookup used for named-colour serialisation.

        The mapping is derived once from :data:`PIL.ImageColor.colormap`
        by inverting it so that ``to_str(method="css")`` can resolve a
        canonical CSS name for a given hex value. The inversion keeps
        only entries whose value is a string, discarding any numeric
        tuple aliases that PIL ships alongside the CSS names.

        Returns
        -------
            Hex strings in the form ``"#rrggbb"`` mapped to their CSS
            name such as ``"red"``. Only entries whose underlying value
            is a string (i.e. a real hex colour) are included.

        See Also
        --------
        matplotlib.colors.CSS4_COLORS : Comparable named-colour mapping.
        PIL.ImageColor.colormap : Source of the inverted mapping.
        Colour.to_str : Consumer of the lookup in ``method="css"`` mode.

        Examples
        --------
        >>> "#ff0000" in Colour.css_map
        True
        """
        return reverse_colourmap

    def __post_init__(
        self,
    ) -> None:
        """
        Validate channel ranges immediately after dataclass construction.

        Runs automatically as part of the dataclass-generated
        ``__init__`` and ensures that no instance can be created with
        out-of-range values that would silently produce invalid
        downstream colour strings. Keeping the check at construction
        time means later conversions can assume well-formed 8-bit
        channel values and a normalised alpha.

        Raises
        ------
        ValueError
            If ``r``, ``g`` or ``b`` lies outside ``[0, 255]``, or if
            ``a`` lies outside ``[0, 1]``.

        See Also
        --------
        matplotlib.colors.to_rgba : Alternative validation pathway.
        Colour : Class on which this hook runs.
        Colour.set_opacity : Runs the alpha check after construction.

        Examples
        --------
        >>> Colour(r=10, g=20, b=30)  # triggers post-init validation
        Colour(r=10, g=20, b=30, a=1.0)
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
        """
        Round each channel in place to the nearest integer.

        Useful after arithmetic operations such as :meth:`blend` that
        can produce fractional channel values which are not meaningful
        for 8-bit hex serialisation. The method mutates the instance
        and returns ``self`` so callers can chain it with builders such
        as :meth:`set_opacity` or conversions like :meth:`to_str`.

        Returns
        -------
            The same instance (``self``) with ``r``, ``g``, ``b`` and
            ``a`` replaced by their rounded equivalents, enabling
            method chaining.

        See Also
        --------
        Colour.blend : Produces the fractional values this method tidies.
        Colour.set_opacity : Sibling mutator returning ``self``.
        matplotlib.colors.to_hex : Related quantisation pathway.

        Examples
        --------
        >>> Colour(r=128.7, g=64.2, b=32.9).round().values()[:3]
        (129, 64, 33)
        """
        self.r = round(number=self.r)
        self.g = round(number=self.g)
        self.b = round(number=self.b)
        self.a = round(number=self.a)

        return self

    def values(
        self,
    ) -> tuple[float, float, float, float]:
        """
        Expose the four channels as a plain tuple.

        Provides positional access to the channel values for callers
        that want to unpack or iterate over them without touching
        dataclass attributes. Internal conversions such as
        :meth:`to_hsv`, :meth:`to_hls` and :meth:`to_cmyk` rely on this
        method so that any future attribute layout change is shielded
        from downstream code.

        Returns
        -------
            The ``(r, g, b, a)`` quadruple, with ``r``, ``g``, ``b`` in
            ``[0, 255]`` and ``a`` in ``[0, 1]``.

        See Also
        --------
        Colour.to_hsv : Conversion that consumes this tuple.
        Colour.to_cmyk : Conversion that consumes this tuple.
        matplotlib.colors.to_rgba : Comparable tuple-returning helper.

        Examples
        --------
        >>> Colour(r=10, g=20, b=30, a=0.5).values()
        (10, 20, 30, 0.5)
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
        """
        Construct a :class:`Colour` from any common string encoding.

        Delegates the bulk of the parsing to
        :func:`PIL.ImageColor.getrgb` while adding handling for the
        ``rgba(r, g, b, a)`` form with an explicit floating-point alpha
        channel, which PIL does not accept natively. The method splits
        the input on commas, detects four-element CSS functional
        notation, extracts the alpha as a float in ``[0, 1]``, and
        rewrites the remainder into an ``rgb(...)`` payload that PIL
        can decode.

        Parameters
        ----------
        colour
            Colour string to parse. Accepts hex (``"#rrggbb"``),
            functional ``rgb(...)`` / ``rgba(...)``, CSS names such as
            ``"red"`` and any other form supported by
            :func:`PIL.ImageColor.getrgb`. When an ``rgba`` form with a
            four-value comma-separated payload is supplied the fourth
            value is interpreted as the alpha channel in ``[0, 1]``.

        Returns
        -------
            A new instance populated with the parsed channel values.
            The alpha defaults to ``1.0`` when not supplied and is
            promoted to the PIL-returned alpha byte when present.

        See Also
        --------
        matplotlib.colors.to_rgba : Analogous matplotlib parser.
        PIL.ImageColor.getrgb : Underlying PIL decoder.
        Colour.to_str : Inverse serialisation helper.

        Examples
        --------
        >>> Colour.parse("rgba(255, 0, 0, 0.25)").a
        0.25
        >>> Colour.parse("#00ff00").g
        255
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
        """
        Replace the alpha channel in place.

        Mutates the instance so that the same :class:`Colour` object
        can be threaded through builders that want different opacities
        without allocating a new instance each time. The check mirrors
        the validation in :meth:`__post_init__` so that partial updates
        cannot leave the instance in an invalid state.

        Parameters
        ----------
        opacity
            New alpha value on the ``[0, 1]`` scale. Lower values make
            the colour more transparent when composited.

        Returns
        -------
            The same instance with its ``a`` attribute updated, to
            allow chained calls.

        Raises
        ------
        ValueError
            If ``opacity`` is outside ``[0, 1]``.

        See Also
        --------
        Colour.blend : Performs full alpha compositing using ``a``.
        matplotlib.colors.to_rgba : Parallel alpha-aware helper.
        Colour.round : Sibling mutator returning ``self``.

        Examples
        --------
        >>> Colour(r=255, g=0, b=0).set_opacity(0.3).a
        0.3
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
        """
        Build a minimal HTML swatch showing the colour.

        Produces a self-contained ``<div>`` whose background is painted
        using the instance's ``rgba(...)`` serialisation, suitable for
        embedding in Jupyter rich display output. Because the background
        uses the CSS functional form, alpha composites correctly against
        the surrounding document when the swatch is rendered in a
        notebook or web page.

        Parameters
        ----------
        size
            Side length of the square swatch in CSS pixels. The same
            value is applied to both width and height.

        Returns
        -------
            HTML string containing a single inline-styled ``<div>``
            element rendered in the requested colour.

        See Also
        --------
        Colour.show : User-facing display wrapper.
        Colour.__repr_html__ : Rich notebook representation using this.
        matplotlib.colors : Alternative visualisation toolkit.

        Examples
        --------
        >>> "background-color:" in Colour(r=255, g=0, b=0)._html_show()
        True
        """
        return f'<div style="width:{size}px;height:{size}px;background-color:{self.to_str()};"></div>'

    def show(
        self,
    ) -> None:
        """
        Display the colour as a swatch in the active environment.

        Preferentially uses IPython's rich HTML display so the swatch
        renders inline in Jupyter. When IPython is not importable,
        falls back to matplotlib and draws a 1x1 inch axes patch
        coloured with the instance's hex value. The fallback path
        discards alpha because matplotlib's ``set_facecolor`` consumes
        the ``method="hex"`` form which omits the alpha byte.

        See Also
        --------
        Colour._html_show : Underlying HTML swatch builder.
        matplotlib.colors : Fallback rendering toolkit.
        IPython.display.display : Preferred notebook display entry.

        Notes
        -----
        This method has no return value and performs only side
        effects. The fallback rendering discards alpha because
        matplotlib's ``set_facecolor`` is given the ``method="hex"``
        form of the colour.

        Examples
        --------
        >>> from mayutils.objects.colours import Colour
        >>> Colour(r=255, g=0, b=0).show()  # doctest: +SKIP
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
        """
        Serialise the colour to a string in one of several encodings.

        Acts as the primary dispatch point for converting the instance
        to any of the textual colour forms understood by CSS, plotly,
        the HTML ``style`` attribute and similar consumers. Variants
        suffixed with ``?`` emit the alpha component only when it is
        strictly less than one, mirroring common CSS short-hand rules.
        Hex output applies gamma-agnostic truncation to 8-bit channels,
        while HSV and HSL paths reuse :func:`colorsys.rgb_to_hsv` and
        :func:`colorsys.rgb_to_hls` after normalising to ``[0, 1]``.

        Parameters
        ----------
        opacity
            When provided, overrides the instance's alpha channel for
            this call only. Leaves the stored ``a`` untouched. Callers
            use this to render the same colour at multiple opacities
            without mutating the instance.
        method
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
            The serialised colour in the requested encoding.

        Raises
        ------
        ValueError
            If ``method`` is not one of the supported values, if
            ``method="hex3"`` is requested but one or more channels are
            not divisible by ``17``, or if ``method="css"`` is
            requested but the colour has no matching named entry in
            :attr:`css_map`.

        See Also
        --------
        matplotlib.colors.to_hex : Parallel matplotlib serialiser.
        plotly.colors : Plotly string colour formats.
        Colour.parse : Inverse parser for most encodings.

        Examples
        --------
        >>> Colour(r=255, g=0, b=0).to_str(method="hex")
        '#ff0000'
        >>> Colour(r=255, g=0, b=0, a=0.5).to_str(method="hexa")
        '#ff000080'
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
        """
        Return the default string representation using ``rgba(...)`` form.

        Equivalent to calling :meth:`to_str` with its default
        ``method="rgba"`` argument, so ``str(colour)`` always produces
        a valid CSS functional string including the alpha channel.
        This keeps interpolation into templates, logs and f-strings
        stable regardless of whether the instance is later mutated via
        :meth:`set_opacity` or :meth:`round`.

        Returns
        -------
            The ``rgba(r, g, b, a)`` serialisation of the instance.

        See Also
        --------
        Colour.to_str : Full dispatch helper invoked by this method.
        Colour.__repr_html__ : Rich notebook representation counterpart.
        matplotlib.colors.to_rgba : Analogous conversion helper.

        Examples
        --------
        >>> str(Colour(r=10, g=20, b=30, a=1.0))
        'rgba(10, 20, 30, 1.0)'
        """
        return self.to_str()

    def __repr_html__(
        self,
    ) -> str:
        """
        Build a rich HTML representation for notebook environments.

        Combines the visual swatch produced by :meth:`_html_show` with
        the textual form returned by :meth:`to_str` so that both the
        hue and the exact value are visible in Jupyter-style displays.
        This format helps when eyeballing transparent colours whose
        alpha cannot be inferred from the swatch colour alone.

        Returns
        -------
            HTML string containing the swatch ``<div>`` followed by a
            ``<p>`` element holding the default ``rgba(...)`` form.

        See Also
        --------
        Colour._html_show : Produces the swatch markup reused here.
        Colour.show : Imperative display wrapper.
        matplotlib.colors : Alternative rendering pathway.

        Examples
        --------
        >>> "<p>rgba(" in Colour(r=1, g=2, b=3).__repr_html__()
        True
        """
        return self._html_show() + f"<p>{self.to_str()}</p>"

    def to_hsv(
        self,
    ) -> tuple[float, float, float]:
        """
        Convert the colour to the HSV colour model.

        Uses :func:`colorsys.rgb_to_hsv` after normalising the RGB
        channels from ``[0, 255]`` to ``[0, 1]``. The alpha channel is
        not part of the output because HSV is defined on RGB alone.
        Returning hue on the unit interval matches :mod:`colorsys`
        conventions; multiply by ``360`` to obtain a degree reading.

        Returns
        -------
            The ``(h, s, v)`` triple with each component in ``[0, 1]``,
            where ``h`` is the hue angle normalised to a unit interval,
            ``s`` is saturation and ``v`` is value (brightness).

        See Also
        --------
        Colour.to_hls : HLS sibling conversion method.
        colorsys.rgb_to_hsv : Underlying standard-library helper.
        matplotlib.colors.rgb_to_hsv : Analogous numpy-aware helper.

        Examples
        --------
        >>> h, s, v = Colour(r=255, g=0, b=0).to_hsv()
        >>> round(h, 3), round(s, 3), round(v, 3)
        (0.0, 1.0, 1.0)
        """
        return rgb_to_hsv(*[val / 255 for val in self.values()[:3]])

    def to_hls(
        self,
    ) -> tuple[float, float, float]:
        """
        Convert the colour to the HLS colour model.

        Uses :func:`colorsys.rgb_to_hls` after normalising the RGB
        channels from ``[0, 255]`` to ``[0, 1]``. The alpha channel is
        not part of the output because HLS is defined on RGB alone.
        Note the component order is ``(h, l, s)`` to match
        :mod:`colorsys`; swap lightness and saturation when feeding a
        consumer that expects the CSS ``hsl(...)`` ordering.

        Returns
        -------
            The ``(h, l, s)`` triple with each component in ``[0, 1]``,
            where ``h`` is the hue angle normalised to a unit interval,
            ``l`` is lightness and ``s`` is saturation.

        See Also
        --------
        Colour.to_hsv : HSV sibling conversion method.
        colorsys.rgb_to_hls : Underlying standard-library helper.
        matplotlib.colors : Analogous colour-model utilities.

        Examples
        --------
        >>> h, l, s = Colour(r=255, g=0, b=0).to_hls()
        >>> round(h, 3), round(l, 3), round(s, 3)
        (0.0, 0.5, 1.0)
        """
        return rgb_to_hls(*[val / 255 for val in self.values()[:3]])

    def to_cmyk(
        self,
    ) -> tuple[float, float, float, float]:
        """
        Convert the colour to the CMYK colour model.

        Uses the standard subtractive conversion from normalised RGB
        without ICC profile adjustment, which is adequate for screen
        and documentation use. If the computed key is ``1`` (pure
        black) the chromatic components collapse to zero to avoid
        division by zero. Because the transformation skips a real
        colour-profile step, the result should not be relied on for
        print-critical workflows.

        Returns
        -------
            The ``(c, m, y, k)`` quadruple with each component in
            ``[0, 1]``, where ``c``, ``m`` and ``y`` are the cyan,
            magenta and yellow proportions and ``k`` is the key
            (black) proportion.

        See Also
        --------
        Colour.to_hsv : Alternative chromatic representation.
        Colour.to_grayscale : Luminance-based reduction.
        matplotlib.colors : Related colour-space tooling.

        Examples
        --------
        >>> c, m, y, k = Colour(r=0, g=0, b=0).to_cmyk()
        >>> (c, m, y, k)
        (0, 0, 0, 1.0)
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
        """
        Compute the perceptual luminance using BT.601 weights.

        Applies the ITU-R BT.601 coefficients ``(0.2989, 0.5870,
        0.1140)`` to the RGB channels, matching the luma calculation
        used by legacy standard-definition video and many greyscale
        conversion utilities. Because the computation is performed in
        gamma-encoded 8-bit space, it approximates perceptual
        luminance rather than true linear-light luminance.

        Returns
        -------
            The scalar luminance on the ``[0, 255]`` scale. Higher
            values correspond to lighter colours.

        See Also
        --------
        Colour.to_cmyk : Subtractive alternative reduction.
        matplotlib.colors : Related conversion helpers.
        Colour.to_hsv : Perception-ordered chromatic conversion.

        Examples
        --------
        >>> round(Colour(r=255, g=255, b=255).to_grayscale(), 3)
        254.974
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
        """
        Alpha-composite a foreground colour over an opaque background.

        Implements the standard source-over compositing formula
        ``out = fg * a + bg * (1 - a)`` channel-by-channel. Because
        the formula assumes an opaque backdrop, the ``background``
        argument must have alpha equal to one; the resulting colour is
        always fully opaque. Callers typically follow this with
        :meth:`round` to collapse fractional channel values produced by
        the mix into 8-bit integers suitable for hex serialisation.

        Parameters
        ----------
        foreground
            The overlay colour. Its alpha channel controls the mix
            ratio with the background.
        background
            The base colour underneath the overlay. Must be fully
            opaque because the formula does not accumulate alpha.

        Returns
        -------
            A new instance whose RGB channels are the weighted
            combination of ``foreground`` and ``background`` and whose
            alpha is the default ``1.0``.

        Raises
        ------
        ValueError
            If ``background.a`` is not exactly ``1``.

        See Also
        --------
        Colour.round : Post-blend quantisation helper.
        Colour.set_opacity : Produces the alpha value driving the mix.
        matplotlib.colors : Alternative compositing utilities.

        Examples
        --------
        >>> fg = Colour(r=255, g=0, b=0, a=0.5)
        >>> bg = Colour(r=0, g=0, b=255, a=1.0)
        >>> blended = Colour.blend(foreground=fg, background=bg)
        >>> blended.round().values()[:3]
        (128, 0, 128)
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
        """
        Build a ``python-pptx`` ``RGBColor`` from this instance.

        PowerPoint's object model uses the :class:`pptx.dml.color.RGBColor`
        wrapper to represent solid fill colours. This property
        constructs one from the current ``r``, ``g`` and ``b`` values.
        Transparency is not preserved because the PowerPoint wire
        format handles alpha through a separate ``lumOff``/``lumMod``
        mechanism that lies outside the scope of ``RGBColor``.

        Returns
        -------
            Equivalent PowerPoint colour carrying only the RGB
            channels. The alpha component is dropped because
            ``RGBColor`` does not model transparency.

        See Also
        --------
        pptx.dml.color.RGBColor : PowerPoint wrapper consumed here.
        matplotlib.colors : Alternative colour interchange utilities.
        Colour.to_str : Hex-string equivalent for other consumers.

        Examples
        --------
        >>> from pptx.dml.color import RGBColor
        >>> isinstance(Colour(r=255, g=128, b=64).pptx_colour, RGBColor)
        True
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
    """
    Convert a hex colour string into a CSS ``rgba(...)`` string.

    Provides a lightweight conversion that does not require
    constructing a :class:`Colour` instance. Supports both the
    six-digit ``#rrggbb`` form (where the caller supplies alpha via
    ``alpha``) and the eight-digit ``#rrggbbaa`` form (where the alpha
    byte is read from the string and rescaled to ``[0, 1]``). The
    eight-digit path rounds the normalised alpha to two decimal places
    so the emitted CSS string remains short and human-readable.

    Parameters
    ----------
    hex_colour
        Hex colour to convert, with or without a leading ``#``. The
        stripped payload must be exactly six or eight hex characters.
    alpha
        Fallback alpha value used when ``hex_colour`` contains only
        six hex digits. Ignored when the string already carries an
        alpha byte.

    Returns
    -------
        A CSS-compatible ``rgba(r, g, b, a)`` string, with ``r``,
        ``g``, ``b`` as integers and ``a`` as a float.

    Raises
    ------
    ValueError
        If the stripped hex payload is neither six nor eight
        characters long.

    See Also
    --------
    Colour.parse : Full-featured parser returning a :class:`Colour`.
    matplotlib.colors.to_rgba : Parallel matplotlib conversion.
    plotly.colors : Plotly colour string utilities.

    Examples
    --------
    >>> hex_to_rgba("#ff0000", alpha=0.25)
    'rgba(255, 0, 0, 0.25)'
    >>> hex_to_rgba("#ff000080")
    'rgba(255, 0, 0, 0.5)'
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
