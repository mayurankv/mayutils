"""Tests for ``mayutils.data.queries``.

Covers the SQL-template discovery helpers: building the search path with
:func:`get_queries_folders`, loading raw text by bare name / relative path /
absolute path with :func:`read_query`, and placeholder interpolation via
:func:`format_query`. Resolution is exercised against throwaway directories
passed explicitly through ``queries_folders`` so the module-level
:data:`QUERIES_FOLDERS` and the real project tree are never touched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mayutils.data.queries import (
    QUERIES_FOLDERS,
    format_query,
    get_queries_folders,
    read_query,
)


def _write_query(folder: Path, name: str, text: str) -> Path:
    """Create a query file under ``folder`` and return its path.

    Parameters
    ----------
    folder
        Directory to create the file in; created if absent.
    name
        File name (with extension) to create.
    text
        Contents to write to the file.

    Returns
    -------
        The created file path.
    """
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


class TestQueriesFoldersConstant:
    """Tests for the module-level :data:`QUERIES_FOLDERS` search path."""

    def test_is_tuple_of_paths(self) -> None:
        """The constant is a tuple of :class:`~pathlib.Path` entries."""
        assert isinstance(QUERIES_FOLDERS, tuple)
        assert all(isinstance(folder, Path) for folder in QUERIES_FOLDERS)

    def test_includes_module_directory_last(self) -> None:
        """The directory containing the module is always the final fallback."""
        assert QUERIES_FOLDERS[-1].name == "queries"

    def test_matches_fresh_computation(self) -> None:
        """The cached constant equals a fresh call to :func:`get_queries_folders`."""
        assert get_queries_folders() == QUERIES_FOLDERS


class TestGetQueriesFolders:
    """Tests for :func:`get_queries_folders` — the ordered search path builder."""

    def test_returns_tuple_of_paths(self) -> None:
        """The result is a tuple whose entries are all paths."""
        folders = get_queries_folders()
        assert isinstance(folders, tuple)
        assert all(isinstance(folder, Path) for folder in folders)

    def test_project_queries_takes_precedence(self) -> None:
        """The project ``queries/`` directory is ordered ahead of the module fallback."""
        folders = get_queries_folders()
        assert folders[0].name == "queries"
        assert folders[0] != folders[-1]

    def test_includes_per_package_data_queries(self) -> None:
        """Every ``src`` package contributes a ``data/queries`` search entry."""
        folders = get_queries_folders()
        data_query_folders = [folder for folder in folders if folder.parent.name == "data" and folder.name == "queries"]
        assert any("mayutils" in folder.parts for folder in data_query_folders)


class TestReadQuery:
    """Tests for :func:`read_query` — locating and loading raw query text."""

    def test_reads_by_bare_name_with_default_suffix(self, tmp_path: Path) -> None:
        """A bare name resolves against the search path with ``.sql`` appended."""
        _write_query(tmp_path, "revenue.sql", "SELECT 1")
        assert read_query("revenue", queries_folders=(tmp_path,)) == "SELECT 1"

    def test_reads_with_custom_default_suffix(self, tmp_path: Path) -> None:
        """A non-default suffix is honoured when the name has no extension."""
        _write_query(tmp_path, "report.txt", "raw text")
        assert read_query("report", queries_folders=(tmp_path,), default_suffix="txt") == "raw text"

    def test_explicit_suffix_is_not_overridden(self, tmp_path: Path) -> None:
        """A name that already carries an extension keeps it untouched."""
        _write_query(tmp_path, "named.sql", "explicit")
        assert read_query("named.sql", queries_folders=(tmp_path,)) == "explicit"

    def test_reads_existing_absolute_path_directly(self, tmp_path: Path) -> None:
        """An already-resolvable path is read without consulting the search folders."""
        path = _write_query(tmp_path, "direct.sql", "direct hit")
        assert read_query(path, queries_folders=()) == "direct hit"

    def test_reads_relative_path_with_subdirectory(self, tmp_path: Path) -> None:
        """A relative path containing subdirectories resolves under a search folder."""
        _write_query(tmp_path / "sub", "nested.sql", "nested query")
        assert read_query(Path("sub") / "nested.sql", queries_folders=(tmp_path,)) == "nested query"

    def test_first_matching_folder_wins(self, tmp_path: Path) -> None:
        """Earlier folders in the search path take precedence over later ones."""
        high = tmp_path / "high"
        low = tmp_path / "low"
        _write_query(high, "dup.sql", "from high")
        _write_query(low, "dup.sql", "from low")
        assert read_query("dup", queries_folders=(high, low)) == "from high"

    def test_preserves_whitespace_and_newlines(self, tmp_path: Path) -> None:
        """The raw file text, including trailing newline, is returned verbatim."""
        text = "SELECT *\nFROM t\n  WHERE x = 1\n"
        _write_query(tmp_path, "spaced.sql", text)
        assert read_query("spaced", queries_folders=(tmp_path,)) == text

    def test_missing_query_raises_value_error(self, tmp_path: Path) -> None:
        """An unresolvable query raises ``ValueError`` naming the searched folders."""
        with pytest.raises(ValueError, match="No query") as exc_info:
            read_query("missing", queries_folders=(tmp_path,))
        assert str(tmp_path) in str(exc_info.value)

    def test_str_path_input_is_accepted(self, tmp_path: Path) -> None:
        """A plain ``str`` identifier is normalised to a path and resolved."""
        _write_query(tmp_path, "stringy.sql", "string input")
        assert read_query("stringy.sql", queries_folders=(tmp_path,)) == "string input"


class TestFormatQuery:
    """Tests for :func:`format_query` — load-then-``str.format`` convenience wrapper."""

    def test_substitutes_single_placeholder(self, tmp_path: Path) -> None:
        """A single ``{name}`` placeholder is replaced by the matching keyword."""
        _write_query(tmp_path, "region.sql", "SELECT * FROM loans WHERE region = '{region}'")
        rendered = format_query("region", queries_folders=(tmp_path,), region="London")
        assert rendered == "SELECT * FROM loans WHERE region = 'London'"

    def test_substitutes_multiple_placeholders(self, tmp_path: Path) -> None:
        """Multiple placeholders are all interpolated from keyword arguments."""
        _write_query(tmp_path, "revenue.sql", "SELECT * FROM {schema}.revenue WHERE dt >= '{start_date}'")
        rendered = format_query(
            "revenue",
            queries_folders=(tmp_path,),
            schema="analytics",
            start_date="2024-01-01",
        )
        assert rendered == "SELECT * FROM analytics.revenue WHERE dt >= '2024-01-01'"

    def test_no_placeholders_returns_text_unchanged(self, tmp_path: Path) -> None:
        """Query text without placeholders is returned as-is."""
        _write_query(tmp_path, "static.sql", "SELECT 1")
        assert format_query("static", queries_folders=(tmp_path,)) == "SELECT 1"

    def test_non_string_value_is_stringified(self, tmp_path: Path) -> None:
        """Non-string substitutions are coerced via ``str`` by ``str.format``."""
        _write_query(tmp_path, "limit.sql", "SELECT * FROM t LIMIT {n}")
        assert format_query("limit", queries_folders=(tmp_path,), n=10) == "SELECT * FROM t LIMIT 10"

    def test_missing_placeholder_raises_key_error(self, tmp_path: Path) -> None:
        """A placeholder without a matching keyword propagates ``KeyError``."""
        _write_query(tmp_path, "needs_arg.sql", "SELECT * FROM {schema}.t")
        with pytest.raises(KeyError):
            format_query("needs_arg", queries_folders=(tmp_path,))

    def test_positional_placeholder_raises_index_error(self, tmp_path: Path) -> None:
        """A positional ``{0}`` placeholder raises ``IndexError`` (keyword-only support)."""
        _write_query(tmp_path, "positional.sql", "SELECT {0}")
        with pytest.raises(IndexError):
            format_query("positional", queries_folders=(tmp_path,))

    def test_unresolvable_query_propagates_value_error(self, tmp_path: Path) -> None:
        """A missing template surfaces the ``ValueError`` raised by :func:`read_query`."""
        with pytest.raises(ValueError, match="No query"):
            format_query("absent", queries_folders=(tmp_path,), x="y")

    def test_empty_search_path_with_bare_name_raises(self) -> None:
        """A bare name with an empty search path cannot resolve and raises ``ValueError``."""
        with pytest.raises(ValueError, match="No query"):
            format_query("nowhere", queries_folders=())
