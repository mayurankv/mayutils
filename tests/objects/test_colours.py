"""Tests for ``mayutils.objects.colours``."""

from __future__ import annotations

import numpy as np
import pytest

from mayutils.objects.colours import (
    BASE_COLOURSCALE,
    CONTINUOUS_COLORSCALE,
    DIVERGENT_COLOURSCALE,
    MAIN_COLOURSCALE,
    OPACITIES,
    SIMPLE_COLOURS,
    SPECTRUM,
    TRANSPARENT,
    Colour,
    hex_to_rgba,
)


class TestColourConstruction:
    """Tests for :class:`Colour` construction and channel validation."""

    def test_defaults_to_opaque(self) -> None:
        """Omitting ``a`` yields a fully opaque colour."""
        assert Colour(r=10, g=20, b=30).a == 1.0

    def test_stores_channel_values(self) -> None:
        """Channels are stored verbatim on the dataclass."""
        colour = Colour(r=10, g=20, b=30, a=0.5)
        assert (colour.r, colour.g, colour.b, colour.a) == (10, 20, 30, 0.5)

    @pytest.mark.parametrize(
        ("r", "g", "b", "a"),
        [
            (-1, 0, 0, 1.0),
            (0, 256, 0, 1.0),
            (0, 0, 500, 1.0),
            (0, 0, 0, -0.1),
            (0, 0, 0, 1.5),
        ],
    )
    def test_out_of_range_rejected(self, r: float, g: float, b: float, a: float) -> None:
        """Out-of-range channel values raise :class:`ValueError` at construction."""
        with pytest.raises(ValueError, match="out of range"):
            Colour(r=r, g=g, b=b, a=a)


class TestColourParse:
    """Tests for :meth:`Colour.parse` — build a :class:`Colour` from a string."""

    def test_parses_hex(self) -> None:
        """Six-digit hex yields the expected RGB channels and full alpha."""
        colour = Colour.parse("#ff0000")
        assert colour.values() == (255, 0, 0, 1.0)

    def test_parses_rgb(self) -> None:
        """Functional ``rgb(...)`` round-trips without alpha."""
        colour = Colour.parse("rgb(10, 20, 30)")
        assert colour.values() == (10, 20, 30, 1.0)

    def test_parses_rgba_with_explicit_alpha(self) -> None:
        """Functional ``rgba(...)`` reads the fourth value as a float alpha."""
        colour = Colour.parse("rgba(10, 20, 30, 0.25)")
        assert colour.values() == (10, 20, 30, 0.25)

    def test_parses_named_colour(self) -> None:
        """CSS named colours resolve via PIL."""
        colour = Colour.parse("red")
        assert colour.values() == (255, 0, 0, 1.0)


class TestColourValues:
    """Tests for :meth:`Colour.values` and :meth:`Colour.round`."""

    def test_values_tuple(self) -> None:
        """Four-channel tuple is returned in ``(r, g, b, a)`` order."""
        assert Colour(r=1, g=2, b=3, a=0.5).values() == (1, 2, 3, 0.5)

    def test_round_mutates_in_place(self) -> None:
        """``round`` rounds each channel and returns the same instance."""
        colour = Colour(r=1.4, g=2.6, b=3.5, a=0.7)
        returned = colour.round()
        assert returned is colour
        assert colour.r == 1
        assert colour.g == 3  # noqa: PLR2004
        assert colour.b == 4  # noqa: PLR2004


class TestColourSetOpacity:
    """Tests for :meth:`Colour.set_opacity`."""

    def test_updates_alpha(self) -> None:
        """The alpha channel is replaced and the instance is returned for chaining."""
        colour = Colour(r=0, g=0, b=0)
        assert colour.set_opacity(0.25) is colour
        assert colour.a == 0.25  # noqa: PLR2004

    def test_rejects_out_of_range(self) -> None:
        """Alpha outside ``[0, 1]`` raises :class:`ValueError`."""
        with pytest.raises(ValueError, match="out of range"):
            Colour(r=0, g=0, b=0).set_opacity(1.5)


