"""Tests for ``mayutils.export.nbconvert``.

Each test renders a minimal notebook inside a :func:`pytest.tmp_path`
fixture so the filesystem stays clean between runs and between suites.
The tests require the ``notebook`` extra (``jupyter``, ``nbconvert``) to
be installed; the module is skipped at collection time otherwise.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("nbconvert")
pytest.importorskip("jupyter_core")

from mayutils.export import nbconvert


def _make_notebook(
    path: Path,
) -> None:
    """Write a minimal valid ``.ipynb`` at ``path``."""
    path.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "markdown",
                        "metadata": {},
                        "source": ["# test\n"],
                    },
                ],
                "metadata": {
                    "kernelspec": {
                        "name": "python3",
                        "language": "python",
                        "display_name": "Python 3",
                    },
                },
                "nbformat": 4,
                "nbformat_minor": 5,
            },
        ),
    )


class TestJupyterBin:
    """Tests for :func:`nbconvert.jupyter_bin`."""

    def test_resolves_existing_executable(self) -> None:
        """Returns an absolute path to a real ``jupyter`` binary on PATH."""
        binary = nbconvert.jupyter_bin()
        assert Path(binary).exists()


class TestListFormats:
    """Tests for :func:`nbconvert.list_formats`."""

    def test_includes_common_formats(self) -> None:
        """Tuple covers the built-in nbconvert exporters every install ships."""
        formats = nbconvert.list_formats()
        assert {"html", "markdown", "notebook", "pdf"}.issubset(formats)

    def test_returns_tuple_of_str(self) -> None:
        """All values are plain strings (no ``CaseInsensitiveStr`` etc.)."""
        formats = nbconvert.list_formats()
        assert all(isinstance(name, str) for name in formats)


class TestListTemplates:
    """Tests for :func:`nbconvert.list_templates`."""

    def test_returns_sorted_unique(self) -> None:
        """Result is alphabetically sorted and deduplicated."""
        templates = nbconvert.list_templates()
        assert list(templates) == sorted(set(templates))

    def test_includes_builtin_templates(self) -> None:
        """Bundled templates (``lab``, ``classic``) are discovered."""
        templates = nbconvert.list_templates()
        assert "lab" in templates
        assert "classic" in templates


class TestExport:
    """Tests for :func:`nbconvert.export`."""

    @pytest.mark.parametrize(
        ("to", "extension"),
        [
            ("html", ".html"),
            ("markdown", ".md"),
            ("notebook", ".ipynb"),
            ("rst", ".rst"),
            ("asciidoc", ".asciidoc"),
            ("python", ".py"),
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
        nb = source_dir / "input.ipynb"
        _make_notebook(path=nb)

        output_dir = tmp_path / "out"

        result = nbconvert.export(
            nb,
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
        """When ``output_dir`` is ``None`` the destination is derived from ``to``."""
        nb = tmp_path / "input.ipynb"
        _make_notebook(path=nb)

        # Redirect the global OUTPUT_FOLDER so we don't write to the repo Outputs dir.
        monkeypatched_root = tmp_path / "mock_outputs"
        nbconvert_module_output_folder = nbconvert.OUTPUT_FOLDER
        nbconvert.OUTPUT_FOLDER = monkeypatched_root
        try:
            result = nbconvert.export(
                nb,
                to="markdown",
                title="probe",
            )
        finally:
            nbconvert.OUTPUT_FOLDER = nbconvert_module_output_folder

        assert monkeypatched_root in result.parents
        assert result.exists()

    def test_invalid_format_raises_before_subprocess(
        self,
        tmp_path: Path,
    ) -> None:
        """An unknown ``to`` value fails fast with a list of valid formats."""
        nb = tmp_path / "input.ipynb"
        _make_notebook(path=nb)

        with pytest.raises(ValueError, match=r"Unknown nbconvert format 'bogus'"):
            nbconvert.export(
                nb,
                to="bogus",
                output_dir=tmp_path / "out",
            )

    def test_invalid_template_raises_before_subprocess(
        self,
        tmp_path: Path,
    ) -> None:
        """An unknown ``template`` value fails fast before nbconvert is invoked."""
        nb = tmp_path / "input.ipynb"
        _make_notebook(path=nb)

        with pytest.raises(ValueError, match=r"Unknown nbconvert template 'does-not-exist'"):
            nbconvert.export(
                nb,
                to="html",
                template="does-not-exist",
                output_dir=tmp_path / "out",
            )

    def test_source_notebook_not_mutated(
        self,
        tmp_path: Path,
    ) -> None:
        """The input notebook on disk is unchanged after a render."""
        nb = tmp_path / "input.ipynb"
        _make_notebook(path=nb)
        before = nb.read_bytes()

        nbconvert.export(
            nb,
            to="html",
            output_dir=tmp_path / "out",
            title="probe",
        )

        assert nb.read_bytes() == before
