"""Tests for ``mayutils.environment.filesystem.metadata``.

These cover :func:`is_file_stale` — the mtime-versus-TTL freshness
check used by the file-backed caches. The module pulls in
:class:`mayutils.objects.datetime.DateTime`, which depends on
pendulum (the ``datetime`` extra), so the suite is skipped at
collection time when pendulum is not importable.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

pytest.importorskip("pendulum")

from mayutils.environment.filesystem.metadata import is_file_stale
from mayutils.objects.datetime import Duration

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def existing_file(tmp_path: Path) -> Path:
    """Create a small UTF-8 file with a known, freshly-written mtime.

    Returns
    -------
        Path to a regular file inside ``tmp_path`` with current mtime.
    """
    path = tmp_path / "artifact.txt"
    path.write_text("payload", encoding="utf-8")
    return path


class TestNoTTL:
    """Tests for the ``ttl=None`` (no-expiry) contract."""

    def test_none_ttl_is_never_stale(self, existing_file: Path) -> None:
        """A ``None`` TTL disables the check, so the file is always fresh."""
        assert is_file_stale(existing_file, ttl=None) is False

    def test_none_ttl_skips_stat(self, tmp_path: Path) -> None:
        """With ``ttl=None`` the file is not stat'd, so a missing path is still ``False``.

        The early ``None`` return happens before any
        :meth:`pathlib.Path.stat` call, so no :class:`FileNotFoundError`
        is raised even for a non-existent path.
        """
        assert is_file_stale(tmp_path / "missing.txt", ttl=None) is False


class TestFreshFile:
    """Tests for a recently-modified file against a generous TTL."""

    def test_recent_file_within_long_ttl_is_fresh(self, existing_file: Path) -> None:
        """A just-written file is fresh against an hour-long TTL."""
        assert is_file_stale(existing_file, ttl=Duration(seconds=3600)) is False

    def test_accepts_pendulum_duration(self, existing_file: Path) -> None:
        """A pendulum :class:`~pendulum.Duration` TTL is honoured like a timedelta."""
        assert is_file_stale(existing_file, ttl=Duration(hours=1)) is False

    def test_return_type_is_bool(self, existing_file: Path) -> None:
        """The result is a plain :class:`bool`, not a truthy proxy."""
        assert isinstance(is_file_stale(existing_file, ttl=Duration(seconds=3600)), bool)


class TestStaleFile:
    """Tests for files whose age exceeds the configured TTL."""

    def test_old_mtime_exceeds_ttl(self, existing_file: Path) -> None:
        """A file modified well in the past is stale against a short TTL."""
        old = existing_file.stat().st_mtime - 10_000
        os.utime(existing_file, (old, old))
        assert is_file_stale(existing_file, ttl=Duration(seconds=60)) is True

    def test_zero_ttl_is_always_stale(self, existing_file: Path) -> None:
        """A zero TTL means any non-zero age is stale (mtime is strictly in the past)."""
        assert is_file_stale(existing_file, ttl=Duration(seconds=0)) is True

    def test_negative_ttl_is_always_stale(self, existing_file: Path) -> None:
        """A negative TTL can never be satisfied, so the file is stale."""
        assert is_file_stale(existing_file, ttl=Duration(seconds=-1)) is True

    def test_age_just_over_ttl_is_stale(self, existing_file: Path) -> None:
        """A file aged just beyond a small TTL crosses the staleness boundary."""
        old = existing_file.stat().st_mtime - 5
        os.utime(existing_file, (old, old))
        assert is_file_stale(existing_file, ttl=Duration(seconds=2)) is True

    def test_age_within_ttl_is_fresh(self, existing_file: Path) -> None:
        """A file aged less than the TTL is still fresh."""
        old = existing_file.stat().st_mtime - 1
        os.utime(existing_file, (old, old))
        assert is_file_stale(existing_file, ttl=Duration(seconds=3600)) is False


class TestMissingFile:
    """Tests for the documented requirement that the path must exist."""

    def test_missing_file_with_ttl_raises(self, tmp_path: Path) -> None:
        """A real TTL forces a stat, so a missing path raises ``FileNotFoundError``."""
        with pytest.raises(FileNotFoundError):
            is_file_stale(tmp_path / "does-not-exist.txt", ttl=Duration(seconds=10))