class TestColourToStr:
    """Tests for :meth:`Colour.to_str` — dispatched string encodings."""

    def test_default_is_rgba(self) -> None:
        """Default encoding is functional ``rgba(...)``."""
        assert Colour(r=1, g=2, b=3, a=0.5).to_str() == "rgba(1, 2, 3, 0.5)"

    def test_str_uses_rgba(self) -> None:
        """``str(colour)`` matches the default ``rgba`` serialisation."""
        colour = Colour(r=1, g=2, b=3, a=1.0)
        assert str(colour) == colour.to_str()

    def test_rgb_drops_alpha(self) -> None:
        """``method="rgb"`` omits the alpha channel."""
        assert Colour(r=1, g=2, b=3, a=0.5).to_str(method="rgb") == "rgb(1, 2, 3)"

    def test_hex(self) -> None:
        """``method="hex"`` renders the six-digit zero-padded form."""
        assert Colour(r=255, g=0, b=15).to_str(method="hex") == "#ff000f"

    def test_hexa(self) -> None:
        """``method="hexa"`` appends the alpha byte."""
        assert Colour(r=255, g=0, b=0, a=1.0).to_str(method="hexa") == "#ff0000ff"

    def test_hex3_requires_divisible_channels(self) -> None:
        """``method="hex3"`` succeeds only when every channel is divisible by 17."""
        assert Colour(r=255, g=0, b=17).to_str(method="hex3") == "#f01"

    def test_hex3_rejects_bad_channels(self) -> None:
        """``method="hex3"`` raises when any channel cannot be shortened."""
        with pytest.raises(ValueError, match="hex code"):
            Colour(r=1, g=0, b=0).to_str(method="hex3")

    def test_rgba_question_switches_on_opacity(self) -> None:
        """``rgba?`` drops the alpha channel when the colour is fully opaque."""
        assert Colour(r=0, g=0, b=0, a=1.0).to_str(method="rgba?") == "rgb(0, 0, 0)"
        assert Colour(r=0, g=0, b=0, a=0.5).to_str(method="rgba?") == "rgba(0, 0, 0, 0.5)"

    def test_hexa_question_switches_on_opacity(self) -> None:
        """``hexa?`` drops the alpha byte when the colour is fully opaque."""
        assert Colour(r=255, g=0, b=0, a=1.0).to_str(method="hexa?") == "#ff0000"
        assert Colour(r=255, g=0, b=0, a=0.5).to_str(method="hexa?").startswith("#ff0000")

    def test_opacity_override(self) -> None:
        """The ``opacity`` override applies without mutating the instance."""
        colour = Colour(r=0, g=0, b=0, a=1.0)
        assert colour.to_str(opacity=0.1) == "rgba(0, 0, 0, 0.1)"
        assert colour.a == 1.0

    def test_css_name(self) -> None:
        """``method="css"`` resolves a named CSS colour when one matches."""
        assert Colour(r=255, g=0, b=0).to_str(method="css") == "red"

    def test_css_raises_for_unnamed(self) -> None:
        """Colours without a named CSS equivalent raise :class:`ValueError`."""
        with pytest.raises(ValueError, match="known css"):
            Colour(r=1, g=2, b=3).to_str(method="css")

    def test_grayscale(self) -> None:
        """``method="grayscale"`` returns the BT.601 luminance as a numeric string."""
        assert np.allclose(float(Colour(r=255, g=255, b=255).to_str(method="grayscale")), 255.0, atol=0.1)

    def test_unknown_method_raises(self) -> None:
        """An unknown ``method`` selector raises :class:`ValueError`."""
        with pytest.raises(ValueError, match="Unknown method"):
            Colour(r=0, g=0, b=0).to_str(method="bogus")  # pyright: ignore[reportArgumentType]  # ty:ignore[invalid-argument-type]


class TestColourConversions:
    """Tests for :meth:`to_hsv`, :meth:`to_hls`, :meth:`to_cmyk`, :meth:`to_grayscale`."""

    def test_to_hsv_red(self) -> None:
        """Pure red has hue/value at their extremes and full saturation."""
        h, s, v = Colour(r=255, g=0, b=0).to_hsv()
        assert h == 0
        assert s == 1
        assert v == 1

    def test_to_hls_red(self) -> None:
        """Pure red has hue ``0``, lightness ``0.5`` and saturation ``1``."""
        h, l, s = Colour(r=255, g=0, b=0).to_hls()  # noqa: E741
        assert h == 0
        assert l == 0.5  # noqa: PLR2004
        assert s == 1

    def test_to_cmyk_white(self) -> None:
        """White resolves to ``(0, 0, 0, 0)`` in CMYK."""
        assert Colour(r=255, g=255, b=255).to_cmyk() == (0.0, 0.0, 0.0, 0.0)

    def test_to_cmyk_black(self) -> None:
        """Black collapses the chromatic channels to zero with full key."""
        assert Colour(r=0, g=0, b=0).to_cmyk() == (0, 0, 0, 1)

    def test_to_grayscale(self) -> None:
        """Luminance follows BT.601 coefficients."""
        result = Colour(r=100, g=100, b=100).to_grayscale()
        assert np.allclose(result, 100.0, atol=0.1)


