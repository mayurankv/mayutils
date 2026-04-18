"""Number formatting helpers — SI-style ``prettify`` and English ``ordinal`` suffixing.

Examples
--------
>>> from mayutils.objects.numbers import ordinal, prettify
>>> prettify(1_234_567)
'1.23M'
>>> ordinal(21)
'21st'
"""


def prettify(
    n: float,
    /,
) -> str:
    """Format a number with an SI-style magnitude suffix.

    The number is rounded to three significant figures, scaled down or
    up in multiples of 1000, and suffixed with the appropriate SI
    letter — ``K``/``M``/``B``/``T``… for large values,
    ``m``/``µ``/``n``… for small ones.

    Parameters
    ----------
    num : float
        The numeric value to format. Zero is returned as the literal
        string ``"0"`` with no suffix.

    Returns
    -------
    str
        The compact string representation (e.g. ``"1.23M"``, ``"500µ"``).

    Raises
    ------
    IndexError
        If ``num`` is larger than 10³⁶ or smaller than 10⁻²⁷, the
        magnitude exceeds the available SI-suffix table.

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

    n = float(f"{n:.3g}")
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
                "B",
                "T",
                "Qa",
                "Qi",
                "Sx",
                "Sp",
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

    return "{}{}".format(f"{n:f}".rstrip("0").rstrip("."), suffix)


def ordinal(
    n: int,
    /,
) -> str:
    """Return an integer's English ordinal form.

    Applies the English rules for ordinal suffixes: ``st`` for values
    ending in 1 (except 11), ``nd`` for 2 (except 12), ``rd`` for 3
    (except 13), and ``th`` otherwise.

    Parameters
    ----------
    n : int
        The integer to format. Negative and zero inputs are accepted
        and follow the same last-digit rules.

    Returns
    -------
    str
        The integer followed by its ordinal suffix (e.g. ``"1st"``,
        ``"22nd"``, ``"113th"``).

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
