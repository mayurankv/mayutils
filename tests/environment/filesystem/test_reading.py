"""Tests for ``mayutils.environment.filesystem.reading``.

These cover :func:`read_file` — the defensive text reader that turns a
missing-or-non-regular-file into an actionable :class:`ValueError`
rather than a bare :class:`FileNotFoundError` or a permission error
from opening a directory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mayutils.environment.filesystem.reading import read_file

if TYPE_CHECKING:
    from pathlib import Path


class TestReadFileContent:
    """Tests for the happy path — reading the full text of a regular file."""

    def test_reads_text(self, tmp_path: Path) -> None:
        """The decoded contents of a regular file are returned verbatim."""
        path = tmp_path / "hello.txt"
        path.write_text("hello", encoding="utf-8")
        assert read_file(path) == "hello"

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """A ``str`` path is coerced to :class:`~pathlib.Path` and read."""
        path = tmp_path / "hello.txt"
        path.write_text("hello", encoding="utf-8")
        assert read_file(str(path)) == "hello"

    def test_multiline_preserves_newlines(self, tmp_path: Path) -> None:
        """Embedded newlines are preserved in the returned string."""
        path = tmp_path / "multi.txt"
        path.write_text("line1\nline2\n", encoding="utf-8")
        assert read_file(path) == "line1\nline2\n"

    def test_empty_file_returns_empty_string(self, tmp_path: Path) -> None:
        """An empty regular file reads back as the empty string."""
        path = tmp_path / "empty.txt"
        path.write_text("", encoding="utf-8")
        assert read_file(path) == ""

    def test_unicode_content(self, tmp_path: Path) -> None:
        """Non-ASCII UTF-8 content round-trips through the reader."""
        path = tmp_path / "unicode.txt"
        path.write_text("café — naïve", encoding="utf-8")
        assert read_file(path) == "café — naïve"


class TestReadFileErrors:
    """Tests for the :class:`ValueError` raised on non-regular-file inputs."""

    def test_missing_file_raises_value_error(self, tmp_path: Path) -> None:
        """A path with no file on disk raises ``ValueError`` (not ``FileNotFoundError``)."""
        with pytest.raises(ValueError, match="could not be found"):
            read_file(tmp_path / "missing.txt")

    def test_directory_raises_value_error(self, tmp_path: Path) -> None:
        """A directory is not a regular file, so reading it raises ``ValueError``."""
        with pytest.raises(ValueError, match="could not be found"):
            read_file(tmp_path)

    def test_error_message_includes_path(self, tmp_path: Path) -> None:
        """The error message names the offending path to aid debugging."""
        missing = tmp_path / "nope.sql"
        with pytest.raises(ValueError, match=str(missing)):
            read_file(missing)

    def test_string_missing_path_raises(self, tmp_path: Path) -> None:
        """A missing path supplied as a string is also rejected with ``ValueError``."""
        with pytest.raises(ValueError, match="could not be found"):
            read_file(str(tmp_path / "missing.txt"))
