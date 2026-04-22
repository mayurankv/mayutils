"""Figure mosaicking utilities for tiling rendered plots into a single image.

This module composes multi-page figure artefacts produced elsewhere in the
visualisation pipeline into a single raster image arranged on a regular
grid. Individual pages are rasterised with PyMuPDF and assembled with
Pillow, allowing a collection of standalone exports to be presented as a
unified contact sheet suitable for reports and slide decks.
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
    """Assemble a collection of figure files into one gridded image export.

    The first page of each source document is rasterised and pasted onto a
    white canvas whose dimensions are derived from the pixel size of the
    first rasterised page multiplied by the requested grid shape. Files are
    laid out in row-major order, so the iteration index maps to ``(row,
    col) = divmod(index, cols)``. The composed canvas is written to disk
    through :meth:`PIL.Image.save`, with the output format inferred by
    Pillow from the ``title`` extension.

    Parameters
    ----------
    files : pathlib.Path | str
        Ordered filesystem paths of the figures to mosaic. The ordering
        drives the row-major placement on the canvas, and the first entry
        additionally dictates the per-cell pixel dimensions used to size
        the output canvas.
    title : pathlib.Path | str
        Destination path (including extension) where the combined image is
        persisted. The extension governs the serialisation format chosen
        by Pillow.
    cols : int
        Number of columns in the target grid. Together with ``rows`` this
        controls both the canvas width and the placement coordinates of
        each tile.
    rows : int
        Number of rows in the target grid. Controls the canvas height and,
        together with ``cols``, the capacity of the mosaic.
    filetype : str, default "pdf"
        Source document format. Selects the rasterisation path; only
        ``"pdf"`` is currently wired up, with other values reserved for
        future backends.

    Returns
    -------
    None
        The function operates through the side effect of writing the
        combined image to ``title`` and does not return a value.

    Raises
    ------
    NotImplementedError
        Raised when ``filetype`` is anything other than ``"pdf"``, since
        no alternative rasterisation backend has been implemented.

    Notes
    -----
    All tiles share the pixel dimensions of the first rasterised page;
    pages with differing native sizes will be placed without rescaling
    and may therefore not fill their cell exactly.
    """
    if filetype != "pdf":
        msg = "Other conversions are not supported yet"
        raise NotImplementedError(msg)

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
