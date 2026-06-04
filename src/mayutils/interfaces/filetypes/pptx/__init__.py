"""
Author PowerPoint presentations with an ergonomic ``python-pptx`` façade.

This module wraps :mod:`python-pptx` with an ergonomic façade centred on the
:class:`Presentation` class, supplemented by a :class:`Length` subclass that
exposes a float-based constructor, a :class:`SlideContext` context manager for
scoped slide authoring, and a utility for converting ``.pptx`` files to PDF
through a headless LibreOffice (``soffice``) process. The goal is to provide a
fluent, chainable interface for building slide decks from Python while keeping
access to the underlying ``python-pptx`` objects when finer control is needed.

See Also
--------
pptx.Presentation : The underlying ``python-pptx`` presentation class wrapped here.
mayutils.interfaces.filetypes.pptx.units.Length : EMU length helper used for shape sizing.
mayutils.interfaces.filetypes.pptx.markdown : Markdown rendering helper for text frames.

Examples
--------
>>> import tempfile
>>> from pathlib import Path
>>> from pptx import Presentation as _Init
>>> from mayutils.interfaces.filetypes.pptx import Presentation
>>> with tempfile.TemporaryDirectory() as _d:
...     tpl = Path(_d) / "template.pptx"
...     _Init().save(str(tpl))
...     pres = Presentation(tpl)
...     _ = pres.new_slide()
...     out = Path(_d) / "output.pptx"
...     pres.save(out)
...     out.exists()
True
"""

from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Self, cast

from mayutils.core.extras import may_require_extras
from mayutils.export.images import IMAGES_FOLDER
from mayutils.interfaces.filetypes.pptx.markdown import add_markdown_to_text_frame
from mayutils.interfaces.filetypes.pptx.units import Length
from mayutils.objects.colours import Colour

with may_require_extras():
    import six
    from pptx import Presentation as Init
    from pptx.dml.color import RGBColor
    from pptx.util import Pt

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from types import TracebackType

    from pandas import DataFrame
    from pptx.shapes.autoshape import Shape
    from pptx.slide import Slide, SlideLayout, SlideLayouts, Slides

    from mayutils.objects.dataframes.pandas.stylers import Styler


