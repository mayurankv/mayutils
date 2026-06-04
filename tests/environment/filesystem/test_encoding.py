"""Tests for ``mayutils.environment.filesystem.encoding``.

These cover the :func:`encode_path` / :func:`decode_path` pair: the
``/`` → ``#`` separator remapping, percent-encoding of reserved
characters, and the round-trip guarantee that ``decode_path`` inverts
``encode_path`` for arbitrary inputs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mayutils.environment.filesystem.encoding import decode_path, encode_path


class TestEncodePath:
    """Tests for :func:`encode_path` — flattens a path to a filename-safe token."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("data/raw/file.csv", "data%23raw%23file.csv"),
            ("logs/2026-04-22.log", "logs%232026-04-22.log"),
            ("plain.txt", "plain.txt"),
            ("a/b/c.txt", "a%23b%23c.txt"),
        ],
    )
    def test_known_tokens(self, raw: str, expected: str) -> None:
        """Separators map to ``#`` (percent-encoded) and non-separated names pass through."""
        assert encode_path(raw) == expected

    def test_no_raw_slash_in_output(self) -> None:
        """The encoded token never contains a literal ``/`` separator."""
        assert "/" not in encode_path("deeply/nested/path/file.txt")

    def test_space_is_percent_encoded(self) -> None:
        """Spaces are escaped by URL quoting rather than left literal."""
        assert encode_path("my file.txt") == "my%20file.txt"

    def test_percent_is_escaped(self) -> None:
        """A literal ``%`` is escaped to ``%25`` so it round-trips cleanly."""
        assert encode_path("100%.txt") == "100%25.txt"

    def test_backslash_is_not_a_separator(self) -> None:
        """Only forward slashes are remapped; a backslash is merely quoted."""
        assert encode_path("a\\b") == "a%5Cb"

    def test_accepts_path_object(self) -> None:
        """A :class:`~pathlib.Path` input is serialised identically to its string form."""
        assert encode_path(Path("data/raw/file.csv")) == encode_path("data/raw/file.csv")

    def test_empty_string(self) -> None:
        """An empty string encodes to an empty token."""
        assert encode_path("") == ""


class TestDecodePath:
    """Tests for :func:`decode_path` — reconstructs a path from a token."""

    @pytest.mark.parametrize(
        ("token", "expected"),
        [
            ("data%23raw%23file.csv", Path("data/raw/file.csv")),
            ("logs%232026-04-22.log", Path("logs/2026-04-22.log")),
            ("plain.txt", Path("plain.txt")),
            ("my%20file.txt", Path("my file.txt")),
        ],
    )
    def test_known_paths(self, token: str, expected: Path) -> None:
        """Encoded tokens decode back to the original path structure."""
        assert decode_path(token) == expected

    def test_returns_path_instance(self) -> None:
        """The decoder always returns a :class:`~pathlib.Path`."""
        assert isinstance(decode_path("plain.txt"), Path)

    def test_empty_string_decodes_to_dot(self) -> None:
        """An empty token decodes to ``Path('.')``, matching ``Path('')`` semantics."""
        assert decode_path("") == Path()


class TestRoundTrip:
    """Tests that :func:`decode_path` inverts :func:`encode_path`."""

    @pytest.mark.parametrize(
        "raw",
        [
            "data/raw/file.csv",
            "logs/2026-04-22.log",
            "plain.txt",
            "my file with spaces.txt",
            "weird/100%/path.txt",
            "a/b/c/d/e/f.parquet",
            "café/naïve.txt",
        ],
    )
    def test_string_round_trip(self, raw: str) -> None:
        """Encoding then decoding a separator-only path yields the equivalent path.

        Inputs here deliberately contain no literal ``#`` (see
        :meth:`TestRoundTrip.test_literal_hash_in_source_is_lossy` for why).
        """
        assert decode_path(encode_path(raw)) == Path(raw)

    @pytest.mark.parametrize(
        "raw",
        [
            "data/raw/file.csv",
            "plain.txt",
            "a/b/c.txt",
        ],
    )
    def test_path_round_trip_str_equal(self, raw: str) -> None:
        """The round-trip preserves the original string representation."""
        assert str(decode_path(encode_path(raw))) == raw

    def test_literal_hash_in_source_is_lossy(self) -> None:
        """A literal ``#`` in the source path does *not* round-trip (current behaviour).

        :func:`encode_path` remaps ``/`` to a literal ``#`` *before*
        URL-quoting, and :func:`urllib.parse.quote` also escapes a literal
        ``#`` to ``%23`` — the same token the separator becomes. On decode
        both are unquoted to ``#`` and then mapped back to ``/``, so a source
        ``#`` is indistinguishable from a separator and surfaces as ``/``.
        This documents the round-trip's known limitation rather than
        asserting a desirable property.
        """
        assert decode_path(encode_path("dir/a#b.txt")) == Path("dir/a/b.txt")
