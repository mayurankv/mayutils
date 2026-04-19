"""Human-readable numeric formatting helpers.

This module provides small, dependency-free routines for turning raw
numeric values into display-friendly strings. :func:`prettify` collapses
a magnitude into a compact SI-style token (``1.23M``, ``500µ``) that is
suitable for chart annotations, table cells, and log messages where the
full floating-point representation would be unwieldy. :func:`ordinal`
attaches the correct English ordinal suffix (``st``, ``nd``, ``rd``,
``th``) to an integer, honouring the irregular behaviour of the teens.

Examples
--------
>>> from mayutils.objects.numbers import ordinal, prettify
>>> prettify(1_234_567)
'1.23M'
>>> prettify(1_234_567, sf=2)
'1.2M'
>>> ordinal(21)
'21st'
"""


def prettify(
    n: float,
    /,
    *,
    sf: int = 3,
    si_units: bool = False,
) -> str:
    """Render a number as a compact magnitude-suffixed string.

    The input is first rounded to ``sf`` significant figures, then
    repeatedly divided (or multiplied) by one thousand until its
    absolute value lies in the canonical ``[1, 1000)`` display band.
    The accumulated magnitude count selects a suffix letter from either
    the large-number table (``K``, ``M``, ``B``/``G``, ``T``…) or the
    small-number table (``m``, ``µ``, ``n``…). Trailing zeros and a
    trailing decimal point are stripped so the result stays terse.

    Parameters
    ----------
    n : float
        Positional-only numeric value to render. The sign is preserved
        in the output, and zero short-circuits to the literal ``"0"``
        with no suffix applied.
    sf : int, optional
        Number of significant figures retained before scaling. Larger
        values expose more precision in the mantissa at the cost of a
        longer string; defaults to ``3``.
    si_units : bool, optional
        When ``True``, the large-magnitude suffixes follow strict SI
        conventions (``G``, ``P``, ``E``, ``Z``, ``Y``). When ``False``
        (the default), colloquial finance-style suffixes are emitted
        instead (``B``, ``Qa``, ``Qi``, ``Sx``, ``Sp``).

    Returns
    -------
    str
        The compact rendering of ``n``, consisting of the scaled
        mantissa immediately followed by the selected magnitude suffix
        (empty for values already in ``[1, 1000)``).

    Raises
    ------
    IndexError
        Raised when the absolute value of ``n`` is large enough (beyond
        roughly ``10**36``) or small enough (below roughly ``10**-27``)
        that no suffix entry exists in the lookup table.

    Examples
    --------
    >>> prettify(0)
    '0'
    >>> prettify(1_500)
    '1.5K'
    >>> prettify(2_500_000)
    '2.5M'
    >>> prettify(0.0001)
    '100µ'
    """
    _pos_magnitude = 1e3
    _neg_magnitude = 1e-3

    if n == 0:
        return "0"

    n = float(f"{n:.{sf}g}")
    pos_magnitude = 0
    neg_magnitude = 0

    while abs(n) >= _pos_magnitude:
        pos_magnitude += 1
        n /= _pos_magnitude

    while abs(n) <= _neg_magnitude:
        neg_magnitude += 1
        n /= _neg_magnitude

    try:
        if pos_magnitude > 0:
            suffix = [
                "",
                "K",
                "M",
                "G" if si_units else "B",
                "T",
                "P" if si_units else "Qa",
                "E" if si_units else "Qi",
                "Z" if si_units else "Sx",
                "Y" if si_units else "Sp",
                "Oc",
                "No",
                "Dc",
            ][pos_magnitude]
        elif neg_magnitude > 0:
            suffix = [
                "",
                "m",
                "µ",
                "n",
                "p",
                "f",
                "a",
                "z",
                "y",
            ][neg_magnitude]
        else:
            suffix = ""

    except IndexError as err:
        raise err from IndexError("Number magnitude exceeds SI suffix table.")

    return f"{f'{n:f}'.rstrip('0').rstrip('.')}{suffix}"


def ordinal(
    n: int,
    /,
) -> str:
    """Attach the English ordinal suffix to an integer.

    Selects the suffix from the standard English scheme: ``st`` for
    numbers ending in 1, ``nd`` for 2, ``rd`` for 3, and ``th``
    otherwise. The tens digit is inspected to override the first three
    cases in the irregular ``11``, ``12``, ``13`` range so that they
    correctly resolve to ``th``.

    Parameters
    ----------
    n : int
        Positional-only integer whose decimal representation is to be
        suffixed. Negative and zero values are accepted; the suffix is
        chosen from the final two digits of ``n`` using the same rules
        as for positive inputs.

    Returns
    -------
    str
        The decimal form of ``n`` concatenated with the two-character
        ordinal suffix appropriate for its final digits.

    Notes
    -----
    Implemented as a single indexing expression against the packed
    lookup string ``"tsnrhtdd"``; the index computation folds in the
    teens exception so no explicit branching is required.

    Examples
    --------
    >>> ordinal(1)
    '1st'
    >>> ordinal(12)
    '12th'
    >>> ordinal(23)
    '23rd'
    >>> ordinal(101)
    '101st'
    """
    return f"{n}{'tsnrhtdd'[(n // 10 % 10 != 1) * (n % 10 < 4) * n % 10 :: 4]}"  # noqa: PLR2004
