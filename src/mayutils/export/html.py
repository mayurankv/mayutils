"""HTML rendering and screenshotting helpers.

This module provides thin wrappers around :mod:`markdown` for converting
Markdown source into HTML, :mod:`html2image` for rasterising arbitrary
HTML fragments into image files via a headless browser, and a small
inline-style helper for producing pill-style badge elements. A
module-level :class:`html2image.Html2Image` instance and logger are
created on import so that callers can invoke the helpers without
managing browser state themselves.
"""

import time
from pathlib import Path

from mayutils.core.extras import may_require_extras
from mayutils.environment.logging import Logger

with may_require_extras():
    from html2image import Html2Image
    from markdown import markdown

H2I = Html2Image()
logger = Logger.spawn()


def markdown_to_html(
    text: str,
    /,
) -> str:
    r"""Render a Markdown document to HTML while preserving newlines.

    Delegates to :func:`markdown.markdown` and then rewrites any
    residual newline characters to ``<br>`` tags, so that soft line
    breaks in the Markdown source remain visually present in the
    rendered HTML output rather than being collapsed by the HTML
    whitespace-normalisation rules.

    Parameters
    ----------
    text : str
        Markdown source document to be rendered. Any Markdown construct
        supported by the standard :mod:`markdown` package is accepted;
        embedded newlines are promoted to explicit ``<br>`` tags in the
        returned HTML.

    Returns
    -------
    str
        The HTML representation of ``text`` with literal ``\n``
        characters replaced by ``<br>`` tags, ready to be embedded in
        an HTML document or passed to :func:`html_to_image`.
    """
    return markdown(
        text=text,
    ).replace(
        "\n",
        "<br>",
    )


def html_to_image(
    html: str,
    /,
    *,
    path: Path | str,
    css: str | None = None,
    size: tuple[int, int] | None = None,
    sleep_time: int = 1,
) -> Path:
    """Rasterise an HTML fragment to a static image file on disk.

    Drives a headless browser through the module-level
    :class:`html2image.Html2Image` instance to render ``html`` (with an
    optional ``css`` stylesheet and viewport ``size``), then relocates
    the browser's output file to ``path``. Because the screenshot is
    written asynchronously by the browser, the function polls the
    filesystem on a ``sleep_time`` cadence until the target file
    appears before returning.

    Parameters
    ----------
    html : str
        Complete HTML source to render. Anything that is valid inside
        the ``<body>`` of a minimal document is acceptable; the library
        wraps the fragment automatically.
    path : Path | str
        Final destination for the rendered image. The directory must
        already exist and be writable; the filename extension
        determines the output format recognised by
        :class:`html2image.Html2Image` (for example ``.png``).
    css : str | None, default None
        Inline CSS stylesheet applied alongside the HTML. When
        ``None`` the empty string is supplied so that no additional
        styling is injected beyond the HTML's own ``<style>`` blocks.
    size : tuple[int, int] | None, default None
        Virtual viewport dimensions ``(width, height)`` in pixels used
        by the headless browser. When ``None`` the underlying
        :class:`html2image.Html2Image` default is used.
    sleep_time : int, default 1
        Number of seconds to wait between filesystem polls while
        waiting for the browser to finish writing the output file. A
        short fixed ``0.5`` second settle is always performed first
        before polling begins.

    Returns
    -------
    Path
        The resolved :class:`pathlib.Path` at which the rendered image
        now lives. This is the same logical location as the input
        ``path`` but normalised to a :class:`~pathlib.Path` instance.

    Notes
    -----
    :class:`html2image.Html2Image` writes screenshots to the current
    working directory using only the filename component of
    ``save_as``. This function relies on that behaviour by first
    taking a screenshot under ``path.name`` and then moving it to the
    full ``path`` via :meth:`pathlib.Path.replace`.
    """
    path = Path(path)

    kwargs = {}

    if size is not None:
        kwargs["size"] = size

    H2I.screenshot(  # pyright: ignore[reportUnknownMemberType]
        html_str=html,
        css_str=css or "",
        save_as=path.name,
        **kwargs,
    )

    time.sleep(0.5)
    while not path.exists():
        logger.debug(f"Waiting {sleep_time} second for {path} to be created...")
        time.sleep(sleep_time)

    Path(path.name).replace(target=path)

    return path


def html_pill(
    text: str,
    /,
    *,
    background_colour: str,
    text_colour: str = "black",
    bold: bool = True,
    padding: tuple[float, float] = (0.2, 0.4),
    relative_font_size: float = 0.9,
    rounding: float = 5.625,
) -> str:
    """Build an inline HTML ``<span>`` styled as a rounded pill badge.

    Assembles an inline-block span whose CSS declarations produce a
    compact, rounded-corner badge suitable for embedding next to
    tabular or narrative content. All sizing parameters are expressed
    in ``em`` units so that the pill scales with the surrounding
    typography.

    Parameters
    ----------
    text : str
        Literal text placed inside the pill. The value is not escaped,
        so any callers passing user-controlled input must sanitise it
        beforehand if the output is going to be rendered in a trust
        boundary that matters.
    background_colour : str
        Any CSS-valid colour expression (hex string, ``rgb(...)``
        function, or named colour) used as the pill's fill colour.
    text_colour : str, default "black"
        CSS-valid colour used as the ``color`` of the text, controlling
        the foreground contrast against ``background_colour``.
    bold : bool, default True
        When ``True`` the span is styled with ``font-weight: bold``;
        otherwise ``font-weight: normal`` is applied for a lighter
        visual weight.
    padding : tuple[float, float], default (0.2, 0.4)
        Vertical and horizontal padding around the text, in ``em``
        units, expressed as ``(vertical, horizontal)``. Larger values
        yield a chunkier pill.
    relative_font_size : float, default 0.9
        CSS ``font-size`` in ``em`` units, expressed relative to the
        surrounding text. Values below ``1`` shrink the badge below the
        inherited size.
    rounding : float, default 5.625
        CSS ``border-radius`` in ``em`` units. Large values produce the
        fully-rounded pill silhouette; smaller values approach a plain
        rectangle with softened corners.

    Returns
    -------
    str
        A self-contained ``<span>`` element string carrying inline
        ``style`` declarations that apply all of the requested visual
        properties. The span is ``display: inline-block`` so it can be
        composed into paragraphs, table cells, or other flow content
        without disturbing line-height.
    """
    return (
        '<span style="'
        "display: inline-block; "
        f"background-color: {background_colour}; "
        f"color: {text_colour}; "
        f"padding: {padding[0]}em {padding[1]}em; "
        f"border-radius: {rounding}em; "
        f"font-size: {relative_font_size}em; "
        f"font-weight: {'bold' if bold else 'normal'}; "
        '">'
        f"{text}"
        "</span>"
    )
