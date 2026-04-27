"""
Expose inline PDF preview helpers for Jupyter notebooks.

Provide a thin wrapper around PyMuPDF (``fitz``) and Pillow that rasterises
each page of a PDF file on disk into an image and emits it through
IPython's display machinery, falling back to the default system image
viewer when IPython is unavailable. The module is intended as a
lightweight way to eyeball locally generated PDFs from within a
notebook cell without leaving the kernel.

See Also
--------
pymupdf.Document : Underlying document handle that :class:`Pdf` opens
    for every render cycle.
PIL.Image.Image : Intermediate image type produced from the rasterised
    page bytes before display.
mayutils.interfaces.filetypes.markdown : Sibling helper module for
    Markdown content shown inline in the same notebook contexts.

Examples
--------
>>> import tempfile
>>> from pathlib import Path
>>> import pymupdf
>>> from mayutils.interfaces.filetypes.pdf import Pdf
>>> with tempfile.TemporaryDirectory() as tmp:
...     p = Path(tmp) / "demo.pdf"
...     doc = pymupdf.open()
...     _ = doc.new_page()
...     doc.save(str(p))
...     doc.close()
...     pdf = Pdf(p)
...     isinstance(pdf, Pdf)
True
"""

import io
from pathlib import Path

from mayutils.core.extras import may_require_extras

with may_require_extras():
    import fitz
    from PIL import Image


