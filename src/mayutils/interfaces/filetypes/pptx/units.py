"""
Provide EMU-based length primitives shared across the ``pptx`` helpers.

This module centralises PowerPoint unit-conversion logic so that both the
high-level presentation façade and the sibling markdown renderer can depend
on the same :class:`Length` subclass without creating a circular import.
PowerPoint internally represents every spatial measurement in English Metric
Units (EMU), where one inch equals ``914400`` EMU, one centimetre equals
``360000`` EMU, and one typographic point equals ``12700`` EMU. The helpers
below accept fractional user-facing units and coerce them into the integer
EMU lattice expected by :class:`pptx.util.Length`.

See Also
--------
pptx.util.Emu : EMU-denominated :class:`~pptx.util.Length` constructor.
pptx.util.Inches : Inch-denominated :class:`~pptx.util.Length` constructor.
pptx.util.Cm : Centimetre-denominated :class:`~pptx.util.Length` constructor.
pptx.util.Mm : Millimetre-denominated :class:`~pptx.util.Length` constructor.
pptx.util.Pt : Point-denominated :class:`~pptx.util.Length` constructor.
mayutils.interfaces.filetypes.pptx.markdown : Markdown-to-slide renderer
    that consumes this :class:`Length` subclass for geometry.

Examples
--------
>>> from mayutils.interfaces.filetypes.pptx.units import Length
>>> Length.from_inches(1).emu
914400
>>> Length.from_cms(2.54).emu
914400
"""

from __future__ import annotations

from mayutils.core.extras import may_require_extras

with may_require_extras():
    import numpy as np
    from pptx.util import Length as BaseLength


