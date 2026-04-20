"""Inline PDF preview helpers for Jupyter notebooks.

This module exposes a thin wrapper around PyMuPDF (``fitz``) and Pillow
that rasterises each page of a PDF file on disk into an image and emits
it through IPython's display machinery, falling back to the default
system image viewer when IPython is unavailable. It is intended as a
lightweight way to eyeball locally generated PDFs from within a
notebook cell without leaving the kernel.
"""

import io
from pathlib import Path

from mayutils.core.extras import may_require_extras

with may_require_extras():
    import fitz
    from PIL import Image


class Pdf:
    """Inline viewer for a PDF file backed by PyMuPDF rasterisation.

    Instances bind to a single PDF on disk and expose a rendering
    method that opens the document, converts each page into a bitmap
    image, and forwards it to IPython's display system when the class
    is evaluated inside a Jupyter cell. Objects implement
    ``_repr_html_`` so simply returning an instance from a notebook
    cell is enough to preview every page.

    Attributes
    ----------
    pdf_path : pathlib.Path
        Absolute, user-expanded path to the PDF that will be rendered
        on each call to :meth:`show_images`.

    Notes
    -----
    PyMuPDF and Pillow are imported lazily through
    :func:`mayutils.core.extras.may_require_extras`, so importing this
    module does not pull in those dependencies until an instance is
    actually rendered.
    """

    def __init__(
        self,
        pdf_path: str | Path,
        /,
    ) -> None:
        """Bind the viewer to a PDF on disk after verifying it exists.

        Parameters
        ----------
        pdf_path : str or pathlib.Path
            Location of the PDF file to preview. A leading ``~`` is
            expanded to the current user's home directory and the
            result is normalised to an absolute, symlink-resolved
            path so that downstream operations do not depend on the
            process's working directory.

        Raises
        ------
        FileNotFoundError
            Raised when the resolved path does not correspond to an
            existing filesystem entry, preventing later rendering
            calls from failing deep inside PyMuPDF.
        """
        self.pdf_path = Path(pdf_path).expanduser().resolve()

        if not self.pdf_path.exists():
            raise FileNotFoundError(self.pdf_path)

    def show_images(
        self,
        *,
        zoom: float = 2.0,
    ) -> None:
        """Rasterise every page of the bound PDF and display it inline.

        The document is opened with PyMuPDF, each page is converted to
        a PNG pixmap at the requested zoom, wrapped in a
        :class:`PIL.Image.Image`, and forwarded to IPython's
        ``display`` helper. When IPython is not importable the image
        is opened through Pillow's default viewer instead, which
        typically delegates to the operating system's image handler.

        Parameters
        ----------
        zoom : float, default 2.0
            Uniform scaling factor fed into :class:`fitz.Matrix` along
            both axes when producing the page pixmap. Values above
            ``1.0`` increase the output resolution at the cost of
            memory, while values below ``1.0`` produce a downscaled
            preview useful for large documents.

        Returns
        -------
        None
            The method does not return a value; rendered pages are
            emitted as display side effects and the underlying
            document handle is closed before exit.

        Notes
        -----
        The PyMuPDF ``Document`` is explicitly closed after iteration
        to release the underlying file handle, which matters on
        Windows where the file would otherwise remain locked.
        """
        doc = fitz.open(filename=str(self.pdf_path))

        for page_idx in range(doc.page_count):  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
            page = doc.load_page(page_id=page_idx)  # pyright: ignore[reportUnknownMemberType]
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix)  # pyright: ignore[reportUnknownMemberType]
            img = Image.open(io.BytesIO(initial_bytes=pix.tobytes(output="png")))  # pyright: ignore[reportUnknownArgumentType]

            try:
                from IPython.display import display  # pyright: ignore[reportUnknownVariableType] # noqa: PLC0415

                display(img)

            except ImportError:
                img.show()

        doc.close()

    def _repr_html_(
        self,
    ) -> None:
        """Render the bound PDF when the instance is displayed in Jupyter.

        IPython invokes this hook when an object is the final
        expression of a notebook cell. The implementation delegates to
        :meth:`show_images` with the default zoom so that returning a
        :class:`Pdf` instance is enough to preview every page.

        Returns
        -------
        None
            No HTML string is produced; pages are emitted via
            :func:`IPython.display.display` as a side effect, leaving
            the cell output empty from IPython's point of view.
        """
        self.show_images(zoom=2.0)