class TestColourBlend:
    """Tests for :meth:`Colour.blend` — alpha-compositing over an opaque backdrop."""

    def test_fully_opaque_foreground(self) -> None:
        """A fully opaque foreground replaces the background entirely."""
        fg = Colour(r=255, g=0, b=0, a=1.0)
        bg = Colour(r=0, g=0, b=0)
        result = Colour.blend(fg, bg)
        assert result.values() == (255.0, 0.0, 0.0, 1.0)

    def test_fully_transparent_foreground(self) -> None:
        """A fully transparent foreground yields the background."""
        fg = Colour(r=255, g=0, b=0, a=0.0)
        bg = Colour(r=0, g=255, b=0)
        result = Colour.blend(fg, bg)
        assert result.values() == (0.0, 255.0, 0.0, 1.0)

    def test_half_opacity_averages_channels(self) -> None:
        """Fifty-percent alpha produces the arithmetic mean of the channels."""
        fg = Colour(r=200, g=0, b=0, a=0.5)
        bg = Colour(r=0, g=100, b=0)
        result = Colour.blend(fg, bg)
        assert result.r == 100.0  # noqa: PLR2004
        assert result.g == 50.0  # noqa: PLR2004

    def test_rejects_translucent_background(self) -> None:
        """A non-opaque background raises :class:`ValueError`."""
        with pytest.raises(ValueError, match="Background"):
            Colour.blend(Colour(r=0, g=0, b=0), Colour(r=0, g=0, b=0, a=0.5))


class TestPptxInterop:
    """Tests for :attr:`Colour.pptx_colour` — build a python-pptx ``RGBColor``."""

    def test_returns_rgbcolor(self) -> None:
        """The property returns a ``python-pptx`` colour carrying the RGB channels."""
        from pptx.dml.color import RGBColor  # noqa: PLC0415

        colour = Colour(r=1, g=2, b=3, a=0.5)
        pptx = colour.pptx_colour
        assert isinstance(pptx, RGBColor)


class TestHexToRgba:
    """Tests for :func:`hex_to_rgba`."""

    def test_six_digit_hex_uses_default_alpha(self) -> None:
        """A six-digit hex string defers to the ``alpha`` argument."""
        assert hex_to_rgba("#ff0000") == "rgba(255, 0, 0, 1.0)"

    def test_six_digit_hex_custom_alpha(self) -> None:
        """The caller-supplied ``alpha`` is embedded in the output."""
        assert hex_to_rgba("ff0000", alpha=0.5) == "rgba(255, 0, 0, 0.5)"

    def test_eight_digit_hex_reads_alpha(self) -> None:
        """An eight-digit hex string rescales the alpha byte to ``[0, 1]``."""
        assert hex_to_rgba("#ff0000ff") == "rgba(255, 0, 0, 1.0)"
        assert hex_to_rgba("#ff000080") == "rgba(255, 0, 0, 0.5)"

    def test_rejects_invalid_length(self) -> None:
        """Strings that are neither six nor eight digits raise :class:`ValueError`."""
        with pytest.raises(ValueError, match="Invalid hex"):
            hex_to_rgba("#fff")


class TestModulePalettes:
    """Tests for module-level palette constants."""

    def test_main_colourscale_is_mapping(self) -> None:
        """:data:`MAIN_COLOURSCALE` maps names to ``#rrggbb`` strings."""
        assert isinstance(MAIN_COLOURSCALE, dict)
        assert all(value.startswith("#") for value in MAIN_COLOURSCALE.values())

    def test_simple_colours_is_subset(self) -> None:
        """:data:`SIMPLE_COLOURS` is a dict with ``#`` prefixed hex values."""
        assert all(value.startswith("#") for value in SIMPLE_COLOURS.values())

    def test_base_colourscale_is_list(self) -> None:
        """:data:`BASE_COLOURSCALE` is the values of :data:`MAIN_COLOURSCALE`."""
        assert list(MAIN_COLOURSCALE.values()) == BASE_COLOURSCALE

    def test_continuous_colourscale_bounds(self) -> None:
        """The continuous scale anchors at ``0.0`` and ``1.0``."""
        assert CONTINUOUS_COLORSCALE[0][0] == 0.0
        assert CONTINUOUS_COLORSCALE[-1][0] == 1.0

    def test_divergent_colourscale_midpoint(self) -> None:
        """The diverging scale passes through ``0.5``."""
        midpoints = [row[0] for row in DIVERGENT_COLOURSCALE]
        assert 0.5 in midpoints  # noqa: PLR2004

    def test_opacities(self) -> None:
        """:data:`OPACITIES` holds an ordered opacity ladder in ``[0, 1]``."""
        assert all(0 <= value <= 1 for value in OPACITIES.values())

    def test_transparent_is_black_with_zero_alpha(self) -> None:
        """:data:`TRANSPARENT` is ``rgba(0, 0, 0, 0)``."""
        assert TRANSPARENT.values() == (0, 0, 0, 0.0)

    def test_spectrum_matches_main_colourscale(self) -> None:
        """:data:`SPECTRUM` has one :class:`Colour` per entry in MAIN_COLOURSCALE."""
        assert set(SPECTRUM.keys()) == set(MAIN_COLOURSCALE.keys())
        assert all(isinstance(colour, Colour) for colour in SPECTRUM.values())