class Length(BaseLength):
    """
    Represent a PowerPoint length in English Metric Units (EMU).

    Extends :class:`pptx.util.Length` with a :meth:`from_float` constructor
    that tolerates fractional EMU inputs produced by intermediate arithmetic
    (for example, half-slide offsets or proportional layout calculations) by
    flooring to the nearest integer EMU before delegating to the base class.
    A trio of friendly ``from_inches`` / ``from_cms`` / ``from_pts``
    shortcuts wraps the EMU conversion factors inherited from
    :class:`pptx.util.Length`, mirroring the behaviour of
    :class:`pptx.util.Inches`, :class:`pptx.util.Cm`, and :class:`pptx.util.Pt`
    while accepting fractional arguments without explicit rounding.

    See Also
    --------
    pptx.util.Length : Base integer-EMU length class.
    pptx.util.Emu : EMU-denominated :class:`~pptx.util.Length` constructor.
    pptx.util.Inches : Inch-denominated :class:`~pptx.util.Length` constructor.
    pptx.util.Cm : Centimetre-denominated :class:`~pptx.util.Length` constructor.
    pptx.util.Mm : Millimetre-denominated :class:`~pptx.util.Length` constructor.
    pptx.util.Pt : Point-denominated :class:`~pptx.util.Length` constructor.

    Examples
    --------
    >>> from mayutils.interfaces.filetypes.pptx.units import Length
    >>> half_inch = Length.from_inches(0.5)
    >>> half_inch.emu
    457200
    >>> Length.from_float(half_inch.emu / 2).inches
    0.25
    """

    @classmethod
    def from_float(
        cls,
        value: float,
        /,
    ) -> Length:
        """
        Construct a :class:`Length` from a possibly fractional EMU value.

        The base :class:`pptx.util.Length` constructor requires an integer
        EMU count, but layout arithmetic (for example ``0.5 * slide_width``
        when centring a shape) frequently yields a floating-point result.
        This helper delegates to :func:`numpy.floor` to clamp the value to
        the nearest integer EMU below the supplied amount before handing it
        off to the base constructor, keeping callers free of defensive
        rounding boilerplate while preserving deterministic truncation
        semantics that match PowerPoint's own sub-EMU behaviour.

        Parameters
        ----------
        value
            Raw length in English Metric Units. Fractional values are
            accepted and floored; negative inputs are passed through
            unchanged and will raise inside :class:`pptx.util.Length` if
            the base class rejects them.

        Returns
        -------
            A new :class:`Length` instance whose EMU count equals
            ``floor(value)``.

        See Also
        --------
        pptx.util.Emu : EMU-denominated :class:`~pptx.util.Length` constructor.
        pptx.util.Length : Base integer-EMU length class.
        Length.from_inches : Build a length from fractional inches.
        Length.from_cms : Build a length from fractional centimetres.
        Length.from_pts : Build a length from fractional points.

        Examples
        --------
        >>> from mayutils.interfaces.filetypes.pptx.units import Length
        >>> Length.from_float(914400.0).inches
        1.0
        >>> Length.from_float(914400.9).emu
        914400
        """
        return cls(emu=np.floor(value))

    @classmethod
    def from_inches(
        cls,
        inches: float,
        /,
    ) -> Length:
        """
        Construct a :class:`Length` from a fractional inch value.

        Multiplies the supplied inch measurement by the ``_EMUS_PER_INCH``
        constant inherited from :class:`pptx.util.Length` (``914400`` EMU
        per inch, the canonical Office Open XML conversion factor) and
        delegates to :meth:`from_float` so that fractional inputs are
        floored rather than rejected. The inch path is the most common
        choice for US-locale slide templates (standard 13.333x7.5 inch
        widescreen and 10x7.5 inch 4:3 decks) and assumes the nominal
        PowerPoint DPI of ``72`` points per inch when interoperating with
        point-denominated typography.

        Parameters
        ----------
        inches
            Length in inches to convert; fractional values are accepted
            and floored toward negative infinity after multiplication.

        Returns
        -------
            Equivalent length in EMU obtained as
            ``floor(inches * 914400)``.

        See Also
        --------
        pptx.util.Inches : Inch-denominated :class:`~pptx.util.Length` constructor.
        pptx.util.Emu : EMU-denominated :class:`~pptx.util.Length` constructor.
        Length.from_float : Underlying fractional-EMU constructor.
        Length.from_cms : Build a length from fractional centimetres.
        Length.from_pts : Build a length from fractional points.

        Examples
        --------
        >>> from mayutils.interfaces.filetypes.pptx.units import Length
        >>> Length.from_inches(1).emu
        914400
        >>> import numpy as np
        >>> bool(np.isclose(Length.from_inches(13.333).inches, 13.333))
        True
        """
        return Length.from_float(inches * cls._EMUS_PER_INCH)

    @classmethod
    def from_cms(
        cls,
        cms: float,
        /,
    ) -> Length:
        """
        Construct a :class:`Length` from a fractional centimetre value.

        Multiplies the supplied centimetre measurement by the
        ``_EMUS_PER_CM`` constant inherited from :class:`pptx.util.Length`
        (``360000`` EMU per centimetre) and delegates to :meth:`from_float`
        to floor the product into the integer EMU lattice. The centimetre
        path is the natural choice for metric-locale slide templates (for
        example the European A4-derived 25.4x19.05 cm 4:3 deck) and pairs
        cleanly with :class:`pptx.util.Mm` when expressing sub-centimetre
        spacing in millimetres.

        Parameters
        ----------
        cms
            Length in centimetres to convert; fractional values are
            accepted and floored toward negative infinity after
            multiplication.

        Returns
        -------
            Equivalent length in EMU obtained as
            ``floor(cms * 360000)``.

        See Also
        --------
        pptx.util.Cm : Centimetre-denominated :class:`~pptx.util.Length` constructor.
        pptx.util.Mm : Millimetre-denominated :class:`~pptx.util.Length` constructor.
        pptx.util.Emu : EMU-denominated :class:`~pptx.util.Length` constructor.
        Length.from_float : Underlying fractional-EMU constructor.
        Length.from_inches : Build a length from fractional inches.
        Length.from_pts : Build a length from fractional points.

        Examples
        --------
        >>> from mayutils.interfaces.filetypes.pptx.units import Length
        >>> Length.from_cms(2.54).emu
        914400
        >>> Length.from_cms(1).cm
        1.0
        """
        return Length.from_float(cms * cls._EMUS_PER_CM)

    @classmethod
    def from_pts(
        cls,
        pts: float,
        /,
    ) -> Length:
        """
        Construct a :class:`Length` from a fractional typographic-point value.

        Multiplies the supplied point measurement by the ``_EMUS_PER_PT``
        constant inherited from :class:`pptx.util.Length` (``12700`` EMU
        per point, equivalent to the standard ``72`` points per inch DPI
        assumption shared by PowerPoint and PDF) and delegates to
        :meth:`from_float` so fractional point sizes survive intact until
        the final floor. The point path is the go-to unit for typography,
        font metrics, and thin-rule strokes where inch or centimetre
        granularity would be too coarse.

        Parameters
        ----------
        pts
            Length in typographic points to convert; fractional values
            are accepted and truncated toward zero EMU after
            multiplication.

        Returns
        -------
            Equivalent length in EMU obtained as
            ``floor(pts * 12700)``.

        See Also
        --------
        pptx.util.Pt : Point-denominated :class:`~pptx.util.Length` constructor.
        pptx.util.Emu : EMU-denominated :class:`~pptx.util.Length` constructor.
        Length.from_float : Underlying fractional-EMU constructor.
        Length.from_inches : Build a length from fractional inches.
        Length.from_cms : Build a length from fractional centimetres.

        Examples
        --------
        >>> from mayutils.interfaces.filetypes.pptx.units import Length
        >>> Length.from_pts(72).inches
        1.0
        >>> Length.from_pts(10.5).emu
        133350
        """
        return Length.from_float(pts * cls._EMUS_PER_PT)


__all__ = [
    "Length",
]
