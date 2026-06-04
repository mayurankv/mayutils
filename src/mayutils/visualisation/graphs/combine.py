"""
Mosaic rendered figure exports into a single gridded contact-sheet image.

This module composes multi-page figure artefacts produced elsewhere in the
visualisation pipeline into a single raster image arranged on a regular
grid. Individual pages are rasterised with PyMuPDF and assembled with
Pillow, allowing a collection of standalone exports to be presented as a
unified contact sheet suitable for reports and slide decks.

See Also
--------
mayutils.visualisation.graphs.plotly.charts : Sibling helpers that build
    plotly ``Plot`` and ``SubPlot`` figures whose exports are typically
    mosaicked by this module.
mayutils.visualisation.graphs.matplotlib.templates : Sibling matplotlib
    template helpers producing figure artefacts compatible with mosaicking.
plotly.subplots.make_subplots : Alternative route that composes multiple
    plotly traces into one figure without needing pre-rendered PDFs.
matplotlib.figure.Figure : Matplotlib figure whose saved PDFs can be fed
    into :func:`combine_figures` as tile sources.

Examples
--------
>>> import tempfile
>>> from pathlib import Path
>>> import pymupdf
>>> from mayutils.visualisation.graphs.combine import combine_figures
>>> with tempfile.TemporaryDirectory() as _tmp:
...     _tmp_path = Path(_tmp)
...     _a = _tmp_path / "a.pdf"
...     _b = _tmp_path / "b.pdf"
...     for _p in (_a, _b):
...         _doc = pymupdf.open()
...         _ = _doc.new_page(width=72, height=72)
...         _doc.save(_p)
...         _doc.close()
...     _out = _tmp_path / "mosaic.png"
...     combine_figures(_a, _b, title=_out, cols=2, rows=1)
...     _out.exists()
True
"""

from pathlib import Path

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from PIL import Image
    from pymupdf import Document, Pixmap


def combine_figures(
    *files: Path | str,
    title: Path | str,
    cols: int,
    rows: int,
    filetype: str = "pdf",
) -> None:
    """
    Assemble a collection of figure files into one gridded image export.

    The first page of each source document is rasterised and pasted onto a
    white canvas whose dimensions are derived from the pixel size of the
    first rasterised page multiplied by the requested grid shape. Files are
    laid out in row-major order, so the iteration index maps to
    ``(row, col) = divmod(index, cols)``. The composed canvas is written to
    disk through :meth:`PIL.Image.save`, with the output format inferred by
    Pillow from the ``title`` extension. All tiles share the pixel
    dimensions of the first rasterised page, so pages with differing native
    sizes will be placed without rescaling and may not fill their cell
    exactly.

    Parameters
    ----------
    *files
        Ordered filesystem paths of the figures to mosaic. The ordering
        drives the row-major placement on the canvas, and the first entry
        additionally dictates the per-cell pixel dimensions used to size
        the output canvas.
    title
        Destination path (including extension) where the combined image is
        persisted. The extension governs the serialisation format chosen
        by Pillow.
    cols
        Number of columns in the target grid. Together with ``rows`` this
        controls both the canvas width and the placement coordinates of
        each tile.
    rows
        Number of rows in the target grid. Controls the canvas height and,
        together with ``cols``, the capacity of the mosaic.
    filetype
        Source document format. Selects the rasterisation path; only
        ``"pdf"`` is currently wired up, with other values reserved for
        future backends.

    Raises
    ------
    NotImplementedError
        Raised when ``filetype`` is anything other than ``"pdf"``, since
        no alternative rasterisation backend has been implemented.
    ValueError
        Raised when no ``files`` are supplied, since the canvas size is
        derived from the first rasterised page.

    See Also
    --------
    plotly.subplots.make_subplots : Build a plotly figure with an arranged
        grid of subplots sharing a common layout rather than combining
        pre-rendered exports.
    matplotlib.figure.Figure : Matplotlib figure container whose saved
        output files can be fed into this mosaicking routine.
    mayutils.visualisation.graphs.plotly.charts : Sibling helpers that
        produce the individual plotly figures typically exported to PDF
        before being combined here.
    mayutils.visualisation.graphs.plotly.utilities : Sibling utilities for
        styling and exporting plotly figures ahead of mosaicking.

    Notes
    -----
    All tiles share the pixel dimensions of the first rasterised page;
    pages with differing native sizes will be placed without rescaling
    and may therefore not fill their cell exactly.

    Examples
    --------
    Combine four PDF chart exports into a 2x2 contact sheet saved as a
    single PNG image:

    >>> import tempfile
    >>> from pathlib import Path
    >>> import pymupdf
    >>> from mayutils.visualisation.graphs.combine import combine_figures
    >>> with tempfile.TemporaryDirectory() as _tmp:
    ...     _tmp_path = Path(_tmp)
    ...     _files = [_tmp_path / f"chart_{_i}.pdf" for _i in range(4)]
    ...     for _p in _files:
    ...         _doc = pymupdf.open()
    ...         _ = _doc.new_page(width=72, height=72)
    ...         _doc.save(_p)
    ...         _doc.close()
    ...     _out = _tmp_path / "dashboard.png"
    ...     combine_figures(*_files, title=_out, cols=2, rows=2)
    ...     _out.exists()
    True
    """
    if filetype != "pdf":
        msg = "Other conversions are not supported yet"
        raise NotImplementedError(msg)

    if not files:
        msg = "combine_figures requires at least one figure file"
        raise ValueError(msg)

    images: list[Image.Image] = []
    for file in files:
        document = Document(filename=Path(file).expanduser().resolve())
        pix: Pixmap = document[0].get_pixmap()  # pyright: ignore[reportUnknownMemberType]
        img = Image.frombytes(
            mode="RGB",
            size=(  # pyright: ignore[reportUnknownArgumentType]
                pix.width,  # pyright: ignore[reportUnknownMemberType]
                pix.height,  # pyright: ignore[reportUnknownMemberType]
            ),
            data=pix.samples,
        )
        images.append(img)

    img_width, img_height = images[0].size

    final_image = Image.new(
        mode="RGB",
        size=(
            img_width * cols,
            img_height * rows,
        ),
        color="white",
    )

    for idx, img in enumerate(images):
        row, col = divmod(idx, cols)
        final_image.paste(
            im=img,
            box=(
                col * img_width,
                row * img_height,
            ),
        )

    final_image.save(fp=Path(title).expanduser().resolve())
