"""EMU-based :class:`Length` subclass shared across the ``pptx`` helpers.

Broken out of :mod:`mayutils.interfaces.filetypes.pptx` so that both
the :class:`~mayutils.interfaces.filetypes.pptx.Presentation` façade
and its sibling :mod:`~mayutils.interfaces.filetypes.pptx.markdown`
module can reach for the same unit-conversion primitives without
triggering a circular import.
"""

from __future__ import annotations

from mayutils.core.extras import may_require_extras

with may_require_extras():
    import numpy as np
    from pptx.util import Length as BaseLength


class Length(BaseLength):
    """Length measured in English Metric Units (EMU) for PowerPoint geometry.

    Extends :class:`pptx.util.Length` with a :meth:`from_float`
    constructor that accepts fractional EMU values — useful for
    arithmetic derived from slide dimensions (e.g. centring or
    proportional offsets) where intermediate results are not exactly
    integral — plus friendly ``from_inches`` / ``from_cms`` /
    ``from_pts`` shortcuts.
    """

    @classmethod
    def from_float(
        cls,
        value: float,
        /,
    ) -> Length:
        """Create a :class:`Length` from a possibly fractional EMU value.

        Parameters
        ----------
        value : float
            Raw length in English Metric Units. Fractional values are
            accepted and coerced via the underlying integer-based
            :class:`Length` constructor, allowing expressions such as
            ``0.5 * slide_width`` to be passed without an explicit
            round.

        Returns
        -------
        Self
            A new :class:`Length` instance representing ``value`` EMU.
        """
        return cls(emu=np.floor(value))

    @classmethod
    def from_inches(
        cls,
        inches: float,
        /,
    ) -> Length:
        """Create a :class:`Length` from an inch-denominated value.

        Parameters
        ----------
        inches : float
            Fractional inches to convert.

        Returns
        -------
        Length
            Equivalent length in EMU.
        """
        return Length.from_float(inches * cls._EMUS_PER_INCH)

    @classmethod
    def from_cms(
        cls,
        cms: float,
        /,
    ) -> Length:
        """Create a :class:`Length` from a centimetre-denominated value.

        Parameters
        ----------
        cms : float
            Fractional centimetres to convert.

        Returns
        -------
        Length
            Equivalent length in EMU.
        """
        return Length.from_float(cms * cls._EMUS_PER_CM)

    @classmethod
    def from_pts(
        cls,
        pts: float,
        /,
    ) -> Length:
        """Create a :class:`Length` from a point-denominated value.

        Parameters
        ----------
        pts : float
            Fractional typographic points to convert.

        Returns
        -------
        Length
            Equivalent length in EMU.
        """
        return Length.from_float(pts * cls._EMUS_PER_PT)


__all__ = [
    "Length",
]
