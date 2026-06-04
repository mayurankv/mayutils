"""Tests for ``mayutils.visualisation.graphs.combine``.

:func:`combine_figures` rasterises the first page of each source PDF with
PyMuPDF and tiles them, row-major, onto a white canvas whose size is the
first tile's pixel dimensions scaled by the requested grid.  These tests
build tiny solid-colour PDFs, run the mosaic, and assert the deterministic
output structure (canvas size, blank-cell background, tile placement) plus
the ``NotImplementedError`` raised for unsupported source formats.  No claim
is made about exact rendered pixels beyond the solid fills used as fixtures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

pytest.importorskip("pymupdf")
pytest.importorskip("PIL")

if TYPE_CHECKING:
    from pathlib import Path

import pymupdf
from PIL import Image

from mayutils.visualisation.graphs.combine import combine_figures

_PAGE_PTS = 72
_TILE_PX = 72  # PyMuPDF's default 72-DPI pixmap renders a 72pt page at 72px.
_WHITE = (255, 255, 255)


def _make_pdf(path: Path, *, colour: tuple[float, float, float] = (1.0, 1.0, 1.0)) -> None:
    """Write a single-page solid-colour PDF of ``_PAGE_PTS`` square."""
    document = pymupdf.open()
    page = document.new_page(width=_PAGE_PTS, height=_PAGE_PTS)
    page.draw_rect(  # pyright: ignore[reportUnknownMemberType]
        page.rect,  # pyright: ignore[reportUnknownMemberType]
        color=colour,
        fill=colour,
    )
    document.save(filename=path)  # pyright: ignore[reportUnknownMemberType]
    document.close()


class TestCanvasShape:
    """Tests for the composed canvas dimensions."""

    @pytest.mark.parametrize(
        ("cols", "rows"),
        [
            (2, 2),
            (4, 1),
            (1, 4),
            (3, 2),
        ],
    )
    def test_canvas_size_is_grid_times_tile(
        self,
        tmp_path: Path,
        cols: int,
        rows: int,
    ) -> None:
        """The canvas is ``(tile_w * cols, tile_h * rows)`` pixels."""
        files = [tmp_path / f"src_{index}.pdf" for index in range(cols * rows)]
        for file in files:
            _make_pdf(file)

        out = tmp_path / "mosaic.png"
        combine_figures(*files, title=out, cols=cols, rows=rows)

        with Image.open(out) as img:
            assert img.size == (_TILE_PX * cols, _TILE_PX * rows)

    def test_output_is_rgb(self, tmp_path: Path) -> None:
        """The mosaic is written as an RGB image."""
        file = tmp_path / "src.pdf"
        _make_pdf(file)
        out = tmp_path / "mosaic.png"
        combine_figures(file, title=out, cols=1, rows=1)

        with Image.open(out) as img:
            assert img.mode == "RGB"


class TestTilePlacement:
    """Tests for where individual tiles land on the canvas."""

    def test_blank_cells_stay_white(self, tmp_path: Path) -> None:
        """With fewer files than cells, unfilled cells remain white."""
        file = tmp_path / "src.pdf"
        _make_pdf(file, colour=(0.0, 0.0, 0.0))
        out = tmp_path / "mosaic.png"
        combine_figures(file, title=out, cols=2, rows=2)

        with Image.open(out) as img:
            rgb = img.convert("RGB")
            width, height = rgb.size
            # First tile occupies the top-left cell; the bottom-right is blank.
            assert rgb.getpixel((0, 0)) == (0, 0, 0)
            assert rgb.getpixel((width - 1, height - 1)) == _WHITE

    def test_row_major_placement(self, tmp_path: Path) -> None:
        """Tiles fill left-to-right then top-to-bottom (row-major order)."""
        colours = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        ]
        files: list[Path] = []
        for index, colour in enumerate(colours):
            file = tmp_path / f"src_{index}.pdf"
            _make_pdf(file, colour=colour)
            files.append(file)

        out = tmp_path / "mosaic.png"
        combine_figures(*files, title=out, cols=2, rows=2)

        half = _TILE_PX // 2
        with Image.open(out) as img:
            rgb = img.convert("RGB")
            # Centre of each cell in row-major order: (col, row) = divmod(idx, cols).
            assert rgb.getpixel((half, half)) == (0, 0, 0)
            assert rgb.getpixel((_TILE_PX + half, half)) == (255, 0, 0)
            assert rgb.getpixel((half, _TILE_PX + half)) == (0, 255, 0)
            assert rgb.getpixel((_TILE_PX + half, _TILE_PX + half)) == (0, 0, 255)


class TestUnsupportedFiletype:
    """Tests for the unsupported-format guard."""

    def test_non_pdf_raises_not_implemented(self, tmp_path: Path) -> None:
        """A non-``pdf`` ``filetype`` raises ``NotImplementedError`` before any I/O."""
        out = tmp_path / "mosaic.png"
        with pytest.raises(NotImplementedError, match="not supported"):
            combine_figures(tmp_path / "missing.png", title=out, cols=1, rows=1, filetype="png")


class TestNoFiles:
    """Tests for the empty-input guard."""

    def test_no_files_raises_value_error(self, tmp_path: Path) -> None:
        """Calling with no figure files raises ``ValueError`` rather than ``IndexError``."""
        out = tmp_path / "mosaic.png"
        with pytest.raises(ValueError, match="at least one figure"):
            combine_figures(title=out, cols=1, rows=1)