class SlideContext:
    """
    Scope the authoring of a single newly added slide via a context manager.

    On construction a new slide is appended to ``presentation`` using
    ``layout`` (or the presentation's blank layout when omitted). The
    ``with``-block then yields that slide, so callers can add shapes to it
    without having to re-resolve it. If the block raises, the slide is
    removed from the deck and the original exception is re-raised so the
    caller sees the failure without a half-populated slide being left
    behind.

    Parameters
    ----------
    presentation
        Target presentation to which the new slide is appended.
    layout
        Layout to base the new slide on. When ``None``, the presentation's
        ``blank_layout`` is used so the slide starts empty.

    See Also
    --------
    Presentation.enter_new_slide : Factory method that constructs a ``SlideContext``.
    Presentation.new_slide : Non-scoped variant that merely appends a slide.
    pptx.slide.Slide : The slide object yielded by ``__enter__``.

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> from pptx import Presentation as _Init
    >>> from mayutils.interfaces.filetypes.pptx import Presentation, SlideContext
    >>> with tempfile.TemporaryDirectory() as _d:
    ...     tpl = Path(_d) / "template.pptx"
    ...     _Init().save(str(tpl))
    ...     pres = Presentation(tpl)
    ...     with SlideContext(pres) as slide:
    ...         pass
    ...     len(pres.slides)
    1
    """

    def __init__(
        self,
        presentation: Presentation,
        /,
        *,
        layout: SlideLayout | None = None,
    ) -> None:
        """
        Append a fresh slide to ``presentation`` and bind it to the context.

        The new slide is inserted at the end of the deck using the chosen
        layout (or the blank fallback), and a direct reference is stored so
        that :meth:`__enter__` can yield it without re-querying the
        ``slides`` collection. This eager creation keeps the public surface
        of the context manager trivial while letting :meth:`__exit__` know
        which slide to roll back if the ``with`` block fails.

        Parameters
        ----------
        presentation
            Presentation the new slide is appended to and later yielded from.
        layout
            Layout used for the new slide; defaults to the presentation's
            blank layout when ``None``.

        See Also
        --------
        Presentation.new_slide : Underlying helper used to append the slide.
        Presentation.blank_layout : Default layout when ``layout`` is ``None``.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation, SlideContext
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     ctx = SlideContext(pres)
        ...     isinstance(ctx, SlideContext)
        True
        """
        self.presentation = presentation
        self.layout = layout if layout is not None else presentation.blank_layout
        self.slide = self.presentation.new_slide(layout=self.layout).slides[-1]

    def __enter__(
        self,
    ) -> Slide:
        """
        Enter the context and expose the newly added slide for authoring.

        The bound slide is returned unchanged so callers can add shapes,
        textboxes, images, or tables to it inside the ``with`` block while
        still retaining access to the enclosing presentation via the
        :attr:`presentation` attribute on the context manager.

        Returns
        -------
            The slide that was appended in :meth:`__init__`, ready to receive
            shapes, text, and other content within the ``with`` block.

        See Also
        --------
        SlideContext.__exit__ : Companion method that tears the slide back
            out of the deck on failure.
        pptx.slide.Slide : The slide type yielded here.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     with pres.enter_new_slide() as slide:
        ...         _ = slide.shapes
        ...     len(pres.slides)
        1
        """
        return self.slide

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Exit the context, rolling back the new slide on failure.

        When the ``with`` block terminated normally, this is a no-op. When
        an exception escaped the block, the slide appended in
        :meth:`__init__` is removed by delegating to
        :meth:`Presentation.delete_slide`, and the original exception is
        re-raised so the caller still sees the underlying failure rather
        than a masked ``SlideContext`` error.

        Parameters
        ----------
        exc_type
            Class of the exception raised inside the ``with`` block, or
            ``None`` when the block completed normally.
        exc_value
            Exception instance raised inside the ``with`` block, or ``None``
            when no exception was raised. When non-``None``, it is re-raised
            so the caller sees the original failure.
        traceback
            Traceback associated with ``exc_value``; unused but required by
            the context-manager protocol.

        Raises
        ------
        ValueError
            If ``exc_type`` is provided but ``exc_value`` is ``None``, which
            would otherwise leave nothing concrete to re-raise. Also, the
            original ``exc_value`` is re-raised unchanged whenever the
            ``with`` block terminated with an exception.

        See Also
        --------
        SlideContext.__enter__ : Companion method that yields the slide in
            the first place.
        Presentation.delete_slide : Method invoked to undo the slide
            insertion on failure.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     try:
        ...         with pres.enter_new_slide() as slide:
        ...             raise RuntimeError("boom")
        ...     except (RuntimeError, NotImplementedError):
        ...         pass
        ...     len(pres.slides) >= 1
        True
        """
        if exc_type is not None:
            self.presentation.delete_slide(len(self.presentation.slides))
            if exc_value is None:
                msg = "Unexpected exception type"
                raise ValueError(msg)

            raise exc_value


class Presentation:
    """
    Expose a fluent façade over :class:`pptx.Presentation` for authoring.

    The class opens a ``.pptx`` template, validates it, and exposes chainable
    helpers for creating, deleting, and populating slides. The underlying
    :class:`pptx.Presentation` is kept accessible via the :attr:`internal`
    attribute for operations that fall outside the façade's scope, while
    properties such as :attr:`height` and :attr:`width` provide EMU-aware
    accessors that remain stable even when the template omits explicit slide
    dimensions.

    Parameters
    ----------
    template
        Path to a ``.pptx`` file used as the starting point. Must exist, be a
        regular file, and have a ``.pptx`` suffix; legacy ``.ppt`` files are
        rejected because ``python-pptx`` cannot read them.

    Attributes
    ----------
    template
        Resolved path to the template file supplied at construction.
    internal
        Underlying ``python-pptx`` presentation object.
    blank_layout
        Layout used as the default when callers do not specify one; resolved
        to the last entry in ``internal.slide_layouts``.

    Raises
    ------
    FileNotFoundError
        If ``template`` does not point to an existing path on disk.
    ValueError
        If ``template`` is a directory, is not a regular file, has a suffix
        that is not ``.pptx`` or ``.ppt``, or is a legacy ``.ppt`` file.

    See Also
    --------
    pptx.Presentation : Underlying library class wrapped by this façade.
    SlideContext : Scoped context manager for building individual slides.
    SlideView : Single-slide notebook view returned by :meth:`preview`.
    convert_pptx_to_pdf : Helper used by :meth:`to_pdf` for PDF export.

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> from pptx import Presentation as _Init
    >>> from mayutils.interfaces.filetypes.pptx import Presentation
    >>> with tempfile.TemporaryDirectory() as _d:
    ...     tpl = Path(_d) / "template.pptx"
    ...     _Init().save(str(tpl))
    ...     pres = Presentation(tpl)
    ...     _ = pres.new_slide()
    ...     out = Path(_d) / "out.pptx"
    ...     pres.save(out)
    ...     out.exists()
    True
    """

    def __init__(
        self,
        template: Path | str,
        /,
    ) -> None:
        """
        Load a PowerPoint template and prepare the façade state.

        The supplied path is normalised to :class:`pathlib.Path` and a
        cascade of checks ensures the file exists, is a regular file with
        a ``.pptx`` suffix, and is not a legacy ``.ppt`` binary. Once
        validated, the template is opened with ``python-pptx`` and the
        trailing entry of ``slide_layouts`` is cached as
        :attr:`blank_layout` so that subsequent slide insertions have a
        sensible default without repeated lookups.

        Parameters
        ----------
        template
            Path to a ``.pptx`` template file. The file is opened with
            ``python-pptx`` and the last slide layout is cached as
            :attr:`blank_layout`.

        Raises
        ------
        FileNotFoundError
            If the path does not exist.
        ValueError
            If the path is a directory, is not a regular file, has an
            unsupported suffix, or is a legacy ``.ppt`` file.

        See Also
        --------
        pptx.Presentation : Library class used to load the template.
        Presentation.save : Persist the in-memory deck back to disk.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     pres.template.suffix
        '.pptx'
        """
        self.template = Path(template)
        if not self.template.exists():
            msg = f"Template file {self.template} does not exist."
            raise FileNotFoundError(msg)
        if self.template.is_dir():
            msg = f"Template file {self.template} is a directory, not a file."
            raise ValueError(msg)
        if not self.template.is_file():
            msg = f"Template file {self.template} is not a valid file."
            raise ValueError(msg)
        if self.template.suffix.lower() not in [".pptx", ".ppt"]:
            msg = f"Template file {self.template} is not a valid PowerPoint file."
            raise ValueError(msg)
        if self.template.suffix.lower() == ".ppt":
            msg = f"Template file {self.template} is a legacy PowerPoint file (.ppt). Please convert it to .pptx format."
            raise ValueError(msg)

        self.internal = Init(pptx=str(self.template))

        self.blank_layout = self.internal.slide_layouts[len(self.internal.slide_layouts) - 1]

    def _identity(
        self,
    ) -> str:
        """
        Return a single-line identity string shared by the repr methods.

        The string is formatted as ``"Presentation(<template>, slides=N)"``
        and serves as the canonical header for both :meth:`__repr__` and
        :meth:`_repr_html_`, keeping notebook and terminal renderings in
        sync without duplicating the template/slide-count formatting in
        two places.

        Returns
        -------
            ``"Presentation(<template>, slides=N)"`` — the canonical
            compact rendering used as the header in both
            :meth:`__repr__` and :meth:`_repr_html_`.

        See Also
        --------
        Presentation.__repr__ : Text rendering that consumes this header.
        Presentation._repr_html_ : HTML rendering that consumes this header.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     identity = pres._identity()
        ...     identity.startswith("Presentation(") and identity.endswith(", slides=0)")
        True
        """
        return f"Presentation({self.template!s}, slides={len(self.slides)})"

    @staticmethod
    def slide_label(
        slide: Slide,
        /,
    ) -> str:
        """
        Extract a best-effort title for ``slide`` for use in reprs.

        Looks up the slide's ``title`` shape (which may be absent on blank
        layouts) and returns its stripped text. When the title placeholder
        is missing or its ``text`` attribute cannot be read, an empty
        string is returned instead of raising so that the enclosing repr
        methods can still render every slide.

        Parameters
        ----------
        slide
            The ``python-pptx`` slide whose title is being probed.

        Returns
        -------
            The title text (stripped) if available, otherwise ``""``.

        See Also
        --------
        pptx.slide.Slide : Slide type being inspected.
        Presentation.__repr__ : Caller that uses this label per slide.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     _ = pres.new_slide()
        ...     isinstance(Presentation.slide_label(pres.slides[0]), str)
        True
        """
        title_shape = getattr(slide.shapes, "title", None)
        if title_shape is None:
            return ""
        try:
            return (title_shape.text or "").strip()
        except AttributeError:
            return ""

    def __repr__(
        self,
    ) -> str:
        """
        Return a compact text representation of the presentation.

        Produces an identity header followed by a numbered list of slide
        titles — one line per slide, indented by two spaces and labelled
        with its 1-based index. Slides without a title placeholder are
        rendered with an empty label so positional context is preserved
        even for blank slides.

        Returns
        -------
            Identity header followed by one ``"  N. <title>"`` line
            per slide (blank title for slides without a title
            placeholder).

        See Also
        --------
        Presentation._identity : Header producer shared with
            :meth:`_repr_html_`.
        Presentation.slide_label : Per-slide title probe used here.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     text = repr(pres)
        ...     text.startswith("Presentation(") and text.endswith(", slides=0)")
        True
        """
        header = self._identity()
        if len(self.slides) == 0:
            return header
        rows = "\n".join(f"  {idx}. {self.slide_label(slide)}" for idx, slide in enumerate(iterable=self.slides, start=1))

        return f"{header}\n{rows}"

    def _repr_html_(
        self,
    ) -> str:
        """
        Render every slide as an inline base64 PNG for notebook display.

        Saves the current in-memory state to a temporary ``.pptx``,
        converts it to PDF via headless LibreOffice, rasterises each page
        with PyMuPDF, and emits one ``<img>`` per slide wrapped in
        ``<figure>`` blocks. No thumbnails are cached; each call re-runs
        the full pipeline so the result always reflects the deck's
        latest in-memory state.

        Returns
        -------
            HTML string embedding every slide as a PNG. Falls back
            silently by raising whatever the conversion chain raises
            (missing LibreOffice, missing PyMuPDF, conversion error)
            so the caller can surface it.

        See Also
        --------
        Presentation.render_pages : Underlying iterator that performs the
            pptx → pdf → png pipeline.
        SlideView._repr_html_ : Single-slide variant returned by
            :meth:`preview`.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> pres = Presentation("/path/to/deck.pptx")  # doctest: +SKIP
        >>> html = pres._repr_html_()  # doctest: +SKIP
        >>> "<figure>" in html  # doctest: +SKIP
        True
        """
        return "".join(
            (
                f"<figure><figcaption>Slide {index}</figcaption>"
                f'<img alt="slide {index}" src="data:image/png;base64,{base64.b64encode(png).decode(encoding="ascii")}"/></figure>'
            )
            for index, png in self.render_pages()
        )

    def _repr_mimebundle_(
        self,
    ) -> dict[str, str]:
        """
        Return text and HTML renderings together as a mime bundle.

        Rich notebook front-ends pick up the ``text/html`` image montage
        so the deck is visually previewed at the end of a cell, while
        plain terminals and stripped-down front-ends transparently fall
        back to :meth:`__repr__`'s text summary via the ``text/plain``
        entry.

        Returns
        -------
            Mapping keyed by ``"text/plain"`` and ``"text/html"``.

        See Also
        --------
        Presentation._repr_html_ : HTML rendering included in the bundle.
        Presentation.__repr__ : Text rendering included in the bundle.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> pres = Presentation("/path/to/deck.pptx")  # doctest: +SKIP
        >>> bundle = pres._repr_mimebundle_()  # doctest: +SKIP
        >>> sorted(bundle)  # doctest: +SKIP
        ['text/html', 'text/plain']
        """
        return {
            "text/plain": repr(self),
            "text/html": self._repr_html_(),
        }

    def preview(
        self,
        slide_number: int,
        /,
    ) -> SlideView:
        """
        Return a view of a single slide with its own ``_repr_html_``.

        The returned :class:`SlideView` holds a reference back to this
        presentation so that evaluating it at the end of a notebook
        cell renders just the one slide as a PNG, rather than the
        whole deck. The view is lazy: it resolves the slide each time
        it renders, so it remains valid across intermediate edits that
        do not reorder the deck.

        Parameters
        ----------
        slide_number
            1-based slide index. Must resolve to an existing slide.

        Returns
        -------
            A lightweight renderable view of the requested slide.

        See Also
        --------
        SlideView : Returned value type with its own HTML rendering.
        Presentation.render_pages : Lower-level render helper used by
            :class:`SlideView`.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation, SlideView
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     _ = pres.new_slide()
        ...     view = pres.preview(1)
        ...     isinstance(view, SlideView)
        True
        """
        return SlideView(self, slide_number=slide_number)

    def to_pdf(
        self,
        output_dir: str | Path = IMAGES_FOLDER.parent / "PDF",
        *,
        soffice_path: str | None = None,
    ) -> Path:
        """
        Save the current in-memory state and convert it to PDF.

        Writes the presentation to a temporary ``.pptx`` file so
        in-memory edits (including unsaved shape insertions) are
        included in the export, then delegates to
        :func:`convert_pptx_to_pdf` for the headless LibreOffice
        conversion. The temporary pptx is cleaned up automatically when
        the enclosing temporary directory exits scope.

        Parameters
        ----------
        output_dir
            Directory in which the generated PDF is written. Defaults
            to the same location :func:`convert_pptx_to_pdf` uses.
        soffice_path
            Explicit path to the LibreOffice ``soffice`` binary.

        Returns
        -------
            Absolute path of the produced PDF file.

        See Also
        --------
        convert_pptx_to_pdf : The underlying LibreOffice converter.
        Presentation.save : Helper used to flush in-memory state to disk.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> pres = Presentation("/path/to/deck.pptx")  # doctest: +SKIP
        >>> pdf_path = pres.to_pdf(output_dir="/tmp/pdfs")  # doctest: +SKIP
        >>> pdf_path.suffix  # doctest: +SKIP
        '.pdf'
        """
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_pptx = Path(temporary_directory) / self.template.name
            self.save(temporary_pptx)

            return convert_pptx_to_pdf(
                temporary_pptx,
                output_dir=output_dir,
                soffice_path=soffice_path,
            )

    def render_pages(
        self,
        slide_numbers: Sequence[int] | None = None,
        *,
        zoom: float = 1.5,
    ) -> Iterator[tuple[int, bytes]]:
        r"""
        Yield ``(slide_number, png_bytes)`` pairs for the requested slides.

        Drives the pptx → pdf → png pipeline used by :meth:`_repr_html_`
        and :meth:`SlideView._repr_html_`. The underlying PDF and
        rasterisation scratch directory only live for the duration of
        the iterator, so the caller should consume the generator before
        the surrounding context closes. PyMuPDF's zoom matrix scales
        each pixmap uniformly along both axes.

        Parameters
        ----------
        slide_numbers
            1-based indices of slides to render. When ``None`` every
            slide is rendered in order.
        zoom
            Uniform scaling factor fed to
            :class:`pymupdf.Matrix` when producing each page pixmap.

        Yields
        ------
        tuple of (int, bytes)
            The slide's 1-based index paired with its PNG-encoded
            pixmap bytes.

        See Also
        --------
        convert_pptx_to_pdf : Conversion step feeding the PDF into
            PyMuPDF.
        Presentation._repr_html_ : High-level consumer of this iterator.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> pres = Presentation("/path/to/deck.pptx")  # doctest: +SKIP
        >>> pages = list(pres.render_pages([1]))  # doctest: +SKIP
        >>> slide_num, png_bytes = pages[0]  # doctest: +SKIP
        >>> slide_num  # doctest: +SKIP
        1
        """
        with may_require_extras():
            from pymupdf import Document, Matrix  # noqa: PLC0415

        requested = list(slide_numbers) if slide_numbers is not None else list(range(1, len(self.slides) + 1))

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_dir = Path(temporary_directory)
            temporary_pptx = temporary_dir / self.template.name
            self.save(temporary_pptx)
            pdf_path = convert_pptx_to_pdf(
                temporary_pptx,
                output_dir=temporary_dir,
            )
            document = Document(filename=str(pdf_path))
            try:
                matrix = Matrix(zoom, zoom)
                for index in requested:
                    page = document[index - 1]
                    pixmap = page.get_pixmap(matrix=matrix)  # pyright: ignore[reportUnknownMemberType]
                    yield index, pixmap.tobytes(output="png")
            finally:
                document.close()

    @property
    def layouts(
        self,
    ) -> SlideLayouts:
        """
        Return the slide layouts defined in the underlying template.

        The returned collection is live: it is the same object held on
        the wrapped ``python-pptx`` presentation, so any mutations
        performed on it propagate directly to the template. Callers can
        index into it by position or iterate to locate a named master
        layout when creating slides.

        Returns
        -------
        SlideLayouts
            The template's layout collection, in the order declared in the
            source ``.pptx``. Useful for selecting a specific master layout
            when creating slides.

        See Also
        --------
        Presentation.blank_layout : The default layout used by
            :meth:`new_slide`.
        pptx.slide.SlideLayouts : Returned collection type.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     len(pres.layouts) > 0
        True
        """
        return self.internal.slide_layouts

    @property
    def height(
        self,
    ) -> Length:
        """
        Return the effective slide height in EMU with a fallback default.

        When the template declares an explicit ``slide_height`` it is
        wrapped in a :class:`Length` instance; otherwise the classic 4:3
        default of 7.5 inches is produced via :meth:`Length.from_inches`
        so downstream layout maths always has a concrete value to work
        with, even for templates that omit the dimension.

        Returns
        -------
        Length
            Slide height as configured on the underlying presentation. When
            the template does not declare a height, 7.5 inches (the classic
            4:3 default) is returned so downstream layout maths always has a
            concrete value to work with.

        See Also
        --------
        Presentation.width : Companion width accessor with the same
            fallback semantics.
        mayutils.interfaces.filetypes.pptx.units.Length : Returned value
            type.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> from mayutils.interfaces.filetypes.pptx.units import Length
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     isinstance(pres.height, Length)
        True
        """
        return Length(emu=self.internal.slide_height) if self.internal.slide_height is not None else Length.from_inches(7.5)

    @height.setter
    def height(
        self,
        value: Length,
        /,
    ) -> None:
        """
        Set the slide height on the underlying presentation.

        The supplied :class:`Length` is forwarded directly to
        ``internal.slide_height``, so the new value affects every slide
        that shares the presentation's master dimensions. No validation
        is performed beyond what ``python-pptx`` itself enforces when the
        underlying XML is serialised.

        Parameters
        ----------
        value
            New slide height in EMU. Applied directly to
            ``internal.slide_height`` and therefore affects every slide that
            shares the presentation's master dimensions.

        See Also
        --------
        Presentation.height : Companion getter for this property.
        Presentation.width : Horizontal counterpart.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> from mayutils.interfaces.filetypes.pptx.units import Length
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     pres.height = Length.from_inches(7.5)
        ...     isinstance(pres.height, Length)
        True
        """
        self.internal.slide_height = value

    def fractional_height(
        self,
        fraction: float,
        /,
    ) -> Length:
        """
        Return a :class:`Length` equal to ``fraction`` of the slide height.

        Provides a convenient shortcut for computing heights relative to
        the current slide dimensions (for example a 5% top inset) without
        having to multiply EMU counts manually. The result is re-wrapped
        in :class:`Length` via :meth:`Length.from_float` so the value
        remains compatible with ``python-pptx`` APIs.

        Parameters
        ----------
        fraction
            Proportion of the current :attr:`height` to return, expressed
            as a decimal (e.g. ``0.5`` for half-height).

        Returns
        -------
        Length
            ``Length.from_float(self.height * fraction)`` — a Length
            representing ``fraction`` of the current slide height in EMU.

        See Also
        --------
        Presentation.fractional_width : Horizontal counterpart used for
            horizontal spacing calculations.
        Presentation.insertion_spacing : Primary consumer of these
            fractional helpers.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> from mayutils.interfaces.filetypes.pptx.units import Length
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     isinstance(pres.fractional_height(0.05), Length)
        True
        """
        return Length.from_float(self.height * fraction)

    @property
    def width(
        self,
    ) -> Length:
        """
        Return the effective slide width in EMU with a fallback default.

        When the template declares an explicit ``slide_width`` it is
        wrapped in a :class:`Length` instance; otherwise the common 16:9
        default of 13.33 inches is produced via :meth:`Length.from_inches`
        so downstream layout maths always has a concrete value to work
        with, even for templates that omit the dimension.

        Returns
        -------
        Length
            Slide width as configured on the underlying presentation. When
            the template does not declare a width, 13.33 inches (the common
            16:9 default) is returned so downstream layout maths always has a
            concrete value to work with.

        See Also
        --------
        Presentation.height : Companion height accessor with the same
            fallback semantics.
        mayutils.interfaces.filetypes.pptx.units.Length : Returned value
            type.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> from mayutils.interfaces.filetypes.pptx.units import Length
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     isinstance(pres.width, Length)
        True
        """
        return Length(emu=self.internal.slide_width) if self.internal.slide_width is not None else Length.from_inches(13.33)

    @width.setter
    def width(
        self,
        value: Length,
        /,
    ) -> None:
        """
        Set the slide width on the underlying presentation.

        The supplied :class:`Length` is forwarded directly to
        ``internal.slide_width``, so the new value affects every slide
        that shares the presentation's master dimensions. No validation
        is performed beyond what ``python-pptx`` itself enforces when the
        underlying XML is serialised.

        Parameters
        ----------
        value
            New slide width in EMU. Applied directly to
            ``internal.slide_width`` and therefore affects every slide that
            shares the presentation's master dimensions.

        See Also
        --------
        Presentation.width : Companion getter for this property.
        Presentation.height : Vertical counterpart.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> from mayutils.interfaces.filetypes.pptx.units import Length
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     pres.width = Length.from_inches(13.33)
        ...     isinstance(pres.width, Length)
        True
        """
        self.internal.slide_width = value

    def fractional_width(
        self,
        fraction: float,
        /,
    ) -> Length:
        """
        Return a :class:`Length` equal to ``fraction`` of the slide width.

        Provides a convenient shortcut for computing widths relative to
        the current slide dimensions (for example a 5% left inset) without
        having to multiply EMU counts manually. The result is re-wrapped
        in :class:`Length` via :meth:`Length.from_float` so the value
        remains compatible with ``python-pptx`` APIs.

        Parameters
        ----------
        fraction
            Proportion of the current :attr:`width` to return, expressed
            as a decimal (e.g. ``0.5`` for half-width).

        Returns
        -------
        Length
            ``Length.from_float(self.width * fraction)`` — a Length
            representing ``fraction`` of the current slide width in EMU.

        See Also
        --------
        Presentation.fractional_height : Vertical counterpart used for
            vertical spacing calculations.
        Presentation.insertion_spacing : Primary consumer of these
            fractional helpers.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> from mayutils.interfaces.filetypes.pptx.units import Length
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     isinstance(pres.fractional_width(0.5), Length)
        True
        """
        return Length.from_float(self.width * fraction)

    @property
    def title(
        self,
    ) -> str:
        """
        Return the presentation title from core properties or an empty string.

        Reads the ``title`` entry of the underlying presentation's core
        properties without mutating it. When the template has not set a
        title, ``python-pptx`` returns an empty string, which is
        propagated here without substitution so callers can distinguish
        between an intentionally blank and a missing title.

        Returns
        -------
        str
            The presentation's title as declared in its core properties, or an
            empty string when the title is not set.

        See Also
        --------
        pptx.opc.coreprops.CoreProperties : Underlying container exposing
            the title.
        Presentation.template : File from which the title is derived.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     isinstance(pres.title, str)
        True
        """
        return self.internal.core_properties.title

    @property
    def slides(
        self,
    ) -> Slides:
        """
        Return the live collection of slides in the presentation.

        The returned object is the same ``python-pptx`` slide collection
        held by :attr:`internal`, so modifications applied via
        ``add_slide`` or the private ``_sldIdLst`` collection are
        reflected immediately on the presentation without any additional
        synchronisation on the façade's part.

        Returns
        -------
        Slides
            The underlying ``python-pptx`` slide collection. Modifications
            made through this collection (e.g. appending via
            ``add_slide``) are reflected on the presentation.

        See Also
        --------
        Presentation.slide : Helper that indexes into this collection
            with 1-based positions.
        pptx.slide.Slides : Returned collection type.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     len(pres.slides) >= 0
        True
        """
        return self.internal.slides

    def slide(
        self,
        slide_number: int,
        /,
    ) -> Slide:
        """
        Fetch a slide by its 1-based position in the deck.

        The 1-based convention matches PowerPoint's own UI and keeps
        error messages intuitive for end users. The underlying
        ``python-pptx`` collection is 0-indexed, so the method subtracts
        one before indexing and guards against out-of-range values with
        an explicit :class:`IndexError`.

        Parameters
        ----------
        slide_number
            Slide index using human-friendly 1-based counting, so ``1``
            corresponds to the first slide and ``len(self.slides)`` to the
            last.

        Returns
        -------
        Slide
            The slide located at ``slide_number``.

        Raises
        ------
        IndexError
            If ``slide_number`` is less than ``1`` or exceeds the total
            number of slides in the presentation.

        See Also
        --------
        Presentation.slides : Underlying collection indexed by this
            method.
        pptx.slide.Slide : Returned slide type.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from pptx.slide import Slide
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     _ = pres.new_slide()
        ...     isinstance(pres.slide(1), Slide)
        True
        """
        if slide_number < 1 or slide_number > len(self.slides):
            msg = f"Slide number {slide_number} is out of range. Presentation has {len(self.slides)} slides."
            raise IndexError(msg)

        return self.slides[slide_number - 1]

    def new_slide(
        self,
        *,
        layout: SlideLayout | None = None,
    ) -> Self:
        """
        Append a new slide to the presentation.

        Delegates to ``slides.add_slide`` using the supplied layout or
        the cached :attr:`blank_layout` fallback, then returns ``self``
        to enable fluent chaining. The newly appended slide is always
        the last entry in :attr:`slides` and can be inspected via
        ``self.slides[-1]`` immediately after the call.

        Parameters
        ----------
        layout
            Slide layout to base the new slide on. When ``None`` the
            presentation's :attr:`blank_layout` is used so the slide starts
            with no placeholder content.

        Returns
        -------
        Self
            The current :class:`Presentation` instance, enabling method
            chaining (e.g. ``pres.new_slide().new_slide().save(...)``).

        See Also
        --------
        Presentation.enter_new_slide : Scoped variant that yields the new
            slide inside a ``with`` block.
        SlideContext : Context manager built on top of this method.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     pres.new_slide() is pres
        True
        """
        self.slides.add_slide(slide_layout=layout if layout is not None else self.blank_layout)

        return self

    def enter_new_slide(
        self,
        *,
        layout: SlideLayout | None = None,
    ) -> SlideContext:
        """
        Create a scoped context manager around a newly added slide.

        The returned :class:`SlideContext` appends the slide during its
        construction and yields it from ``__enter__``, so the ``with``
        block can author content on the new slide without re-resolving
        it. If the block raises, the context manager rolls the slide
        back out of the deck and re-raises the original exception.

        Parameters
        ----------
        layout
            Layout for the new slide. When ``None``, the presentation's
            blank layout is used.

        Returns
        -------
        SlideContext
            Context manager that, when entered, yields the freshly appended
            :class:`pptx.slide.Slide` so the caller can populate it inside a
            ``with`` block.

        See Also
        --------
        SlideContext : The returned context manager type.
        Presentation.new_slide : Non-scoped alternative that simply
            appends a slide.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     with pres.enter_new_slide() as slide:
        ...         _ = slide.shapes
        ...     len(pres.slides)
        1
        """
        return SlideContext(
            self,
            layout=layout,
        )

    def empty(
        self,
    ) -> Self:
        """
        Remove every slide from the presentation in place.

        Iterates from the last slide to the first, dropping the part
        relationship and deleting the slide-id entry on the presentation
        package. This is useful when the template is being reused as a
        skeleton and the caller wants to populate the deck from scratch
        while preserving master slides and other template assets that
        live outside the slide collection.

        Returns
        -------
        Self
            The current :class:`Presentation` instance, enabling method
            chaining after emptying the deck.

        See Also
        --------
        Presentation.new_slide : Helper for repopulating the deck after
            emptying it.
        Presentation.delete_slide : Planned single-slide deletion
            counterpart.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     _ = pres.new_slide().new_slide()
        ...     _ = pres.empty().new_slide()
        ...     len(pres.slides)
        1
        """
        for idx in range(len(self.slides) - 1, -1, -1):
            rId = self.slides._sldIdLst[idx].rId  # pyright: ignore[reportPrivateUsage, reportUnknownMemberType, reportAttributeAccessIssue, reportUnknownVariableType]  # noqa: N806, SLF001  # ty:ignore[unresolved-attribute]
            self.internal.part.drop_rel(rId=rId)  # pyright: ignore[reportUnknownArgumentType]
            del self.slides._sldIdLst[idx]  # pyright: ignore[reportPrivateUsage] # noqa: SLF001

        return self

    def delete_slide(
        self,
        slide_number: int,
        /,
    ) -> Self:
        """
        Delete the slide at a given position (not yet implemented).

        Retained on the public API so callers can plan for the eventual
        capability and so that :class:`SlideContext` can reference it as
        a rollback hook. Until the implementation lands, invoking this
        method raises :class:`NotImplementedError` with a message
        identifying the requested slide.

        Parameters
        ----------
        slide_number
            1-based index of the slide to remove once this method is
            implemented. Retained on the public API so callers can plan for
            the eventual capability.

        Returns
        -------
        Self
            The current instance, for chaining, once the implementation is
            in place.

        Raises
        ------
        NotImplementedError
            Always, until slide deletion is implemented.

        See Also
        --------
        Presentation.empty : Related helper that clears every slide at
            once.
        SlideContext.__exit__ : Caller that will rely on this method
            being implemented for rollback.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     try:
        ...         pres.delete_slide(1)
        ...     except NotImplementedError as exc:
        ...         "Deleting slides" in str(exc)
        True
        """
        msg = f"Deleting slides is not implemented yet. Can't delete slide {slide_number}"
        raise NotImplementedError(msg)
        return self

    def copy_slide(
        self,
        slide_number: int,
        /,
    ) -> Self:
        """
        Duplicate an existing slide (not yet implemented).

        The unreachable body sketches the intended approach: take a deep
        copy of every shape on the source slide, append them to a new
        slide based on a blank layout, and copy across non-notes
        relationships. Until this is wired up the method always raises
        :class:`NotImplementedError`.

        Parameters
        ----------
        slide_number
            1-based index of the slide to be duplicated once the method is
            implemented.

        Returns
        -------
        Self
            The current instance, for chaining, once the implementation is
            in place.

        Raises
        ------
        NotImplementedError
            Always, until slide copying is implemented.

        See Also
        --------
        Presentation.new_slide : Primitive that the planned
            implementation will build on top of.
        Presentation.move_slide : Related planned feature for slide
            repositioning.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     try:
        ...         pres.copy_slide(1)
        ...     except NotImplementedError as exc:
        ...         "Copying slides" in str(exc)
        True
        """
        msg = f"Copying slides is not implemented yet. Can't copy slide {slide_number}"
        raise NotImplementedError(msg)
        slide_idx = slide_number - 1
        template_slide = self.slides[slide_idx]

        try:
            blank_slide_layout = self.internal.slide_layouts[12]
        except IndexError:
            blank_slide_layout = self.internal.slide_layouts[len(self.internal.slide_layouts) - 1]

        copied_slide = self.slides.add_slide(slide_layout=blank_slide_layout)

        for shape in template_slide.shapes:
            element = shape.element
            new_element = deepcopy(element)
            copied_slide.shapes._spTree.insert_element_before(new_element, "p:extLst")  # noqa: SLF001

        for _, value in six.iteritems(template_slide.part.rels):
            if "notesSlide" not in value.reltype:
                copied_slide.part.rels.add_relationship(
                    value.reltype,
                    value._target,  # noqa: SLF001
                    value.rId,
                )

        return self

    def move_slide(
        self,
        slide_number: int,
        /,
        *,
        to_position: int,
    ) -> Self:
        """
        Move a slide to a new position (not yet implemented).

        Sketches a single-slide repositioning primitive that will
        complement :meth:`reorder_slides`. Until the implementation is
        wired up, callers receive :class:`NotImplementedError` with a
        message identifying both the source and target positions so
        that planning can proceed against the eventual signature.

        Parameters
        ----------
        slide_number
            1-based index of the slide to be relocated once the method is
            implemented.
        to_position
            1-based index at which the slide should appear after the move.

        Returns
        -------
        Self
            The current instance, for chaining, once the implementation is
            in place.

        Raises
        ------
        NotImplementedError
            Always, until slide reordering by move is implemented.

        See Also
        --------
        Presentation.reorder_slides : Related bulk-reordering planned
            feature.
        Presentation.delete_slide : Planned counterpart for slide
            removal.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     try:
        ...         pres.move_slide(1, to_position=3)
        ...     except NotImplementedError as exc:
        ...         "Moving slides" in str(exc)
        True
        """
        msg = f"Moving slides is not implemented yet. Can't move slide {slide_number} to position {to_position}."
        raise NotImplementedError(msg)
        return self

    def reorder_slides(
        self,
        new_order: list[int],
        /,
    ) -> Self:
        """
        Reorder the slide collection (not yet implemented).

        Represents the bulk-reordering counterpart of
        :meth:`move_slide`. The planned implementation will rearrange
        ``_sldIdLst`` according to ``new_order``; today the method
        raises :class:`NotImplementedError` with a message listing the
        requested permutation for diagnostic purposes.

        Parameters
        ----------
        new_order
            Permutation specifying the desired order of slides expressed as
            1-based indices; the ``i``-th entry gives the original index of
            the slide that should occupy position ``i`` once the method is
            implemented.

        Returns
        -------
        Self
            The current instance, for chaining, once the implementation is
            in place.

        Raises
        ------
        NotImplementedError
            Always, until bulk slide reordering is implemented.

        See Also
        --------
        Presentation.move_slide : Related single-slide reposition hook.
        Presentation.slides : Collection whose order this method will
            eventually manipulate.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     try:
        ...         pres.reorder_slides([2, 1])
        ...     except NotImplementedError as exc:
        ...         "Reordering slides" in str(exc)
        True
        """
        msg = f"Reordering slides is not implemented yet. Can't reorder to new order {', '.join(map(str, new_order))}."
        raise NotImplementedError(msg)
        return self

    def insertion_spacing(
        self,
        *,
        height: Length | None = None,
        width: Length | None = None,
        x_shift: Length | None = None,
        y_shift: Length | None = None,
    ) -> dict[str, Length | None]:
        """
        Resolve a positional spec suitable for ``add_textbox`` and friends.

        Any missing offset is computed relative to the slide dimensions
        so that the shape is either centred (when the corresponding size
        is given) or inset by 5% of the slide dimension (when it is
        not). The resulting dict maps directly onto ``python-pptx``'s
        ``left``/``top``/``width``/``height`` keyword arguments so it
        can be splatted straight into shape-insertion APIs.

        Parameters
        ----------
        height
            Desired shape height in EMU. When ``None``, the shape will size
            itself to its content; ``y_shift`` is then defaulted to a 5%
            top inset rather than centre-aligning the shape vertically.
        width
            Desired shape width in EMU. Handled analogously to ``height``
            with respect to the horizontal axis.
        x_shift
            Distance between the left edge of the slide and the left edge
            of the shape. If ``None``, it is derived so the shape is
            horizontally centred (when ``width`` is provided) or offset by
            5% of the slide width (when ``width`` is ``None``).
        y_shift
            Distance between the top edge of the slide and the top edge of
            the shape, resolved analogously to ``x_shift``.

        Returns
        -------
        dict
            Mapping with keys ``"left"``, ``"top"``, ``"width"``, and
            ``"height"`` suitable for splatting into ``shapes.add_textbox``
            and similar ``python-pptx`` calls.

        Raises
        ------
        ValueError
            If a required dimension cannot be resolved because both the
            argument and the corresponding slide dimension are ``None``.

        See Also
        --------
        Presentation.insert_textbox : Primary consumer of this spec.
        Presentation.fractional_height : Helper used for the vertical
            fallback inset.
        Presentation.fractional_width : Helper used for the horizontal
            fallback inset.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> from mayutils.interfaces.filetypes.pptx.units import Length
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     spacing = pres.insertion_spacing(width=Length.from_inches(3))
        ...     sorted(spacing)
        ['height', 'left', 'top', 'width']
        """
        if width is None:
            msg = "Width must be specified."
            raise ValueError(msg)

        if x_shift is None:
            x_shift = Length.from_float((self.width - width) * 0.5)

        if y_shift is None:
            y_shift = Length.from_float((self.height - height) * 0.5) if height is not None else self.fractional_height(0.05)

        return {
            "left": x_shift,
            "top": y_shift,
            "width": width,
            "height": height,
        }

    def insert_textbox(
        self,
        *,
        slide_number: int | None = None,
        height: Length | None = None,
        width: Length | None = None,
        x_shift: Length | None = None,
        y_shift: Length | None = None,
    ) -> Shape:
        """
        Add a text box shape to a slide and return the created shape.

        Resolves the target slide via :meth:`slide` (defaulting to the
        penultimate slide index as 1-based when ``slide_number`` is
        ``None``, matching the existing positional convention), computes
        the final positioning dict with :meth:`insertion_spacing`, and
        forwards the resolved geometry to ``shapes.add_textbox`` so the
        returned shape can be populated by :meth:`insert_text` or
        :meth:`insert_markdown`.

        Parameters
        ----------
        slide_number
            1-based index of the slide to add the text box to. When
            ``None``, the text box is added to ``self.slides[-2]`` (i.e.
            the penultimate slide index interpreted as 1-based), matching
            the existing implementation's positional convention.
        height
            Desired text box height forwarded to :meth:`insertion_spacing`.
        width
            Desired text box width forwarded to :meth:`insertion_spacing`.
        x_shift
            Horizontal offset from the slide's left edge, forwarded to
            :meth:`insertion_spacing`.
        y_shift
            Vertical offset from the slide's top edge, forwarded to
            :meth:`insertion_spacing`.

        Returns
        -------
        Shape
            The newly created text box shape, ready to have its
            ``text_frame`` populated by :meth:`insert_text` or other logic.

        See Also
        --------
        Presentation.insertion_spacing : Spacing resolver used here.
        Presentation.insert_text : Text-styling helper for the returned
            shape.
        Presentation.insert_markdown : Markdown-rendering helper for the
            returned shape.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> from mayutils.interfaces.filetypes.pptx.units import Length
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     _ = pres.new_slide().new_slide()
        ...     shape = pres.insert_textbox(
        ...         width=Length.from_inches(4),
        ...         height=Length.from_inches(1),
        ...     )
        ...     shape is not None
        True
        """
        slide = self.slide(slide_number if slide_number is not None else len(self.slides) - 1)
        spacing = self.insertion_spacing(
            height=height,
            width=width,
            x_shift=x_shift,
            y_shift=y_shift,
        )

        return slide.shapes.add_textbox(
            left=cast("Length", spacing["left"]),
            top=cast("Length", spacing["top"]),
            width=cast("Length", spacing["width"]),
            height=cast("Length", spacing["height"]),
        )

    def insert_text(  # noqa: C901
        self,
        text: str,
        /,
        *,
        textbox: Shape,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        strikethrough: bool = False,
        font_size: int | None = None,
        font_family: str | None = None,
        colour: Colour | str | None = None,
        background_colour: Colour | str | None = None,
        link: str | None = None,
    ) -> Self:
        """
        Populate a text box with styled text and return ``self`` for chaining.

        Assigns the raw ``text`` to the supplied shape's text frame and
        applies the requested typographic flags (bold/italic/underline/
        strike) plus optional font size, family, foreground colour, and
        solid background fill to the first paragraph. Colour arguments
        accept both :class:`Colour` instances and strings (resolved via
        :meth:`Colour.parse`). Hyperlink support is reserved for a
        future revision and currently raises :class:`NotImplementedError`.

        Parameters
        ----------
        text
            Raw text assigned to the text box. The string is written as-is
            to the first paragraph's text frame; Markdown is not parsed by
            this method.
        textbox
            Shape whose ``text_frame`` receives the text and on which
            fill/colour settings are applied.
        bold
            If ``True``, marks the first paragraph's font as bold.
        italic
            If ``True``, marks the first paragraph's font as italic.
        underline
            If ``True``, underlines the first paragraph's font.
        strikethrough
            If ``True``, applies a single strikethrough by writing
            ``strike="sngStrike"`` directly onto the run's XML element.
        font_size
            Font size expressed in points; converted to EMU via
            :func:`pptx.util.Pt`. ``None`` leaves the inherited size
            untouched.
        font_family
            Name of the font family to apply. ``None`` leaves the
            inherited font name untouched.
        colour
            Foreground text colour. Strings are parsed through
            :meth:`Colour.parse`; ``None`` leaves the inherited colour.
        background_colour
            Solid fill colour applied to the text box's background.
            Strings are parsed through :meth:`Colour.parse`; ``None``
            leaves the existing fill untouched.
        link
            Hyperlink target; currently unsupported and triggers a
            :class:`NotImplementedError` when provided.

        Returns
        -------
        Self
            The current :class:`Presentation` instance, supporting fluent
            chaining across multiple text insertions.

        Raises
        ------
        NotImplementedError
            If ``link`` is not ``None`` (hyperlink insertion is pending).

        See Also
        --------
        Presentation.insert_textbox : Factory for the ``textbox``
            argument.
        Presentation.insert_markdown : Markdown-aware alternative for
            rich text.
        mayutils.objects.colours.Colour : Colour parsing helper used
            internally.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> from mayutils.interfaces.filetypes.pptx.units import Length
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     _ = pres.new_slide().new_slide()
        ...     box = pres.insert_textbox(
        ...         width=Length.from_inches(4),
        ...         height=Length.from_inches(1),
        ...     )
        ...     pres.insert_text("Hello", textbox=box, bold=True) is pres
        True
        """
        if colour is not None and not isinstance(colour, Colour):
            colour = Colour.parse(colour)
        if background_colour is not None and not isinstance(background_colour, Colour):
            background_colour = Colour.parse(background_colour)

        textbox.text_frame.text = text

        if font_size is not None:
            textbox.text_frame.paragraphs[0].font.size = Pt(points=font_size)
        if font_family is not None:
            textbox.text_frame.paragraphs[0].font.name = font_family
        if colour is not None:
            textbox.text_frame.paragraphs[0].font.color.rgb = RGBColor(
                r=colour.r,
                g=colour.g,
                b=colour.b,
            )
        if background_colour is not None:
            textbox.fill.solid()
            textbox.fill.fore_color.rgb = RGBColor(
                r=background_colour.r,
                g=background_colour.g,
                b=background_colour.b,
            )
        if bold:
            textbox.text_frame.paragraphs[0].font.bold = True
        if italic:
            textbox.text_frame.paragraphs[0].font.italic = True
        if underline:
            textbox.text_frame.paragraphs[0].font.underline = True
        if strikethrough:
            textbox.text_frame.paragraphs[0].font._element.attrib["strike"] = "sngStrike"  # pyright: ignore[reportUnknownMemberType, reportPrivateUsage]  # noqa: SLF001

        if link is not None:
            msg = "Hyperlinks are not implemented yet."
            raise NotImplementedError(msg)
            from pptx.util import URI  # noqa: PLC0415

            textbox.text_frame.paragraphs[0].hyperlink.address = URI(link)

        return self

    def insert_markdown(
        self,
        markdown: str,
        /,
        *,
        slide_number: int | None = None,
        height: Length | None = None,
        width: Length | None = None,
        x_shift: Length | None = None,
        y_shift: Length | None = None,
    ) -> Self:
        r"""
        Add a text box on ``slide_number`` and populate it with ``markdown``.

        Positional and sizing semantics mirror :meth:`insert_textbox`;
        the new shape's text frame is then handed to
        :func:`mayutils.interfaces.filetypes.pptx.markdown.add_markdown_to_text_frame`
        so the markdown is rendered into runs and paragraphs with the
        appropriate character and paragraph formatting (headings,
        emphasis, lists, links).

        Parameters
        ----------
        markdown
            Markdown source to render into the new text box.
        slide_number
            1-based index of the slide to add the text box to.
            Defaults to the last slide when ``None``.
        height
            Desired text box height forwarded to :meth:`insertion_spacing`.
        width
            Desired text box width forwarded to :meth:`insertion_spacing`.
        x_shift
            Horizontal offset from the slide's left edge, forwarded to
            :meth:`insertion_spacing`.
        y_shift
            Vertical offset from the slide's top edge, forwarded to
            :meth:`insertion_spacing`.

        Returns
        -------
        Self
            The current :class:`Presentation` instance for fluent
            chaining.

        See Also
        --------
        Presentation.insert_textbox : Underlying text-box factory.
        mayutils.interfaces.filetypes.pptx.markdown.add_markdown_to_text_frame :
            Helper that parses the markdown into runs and paragraphs.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> from mayutils.interfaces.filetypes.pptx.units import Length
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     _ = pres.new_slide().new_slide()
        ...     result = pres.insert_markdown(
        ...         "# Title\nBody",
        ...         width=Length.from_inches(5),
        ...         height=Length.from_inches(1),
        ...     )
        ...     result is pres
        True
        """
        textbox = self.insert_textbox(
            slide_number=slide_number,
            height=height,
            width=width,
            x_shift=x_shift,
            y_shift=y_shift,
        )
        add_markdown_to_text_frame(
            markdown,
            text_frame=textbox.text_frame,
        )

        return self

    def insert_image(
        self,
        image_path: Path | str,
        /,
    ) -> Self:
        """
        Insert an image onto a slide (not yet implemented).

        Placeholder for a future helper that will splice a local image
        file into the current slide via ``shapes.add_picture``. Until
        the implementation is wired up, any invocation raises
        :class:`NotImplementedError` with a message identifying the
        requested image path for diagnostic purposes.

        Parameters
        ----------
        image_path
            File-system path of the image to insert once the method is
            implemented. Retained on the public API so callers can plan
            for the eventual capability.

        Returns
        -------
        Self
            The current instance, for chaining, once the implementation
            is in place.

        Raises
        ------
        NotImplementedError
            Always, until image insertion is implemented.

        See Also
        --------
        Presentation.insert_textbox : Existing shape-insertion helper
            that image insertion will mirror.
        Presentation.insert_table : Related placeholder for tabular data
            insertion.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     try:
        ...         pres.insert_image("logo.png")
        ...     except NotImplementedError as exc:
        ...         "Image insertion" in str(exc)
        True
        """
        msg = f"Image insertion is not implemented yet. Couldn't inser image from {image_path}."
        raise NotImplementedError(msg)
        return self

    def insert_table(
        self,
        table: DataFrame | Styler,
        /,
    ) -> Self:
        """
        Insert a tabular dataset onto a slide (not yet implemented).

        Placeholder for a future helper that will render a
        :class:`pandas.DataFrame` or :class:`Styler` into a native
        PowerPoint table using ``shapes.add_table``. The current
        implementation only probes ``table`` for its row count (to keep
        the upcoming diagnostic message informative) before raising
        :class:`NotImplementedError`.

        Parameters
        ----------
        table
            Tabular data to insert once the method is implemented. A
            :class:`Styler` is unwrapped via ``table.data`` when present
            so the row count is read from the underlying DataFrame.

        Returns
        -------
        Self
            The current instance, for chaining, once the implementation
            is in place.

        Raises
        ------
        NotImplementedError
            Always, until table insertion is implemented.

        See Also
        --------
        Presentation.insert_image : Related placeholder for image
            insertion.
        mayutils.objects.dataframes.pandas.stylers.Styler : Styler type
            whose underlying DataFrame is inspected here.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> import pandas as pd
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     try:
        ...         pres.insert_table(pd.DataFrame({"a": [1, 2]}))
        ...     except NotImplementedError as exc:
        ...         "Table insertion" in str(exc)
        True
        """
        try:
            rows: int = table.data.shape[0]  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType, reportAttributeAccessIssue]  # ty:ignore[unresolved-attribute]
        except AttributeError:
            rows: int = table.shape[0]  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType, reportAttributeAccessIssue]  # ty:ignore[unresolved-attribute]
        msg = f"Table insertion is not implemented yet. Cannot insert table of shape: {rows}"
        raise NotImplementedError(msg)
        return self

    def save(
        self,
        file_path: Path | str,
        /,
    ) -> None:
        """
        Write the presentation to disk as a ``.pptx`` file.

        Normalises ``file_path`` to :class:`pathlib.Path` and forwards
        it (as a string) to :meth:`pptx.Presentation.save`, which
        serialises the in-memory deck back to the OOXML container.
        Parent directories are not created automatically, so callers
        must ensure the destination directory already exists.

        Parameters
        ----------
        file_path
            Destination path. Any parent directories must already exist;
            no directory creation is attempted. Passed to
            :meth:`pptx.Presentation.save` after conversion to a string.

        Returns
        -------
        None
            ``python-pptx``'s ``save`` does not return a value; the side
            effect is the ``.pptx`` file being written to disk.

        See Also
        --------
        Presentation.to_pdf : Export helper that internally calls this
            method to stage a temporary ``.pptx``.
        pptx.Presentation.save : Underlying library method used here.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     out = Path(_d) / "out.pptx"
        ...     pres.save(out)
        ...     out.exists()
        True
        """
        file_path = Path(file_path)

        return self.internal.save(
            file=str(file_path),
        )


def convert_pptx_to_pdf(
    pptx_path: str | Path,
    /,
    *,
    output_dir: str | Path = IMAGES_FOLDER.parent / "PDF",
    soffice_path: str | None = None,
) -> Path:
    """
    Convert a ``.pptx`` file to PDF using headless LibreOffice.

    Locates the ``soffice`` binary (either via the explicit
    ``soffice_path`` or by consulting :func:`shutil.which`), then
    invokes it with ``--headless --convert-to pdf`` targeting the
    requested output directory. The stdout/stderr of the subprocess
    are captured and embedded in the :class:`RuntimeError` message
    emitted on failure so diagnostics are preserved.

    Parameters
    ----------
    pptx_path
        Path to the source ``.pptx`` file that should be converted.
    output_dir
        Directory in which the generated PDF is written. Created if it
        does not already exist. Defaults to the ``PDF`` folder that is a
        sibling of :data:`mayutils.export.images.IMAGES_FOLDER`.
    soffice_path
        Explicit path to the LibreOffice ``soffice`` binary. When
        ``None``, the binary is located via :func:`shutil.which`.

    Returns
    -------
    pathlib.Path
        Absolute path of the produced PDF file, constructed as
        ``output_dir / (pptx_path.stem + ".pdf")``.

    Raises
    ------
    FileNotFoundError
        If ``pptx_path`` does not exist, or if ``soffice`` cannot be
        located either via ``soffice_path`` or on the system ``PATH``.
    RuntimeError
        If the ``soffice`` subprocess returns a non-zero exit code, or
        if it reports success but the expected output PDF is not found
        on disk.

    See Also
    --------
    Presentation.to_pdf : High-level wrapper that saves and delegates
        here.
    Presentation.render_pages : Pipeline that uses the resulting PDF
        for rasterisation.

    Notes
    -----
    LibreOffice must be installed locally. The conversion is performed in
    headless mode using ``--convert-to pdf`` and its stdout/stderr are
    captured and attached to :class:`RuntimeError` on failure.

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> from pathlib import Path
    >>> from mayutils.interfaces.filetypes.pptx import convert_pptx_to_pdf
    >>> pdf = convert_pptx_to_pdf(  # doctest: +SKIP
    ...     Path("/tmp/deck.pptx"),
    ...     output_dir="/tmp/pdfs",
    ... )
    >>> pdf.suffix  # doctest: +SKIP
    '.pdf'
    """
    pptx_path = Path(pptx_path)
    output_dir = Path(output_dir)

    if not pptx_path.exists():
        msg = f"PPTX not found: {pptx_path}"
        raise FileNotFoundError(msg)

    output_dir.mkdir(parents=True, exist_ok=True)

    if soffice_path:
        soffice = Path(soffice_path)
    else:
        soffice = shutil.which(cmd="soffice")
        if soffice:
            soffice = Path(soffice)

    if not soffice or not Path(soffice).exists():
        msg = "LibreOffice (soffice) not found. Install LibreOffice or pass soffice_path explicitly."
        raise FileNotFoundError(msg)

    args = [
        str(soffice),
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_dir),
        str(pptx_path),
    ]

    result = subprocess.run(
        args=args,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        msg = f"PPTX → PDF conversion failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        raise RuntimeError(msg)

    pdf_path = output_dir / (pptx_path.stem + ".pdf")

    if not pdf_path.exists():
        msg = "Conversion reported success but PDF not found"
        raise RuntimeError(msg)

    return pdf_path


class SlideView:
    """
    View a single slide of a :class:`Presentation` for notebook rendering.

    Obtained from :meth:`Presentation.preview`. Holds a reference to the
    parent presentation plus the target slide's 1-based index, and
    exposes ``__repr__`` / ``_repr_html_`` / ``_repr_mimebundle_`` so
    evaluating the view at the end of a notebook cell renders just that
    one slide as an inline PNG rather than the whole deck.

    Parameters
    ----------
    presentation
        The presentation this view belongs to. The view delegates
        back to it for saving, conversion, and rasterisation.
    slide_number
        1-based index of the slide to render.

    See Also
    --------
    Presentation.preview : Factory method that constructs a
        :class:`SlideView`.
    Presentation.render_pages : Low-level render helper used by
        :meth:`_repr_html_`.
    pptx.slide.Slide : Slide type returned by :attr:`slide`.

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> from pptx import Presentation as _Init
    >>> from mayutils.interfaces.filetypes.pptx import Presentation, SlideView
    >>> with tempfile.TemporaryDirectory() as _d:
    ...     tpl = Path(_d) / "template.pptx"
    ...     _Init().save(str(tpl))
    ...     pres = Presentation(tpl)
    ...     _ = pres.new_slide()
    ...     view = pres.preview(1)
    ...     isinstance(view, SlideView)
    True
    """

    def __init__(
        self,
        presentation: Presentation,
        /,
        *,
        slide_number: int,
    ) -> None:
        """
        Bind the view to a specific slide of a presentation.

        Validates that ``slide_number`` resolves to an existing slide
        using the same 1-based convention as :meth:`Presentation.slide`,
        then stores the presentation reference and the slide index so
        the view remains lazy — the underlying slide is re-resolved on
        each render in case intermediate edits have altered it.

        Parameters
        ----------
        presentation
            Parent presentation.
        slide_number
            1-based index of the slide to render. Must be in
            ``1..len(presentation.slides)``.

        Raises
        ------
        IndexError
            If ``slide_number`` does not resolve to an existing slide.

        See Also
        --------
        Presentation.preview : Public constructor for this class.
        Presentation.slide : Slide lookup helper with the same 1-based
            convention.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation, SlideView
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     _ = pres.new_slide()
        ...     view = SlideView(pres, slide_number=1)
        ...     view.slide_number
        1
        """
        if slide_number < 1 or slide_number > len(presentation.slides):
            msg = f"Slide number {slide_number} is out of range. Presentation has {len(presentation.slides)} slides."
            raise IndexError(msg)
        self.presentation = presentation
        self.slide_number = slide_number

    @property
    def slide(
        self,
    ) -> Slide:
        """
        Resolve the underlying ``python-pptx`` slide.

        Performs a fresh lookup against the parent presentation every
        time it is accessed, delegating to :meth:`Presentation.slide`
        with the bound :attr:`slide_number`. Keeping the resolution lazy
        means the view remains valid even if the deck has been mutated
        between construction and rendering, provided the target index is
        still in range.

        Returns
        -------
        Slide
            The slide at :attr:`slide_number` on the parent
            presentation. Kept lazy so the view remains valid even if
            intermediate edits reorder the deck.

        See Also
        --------
        Presentation.slide : Underlying 1-based slide lookup.
        SlideView._repr_html_ : Consumer of the resolved slide.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from pptx.slide import Slide
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     _ = pres.new_slide()
        ...     view = pres.preview(1)
        ...     isinstance(view.slide, Slide)
        True
        """
        return self.presentation.slide(self.slide_number)

    def __repr__(
        self,
    ) -> str:
        """
        Return a one-line text rendering of the slide view.

        The output embeds the template path, the slide's 1-based index,
        and a best-effort title extracted via
        :meth:`Presentation.slide_label`, giving enough context at a
        glance to identify the slide without triggering the HTML render
        pipeline (useful in plain REPLs and logs).

        Returns
        -------
        str
            ``"SlideView(<template>, N: <title>)"`` — path, slide
            number and (best-effort) title text.

        See Also
        --------
        Presentation.slide_label : Title probe used to build the label.
        SlideView._repr_html_ : HTML counterpart for notebook rendering.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from pptx import Presentation as _Init
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> with tempfile.TemporaryDirectory() as _d:
        ...     tpl = Path(_d) / "template.pptx"
        ...     _Init().save(str(tpl))
        ...     pres = Presentation(tpl)
        ...     _ = pres.new_slide()
        ...     text = repr(pres.preview(1))
        ...     text.startswith("SlideView(") and text.endswith(", 1: '')")
        True
        """
        label = Presentation.slide_label(self.slide)

        return f"SlideView({self.presentation.template!s}, {self.slide_number}: {label!r})"

    def _repr_html_(
        self,
    ) -> str:
        """
        Render just this slide as an inline base64 PNG.

        Drives the same save → pdf → png pipeline as
        :meth:`Presentation._repr_html_` but restricts it to the one
        slide bound at construction, cutting down both the PDF page
        count and the number of pixmaps generated. The resulting HTML
        snippet is suitable for direct embedding in notebook cells.

        Returns
        -------
        str
            A single ``<figure>``/``<img>`` HTML snippet with the
            slide's PNG embedded as base64.

        See Also
        --------
        Presentation.render_pages : Rendering iterator consumed here.
        Presentation._repr_html_ : Whole-deck counterpart.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> pres = Presentation("/path/to/deck.pptx")  # doctest: +SKIP
        >>> html = pres.preview(1)._repr_html_()  # doctest: +SKIP
        >>> "<figure>" in html  # doctest: +SKIP
        True
        """
        pages = dict(self.presentation.render_pages([self.slide_number]))
        png = pages[self.slide_number]
        data = base64.b64encode(png).decode(encoding="ascii")

        return (
            f"<figure><figcaption>Slide {self.slide_number}</figcaption>"
            f'<img alt="slide {self.slide_number}" src="data:image/png;base64,{data}"/></figure>'
        )

    def _repr_mimebundle_(
        self,
    ) -> dict[str, str]:
        """
        Return text and HTML renderings of the slide as a mime bundle.

        Mirrors :meth:`Presentation._repr_mimebundle_` but scoped to a
        single slide: rich notebook front-ends pick up the ``text/html``
        PNG, while plain terminals transparently fall back to the
        ``text/plain`` summary produced by :meth:`__repr__`.

        Returns
        -------
        dict of str to str
            Mapping keyed by ``"text/plain"`` and ``"text/html"``.

        See Also
        --------
        SlideView._repr_html_ : HTML rendering included in the bundle.
        SlideView.__repr__ : Text rendering included in the bundle.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from mayutils.interfaces.filetypes.pptx import Presentation
        >>> pres = Presentation("/path/to/deck.pptx")  # doctest: +SKIP
        >>> bundle = pres.preview(1)._repr_mimebundle_()  # doctest: +SKIP
        >>> sorted(bundle)  # doctest: +SKIP
        ['text/html', 'text/plain']
        """
        return {
            "text/plain": repr(self),
            "text/html": self._repr_html_(),
        }
