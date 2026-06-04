"""Tests for ``mayutils.interfaces.filetypes.pptx.units``.

These cover the :class:`Length` EMU-conversion helpers: the
fractional-EMU ``from_float`` constructor and the
``from_inches`` / ``from_cms`` / ``from_pts`` shortcuts. Reference
conversion factors are 914400 EMU per inch, 360000 EMU per centimetre,
and 12700 EMU per point.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pptx")

from pptx.util import Length as BaseLength

from mayutils.interfaces.filetypes.pptx.units import Length

EMUS_PER_INCH = 914400
EMUS_PER_CM = 360000
EMUS_PER_PT = 12700


class TestFromFloat:
    """Tests for :meth:`Length.from_float` — floors a fractional EMU value to an integer ``Length``."""

    @pytest.mark.parametrize(
        ("value", "expected_emu"),
        [
            (0, 0),
            (0.0, 0),
            (1.0, 1),
            (914400.0, EMUS_PER_INCH),
            (914400.9, EMUS_PER_INCH),
            (914400.1, EMUS_PER_INCH),
            (1.5, 1),
            (0.999999, 0),
        ],
    )
    def test_floors_toward_negative_infinity(self, value: float, expected_emu: int) -> None:
        """Fractional EMU inputs are floored to the integer EMU below them."""
        assert Length.from_float(value).emu == expected_emu

    @pytest.mark.parametrize(
        ("value", "expected_emu"),
        [
            (-1.0, -1),
            (-914400.0, -EMUS_PER_INCH),
            (-0.5, -1),
            (-0.0001, -1),
            (-1.5, -2),
        ],
    )
    def test_negative_values_floor_away_from_zero(self, value: float, expected_emu: int) -> None:
        """``numpy.floor`` rounds negatives toward negative infinity, not toward zero."""
        assert Length.from_float(value).emu == expected_emu

    def test_returns_length_instance(self) -> None:
        """The result is a :class:`Length` (and therefore a :class:`pptx.util.Length`)."""
        result = Length.from_float(914400.0)
        assert isinstance(result, Length)
        assert isinstance(result, BaseLength)

    def test_emu_is_plain_int(self) -> None:
        """The floored EMU count is an ``int``, not a NumPy float."""
        emu = Length.from_float(914400.9).emu
        assert isinstance(emu, int)
        assert emu == EMUS_PER_INCH

    def test_accepts_numpy_float(self) -> None:
        """A ``numpy.float64`` argument is floored just like a Python float."""
        assert Length.from_float(np.float64(914400.9)).emu == EMUS_PER_INCH

    def test_value_is_positional_only(self) -> None:
        """``value`` cannot be supplied by keyword (positional-only signature)."""
        with pytest.raises(TypeError):
            Length.from_float(value=1.0)  # pyright: ignore[reportCallIssue]  # ty:ignore[positional-only-parameter-as-kwarg]


class TestFromInches:
    """Tests for :meth:`Length.from_inches` — converts fractional inches to EMU (914400 EMU/inch)."""

    @pytest.mark.parametrize(
        ("inches", "expected_emu"),
        [
            (0, 0),
            (1, EMUS_PER_INCH),
            (2, 2 * EMUS_PER_INCH),
            (0.5, 457200),
            (0.25, 228600),
            (-1, -EMUS_PER_INCH),
            (10, 10 * EMUS_PER_INCH),
        ],
    )
    def test_known_conversions(self, inches: float, expected_emu: int) -> None:
        """One inch is 914400 EMU; zero, fractional, and negative inches scale linearly."""
        assert Length.from_inches(inches).emu == expected_emu

    def test_one_inch_reports_one_inch(self) -> None:
        """The ``inches`` property round-trips an exact one-inch length."""
        assert Length.from_inches(1).inches == 1.0

    def test_floors_non_integer_product(self) -> None:
        """A fractional inch whose EMU product is non-integer is floored, not rounded."""
        # 1.0000005 * 914400 == 914400.457... -> floor -> 914400
        assert Length.from_inches(1.0000005).emu == EMUS_PER_INCH

    def test_round_trip_inches(self) -> None:
        """Converting inches to EMU and back is close to the original value."""
        assert np.isclose(Length.from_inches(13.333).inches, 13.333)


class TestFromCms:
    """Tests for :meth:`Length.from_cms` — converts fractional centimetres to EMU (360000 EMU/cm)."""

    @pytest.mark.parametrize(
        ("cms", "expected_emu"),
        [
            (0, 0),
            (1, EMUS_PER_CM),
            (2.54, EMUS_PER_INCH),
            (0.5, 180000),
            (-1, -EMUS_PER_CM),
            (10, 10 * EMUS_PER_CM),
        ],
    )
    def test_known_conversions(self, cms: float, expected_emu: int) -> None:
        """One cm is 360000 EMU; 2.54 cm equals exactly one inch (914400 EMU)."""
        assert Length.from_cms(cms).emu == expected_emu

    def test_one_cm_reports_one_cm(self) -> None:
        """The ``cm`` property round-trips an exact one-centimetre length."""
        assert Length.from_cms(1).cm == 1.0

    def test_floors_non_integer_product(self) -> None:
        """A centimetre value whose EMU product is sub-unit is floored to zero."""
        # 0.0000001 * 360000 == 0.036 -> floor -> 0
        assert Length.from_cms(0.0000001).emu == 0

    def test_round_trip_cms(self) -> None:
        """Converting centimetres to EMU and back is close to the original value."""
        assert np.isclose(Length.from_cms(19.05).cm, 19.05)


class TestFromPts:
    """Tests for :meth:`Length.from_pts` — converts fractional points to EMU (12700 EMU/point)."""

    @pytest.mark.parametrize(
        ("pts", "expected_emu"),
        [
            (0, 0),
            (1, EMUS_PER_PT),
            (72, EMUS_PER_INCH),
            (10.5, 133350),
            (0.5, 6350),
            (-1, -EMUS_PER_PT),
        ],
    )
    def test_known_conversions(self, pts: float, expected_emu: int) -> None:
        """One point is 12700 EMU; 72 points equals exactly one inch (914400 EMU)."""
        assert Length.from_pts(pts).emu == expected_emu

    def test_seventy_two_points_is_one_inch(self) -> None:
        """The ``inches`` property confirms 72 points equals one inch."""
        assert Length.from_pts(72).inches == 1.0

    def test_one_point_reports_one_point(self) -> None:
        """The ``pt`` property round-trips an exact one-point length."""
        assert Length.from_pts(1).pt == 1.0

    def test_floors_non_integer_product(self) -> None:
        """A point value whose EMU product is sub-unit is floored to zero."""
        # 0.00001 * 12700 == 0.127 -> floor -> 0
        assert Length.from_pts(0.00001).emu == 0


class TestCrossUnitEquivalence:
    """Tests that the inch, centimetre, and point paths agree on shared reference lengths."""

    def test_one_inch_three_ways(self) -> None:
        """One inch, 2.54 cm, and 72 pt all resolve to 914400 EMU."""
        assert Length.from_inches(1).emu == Length.from_cms(2.54).emu == Length.from_pts(72).emu == EMUS_PER_INCH

    def test_inches_equals_from_float_of_product(self) -> None:
        """``from_inches`` is exactly ``from_float(inches * 914400)``."""
        assert Length.from_inches(3.7).emu == Length.from_float(3.7 * EMUS_PER_INCH).emu

    def test_pts_equals_from_float_of_product(self) -> None:
        """``from_pts`` is exactly ``from_float(pts * 12700)``."""
        assert Length.from_pts(11.3).emu == Length.from_float(11.3 * EMUS_PER_PT).emu

    def test_cms_equals_from_float_of_product(self) -> None:
        """``from_cms`` is exactly ``from_float(cms * 360000)``."""
        assert Length.from_cms(7.9).emu == Length.from_float(7.9 * EMUS_PER_CM).emu
