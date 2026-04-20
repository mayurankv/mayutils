"""Tests for ``mayutils.export.quarto``.

Each test renders a minimal ``.qmd`` inside a :func:`pytest.tmp_path`
fixture so neither the source directory nor the repository ``Outputs``
folder is ever written to. The tests require the ``notebook`` extra
(specifically ``quarto-cli``) to be installed; the module is skipped at
collection time otherwise.
"""

from __future__ import annotations

import pytest

pytest.importorskip("quarto_cli")

from typing import TYPE_CHECKING

from mayutils.export import quarto

if TYPE_CHECKING:
    from pathlib import Path


def _make_qmd(path: Path) -> None:
    """Write a minimal valid Quarto source document at ``path``."""
    path.write_text("---\ntitle: test\n---\n\nHello.\n")


class TestQuartoBin:
    """Tests for :func:`quarto.quarto_bin`."""

    def test_resolves_existing_binary(self) -> None:
        """Returns a :class:`Path` that points at an existing executable."""
        binary = quarto.quarto_bin()
        assert binary.exists()
        assert binary.is_file()


class TestListFormats:
    """Tests for :func:`quarto.list_formats`."""

    def test_includes_common_formats(self) -> None:
        """Tuple covers the headline Pandoc/Quarto output targets."""
        formats = quarto.list_formats()
        assert {"html", "markdown", "pdf", "pptx", "revealjs", "docx", "typst"}.issubset(formats)

    def test_matches_default_settings_keys(self) -> None:
        """``list_formats`` reflects :data:`quarto.DEFAULT_SETTINGS` exactly."""
        assert set(quarto.list_formats()) == set(quarto.DEFAULT_SETTINGS)


class TestListExtensions:
    """Tests for :func:`quarto.list_extensions`."""

    def test_returns_tuple_of_dicts(self) -> None:
        """The parsed table is a tuple of dicts with the expected keys."""
        result = quarto.list_extensions()
        assert isinstance(result, tuple)
        for row in result:
            assert set(row).issuperset({"id", "version", "contributes"})


class TestExport:
    """Tests for :func:`quarto.export`."""

    @pytest.mark.parametrize(
        ("to", "extension"),
        [
            ("html", ".html"),
            ("markdown", ".md"),
            ("docx", ".docx"),
            ("gfm", ".md"),
            ("revealjs", ".html"),
            ("latex", ".tex"),
        ],
    )
    def test_returned_path_exists_with_expected_extension(
        self,
        tmp_path: Path,
        to: str,
        extension: str,
    ) -> None:
        """Rendered artefact lands at the returned path with the right suffix."""
        source_dir = tmp_path / "src"
        source_dir.mkdir()
        qmd = source_dir / "input.qmd"
        _make_qmd(path=qmd)

        output_dir = tmp_path / "out"

        result = quarto.export(
            qmd,
            to=to,
            output_dir=output_dir,
            title="probe",
        )

        assert result.parent == output_dir
        assert result.name.endswith(extension)
        assert result.exists()
        assert result.stat().st_size > 0

    def test_default_output_dir_derives_from_format(
        self,
        tmp_path: Path,
    ) -> None:
        """When ``output_dir`` is ``None`` the destination is under ``OUTPUT_FOLDER``."""
        qmd = tmp_path / "input.qmd"
        _make_qmd(path=qmd)

        monkeypatched_root = tmp_path / "mock_outputs"
        quarto_module_output_folder = quarto.OUTPUT_FOLDER
        quarto.OUTPUT_FOLDER = monkeypatched_root
        try:
            result = quarto.export(
                qmd,
                to="markdown",
                title="probe",
            )
        finally:
            quarto.OUTPUT_FOLDER = quarto_module_output_folder

        assert monkeypatched_root in result.parents
        assert result.exists()

    def test_invalid_format_raises_before_subprocess(
        self,
        tmp_path: Path,
    ) -> None:
        """An unknown ``to`` value fails fast with a list of valid formats."""
        qmd = tmp_path / "input.qmd"
        _make_qmd(path=qmd)

        with pytest.raises(ValueError, match=r"Unknown Quarto format 'bogus'"):
            quarto.export(
                qmd,
                to="bogus",
                output_dir=tmp_path / "out",
            )

    def test_source_directory_not_polluted(
        self,
        tmp_path: Path,
    ) -> None:
        """No new files are written next to the source during render."""
        source_dir = tmp_path / "src"
        source_dir.mkdir()
        qmd = source_dir / "input.qmd"
        _make_qmd(path=qmd)

        before = {child.name for child in source_dir.iterdir()}

        quarto.export(
            qmd,
            to="html",
            output_dir=tmp_path / "out",
            title="probe",
        )

        after = {child.name for child in source_dir.iterdir()}
        assert before == after

    def test_same_stem_sibling_not_clobbered(
        self,
        tmp_path: Path,
    ) -> None:
        """Pre-existing ``<stem>.<ext>`` next to the source is preserved."""
        source_dir = tmp_path / "src"
        source_dir.mkdir()
        qmd = source_dir / "report.qmd"
        _make_qmd(path=qmd)
        stale = source_dir / "report.html"
        stale.write_text("<!-- STALE -->")

        quarto.export(
            qmd,
            to="html",
            output_dir=tmp_path / "out",
            title="probe",
        )

        assert stale.read_text() == "<!-- STALE -->"

    def test_relative_asset_reference_resolves(
        self,
        tmp_path: Path,
    ) -> None:
        """Relative paths inside the ``.qmd`` resolve via symlinked siblings."""
        source_dir = tmp_path / "src"
        source_dir.mkdir()
        (source_dir / "data").mkdir()
        (source_dir / "data" / "table.csv").write_text("a,b\n1,2\n")

        qmd = source_dir / "report.qmd"
        qmd.write_text(
            "---\ntitle: test\n---\n\nSee [the data](data/table.csv).\n",
        )

        result = quarto.export(
            qmd,
            to="markdown",
            output_dir=tmp_path / "out",
            title="probe",
        )

        assert result.exists()
        assert "data/table.csv" in result.read_text()

    def test_source_qmd_not_mutated(
        self,
        tmp_path: Path,
    ) -> None:
        """The input ``.qmd`` on disk is unchanged after a render."""
        qmd = tmp_path / "input.qmd"
        _make_qmd(path=qmd)
        before = qmd.read_bytes()

        quarto.export(
            qmd,
            to="html",
            output_dir=tmp_path / "out",
            title="probe",
        )

        assert qmd.read_bytes() == before
