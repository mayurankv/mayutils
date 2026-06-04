r"""
Provide LaTeX document (``.tex``) authoring helpers.

Serve as the entry point for wrappers around a LaTeX toolchain (for
example ``pylatex`` or a direct ``latex``/``xelatex``/``lualatex``
subprocess driver) that offer an ergonomic façade for building
``.tex`` sources, managing preamble and package imports, switching
between math and text mode, and escaping special characters such as
``%``, ``&``, ``#``, ``_``, ``$`` and ``\\`` when interpolating
arbitrary Python strings into LaTeX payloads. The module mirrors the
style of :mod:`mayutils.interfaces.filetypes.pptx` and
:mod:`mayutils.interfaces.filetypes.docx` so that downstream code can
switch between PowerPoint, Word and LaTeX outputs with minimal churn.

See Also
--------
mayutils.interfaces.filetypes.pptx :
    Sibling helper for PowerPoint (``.pptx``) authoring.
mayutils.interfaces.filetypes.docx :
    Sibling helper for Word (``.docx``) authoring.
mayutils.interfaces.filetypes.xlsx :
    Sibling helper for Excel (``.xlsx``) workbook authoring.

Examples
--------
Build a minimal LaTeX source string and verify its structure:

>>> source = "\\documentclass{article}\n\\begin{document}\nHello, $E = mc^2$.\n\\end{document}\n"
>>> "documentclass" in source
True
>>> "\\begin{document}" in source
True

Compile a ``.tex`` file to PDF via a subprocess (requires a TeX
distribution such as TeX Live or MiKTeX):

>>> import subprocess  # doctest: +SKIP
>>> subprocess.run(  # doctest: +SKIP
...     ["xelatex", "-interaction=nonstopmode", "hello.tex"],
...     check=True,
... )
"""

from typing import cast

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from unicodeit.replace import replace  # pyright: ignore[reportUnknownVariableType]


def latex_to_unicode(
    latex: str,
    /,
) -> str:
    r"""
    Convert a LaTeX source string into an equivalent Unicode rendering.

    The helper delegates the actual translation to
    :func:`unicodeit.replace`, which substitutes recognised LaTeX
    commands with their closest Unicode counterparts. Unknown tokens
    pass through untouched, so the function is safe to call on mixed
    prose-and-math strings. The resulting text is well suited for
    printing alongside Rich markup in environments that cannot render
    native TeX output.

    Parameters
    ----------
    latex
        LaTeX source containing commands and symbols to be translated,
        for example ``r"\alpha + \beta"``. Only expressions recognised
        by :func:`unicodeit.replace` are translated.

    Returns
    -------
    str
        A plain string with LaTeX commands replaced by their closest
        Unicode counterparts, suitable for printing in a terminal.

    See Also
    --------
    unicodeit.replace : Underlying LaTeX-to-Unicode substitution.

    Examples
    --------
    >>> result = latex_to_unicode(r"\alpha + \beta")
    >>> isinstance(result, str)
    True
    """
    return cast("str", replace(f=latex))