class Pdf:
    """
    Render a PDF file inline in a notebook using PyMuPDF and Pillow.

    Bind each instance to a single PDF on disk and expose a rendering
    method that opens the document, converts each page into a bitmap
    image, and forwards it to IPython's display system when the class
    is evaluated inside a Jupyter cell. Objects implement
    ``_repr_html_`` so simply returning an instance from a notebook
    cell is enough to preview every page at the default zoom.

    Parameters
    ----------
    pdf_path
        Location of the PDF file to preview. A leading ``~`` is
        expanded to the current user's home directory and the result
        is normalised to an absolute, symlink-resolved path so that
        downstream operations do not depend on the process's working
        directory.

    Attributes
    ----------
    pdf_path
        Absolute, user-expanded path to the PDF that will be rendered
        on each call to :meth:`show_images`.

    Raises
    ------
    FileNotFoundError
        Raised when the resolved path does not correspond to an
        existing filesystem entry, preventing later rendering calls
        from failing deep inside PyMuPDF.

    See Also
    --------
    pymupdf.Document : Underlying document handle opened by
        :meth:`show_images` to iterate over pages.
    PIL.Image.Image : Intermediate image type produced from each
        rasterised page before display.
    Pdf.show_images : Rasterise and display every page at a chosen
        zoom factor.
    Pdf._repr_html_ : Hook invoked by Jupyter when the instance is the
        last expression of a cell.

    Notes
    -----
    PyMuPDF and Pillow are imported lazily through
    :func:`mayutils.core.extras.may_require_extras`, so importing this
    module does not pull in those dependencies until an instance is
    actually rendered.

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> import pymupdf
    >>> from mayutils.interfaces.filetypes.pdf import Pdf
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     p = Path(tmp) / "demo.pdf"
    ...     doc = pymupdf.open()
    ...     _ = doc.new_page()
    ...     doc.save(str(p))
    ...     doc.close()
    ...     viewer = Pdf(p)
    ...     isinstance(viewer, Pdf)
    True
    """

    def __init__(
        self,
        pdf_path: str | Path,
        /,
    ) -> None:
        """
        Bind the viewer to a PDF on disk after verifying it exists.

        Normalise the supplied path by expanding a leading ``~`` to the
        user's home directory and resolving symlinks to an absolute
        location. Probe the resulting path for existence so that later
        calls to :meth:`show_images` fail fast with a clear error
        rather than deep inside PyMuPDF's C bindings.

        Parameters
        ----------
        pdf_path
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

        See Also
        --------
        pymupdf.Document : Document handle that will later be opened
            on ``self.pdf_path``.
        Pdf.show_images : Sibling method that consumes the stored
            path to render pages.
        pathlib.Path.resolve : Underlying helper used to produce the
            absolute, symlink-free path stored on the instance.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> import pymupdf
        >>> from mayutils.interfaces.filetypes.pdf import Pdf
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "demo.pdf"
        ...     doc = pymupdf.open()
        ...     _ = doc.new_page()
        ...     doc.save(str(p))
        ...     doc.close()
        ...     viewer = Pdf(p)
        ...     viewer.pdf_path.is_absolute()
        True
        """
        self.pdf_path = Path(pdf_path).expanduser().resolve()

        if not self.pdf_path.exists():
            raise FileNotFoundError(self.pdf_path)

    def show_images(
        self,
        *,
        zoom: float = 2.0,
    ) -> None:
        """
        Rasterise every page of the bound PDF and display it inline.

        Open the document with PyMuPDF, iterate over every page in
        order, convert each one to a PNG pixmap at the requested zoom,
        wrap the bytes in a :class:`PIL.Image.Image`, and forward it
        to IPython's ``display`` helper. When IPython is not importable
        the image is opened through Pillow's default viewer instead,
        which typically delegates to the operating system's image
        handler. The document handle is always closed before the
        method returns, releasing the underlying file lock.

        Parameters
        ----------
        zoom
            Uniform scaling factor fed into :class:`fitz.Matrix` along
            both axes when producing the page pixmap. PyMuPDF's default
            rendering is 72 DPI, so a ``zoom`` of ``2.0`` produces a
            144 DPI image and a ``zoom`` of ``4.0`` produces 288 DPI.
            Values above ``1.0`` increase the output resolution at the
            cost of memory, while values below ``1.0`` produce a
            downscaled preview useful for very large documents.

        See Also
        --------
        pymupdf.Document : Document handle opened on
            ``self.pdf_path`` and iterated one page at a time.
        PIL.Image.Image : Container for the rasterised pixmap bytes
            before they are handed to IPython or Pillow's viewer.
        Pdf._repr_html_ : Jupyter hook that calls this method with
            the default zoom.

        Notes
        -----
        The PyMuPDF ``Document`` is explicitly closed after iteration
        to release the underlying file handle, which matters on
        Windows where the file would otherwise remain locked until the
        interpreter exits. The per-page PNG bytes are produced by
        :meth:`fitz.Pixmap.tobytes` with ``output="png"`` so that
        Pillow can decode them without any colour-space conversion.

        Examples
        --------
        >>> import io
        >>> import contextlib
        >>> import tempfile
        >>> from pathlib import Path
        >>> import pymupdf
        >>> from mayutils.interfaces.filetypes.pdf import Pdf
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "demo.pdf"
        ...     doc = pymupdf.open()
        ...     _ = doc.new_page()
        ...     doc.save(str(p))
        ...     doc.close()
        ...     viewer = Pdf(p)
        ...     buf = io.StringIO()
        ...     with contextlib.redirect_stdout(buf):
        ...         result = viewer.show_images(zoom=1.0)
        ...     result is None
        True
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
        """
        Render the bound PDF when the instance is displayed in Jupyter.

        Delegate to :meth:`show_images` with the default zoom of
        ``2.0`` so that returning a :class:`Pdf` instance as the final
        expression of a notebook cell previews every page without any
        further method call. The hook is named ``_repr_html_`` because
        IPython probes for that attribute when deciding how to render
        an object, but no HTML string is actually returned: pages are
        emitted through :func:`IPython.display.display` as a side
        effect instead.

        See Also
        --------
        Pdf.show_images : Sibling method that performs the actual
            rasterisation and display at a configurable zoom.
        pymupdf.Document : Document handle opened by
            :meth:`show_images` on each invocation.
        PIL.Image.Image : Image type that IPython ultimately
            displays for each page.

        Examples
        --------
        >>> import io
        >>> import contextlib
        >>> import tempfile
        >>> from pathlib import Path
        >>> import pymupdf
        >>> from mayutils.interfaces.filetypes.pdf import Pdf
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     p = Path(tmp) / "demo.pdf"
        ...     doc = pymupdf.open()
        ...     _ = doc.new_page()
        ...     doc.save(str(p))
        ...     doc.close()
        ...     viewer = Pdf(p)
        ...     buf = io.StringIO()
        ...     with contextlib.redirect_stdout(buf):
        ...         result = viewer._repr_html_()
        ...     result is None
        True
        """
        self.show_images(zoom=2.0)
