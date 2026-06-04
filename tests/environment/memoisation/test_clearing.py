"""Tests for ``mayutils.environment.memoisation.clearing``.

Covers :func:`clear_cache`: clearing in-memory stores, scanning a cache
folder with prefix/suffix/TTL filters, the ``.gitkeep`` exclusion, dry-run
mode, and the missing-folder short-circuit. Requires the ``datetime``
extra (pendulum) via the staleness check.
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

import pytest

pytest.importorskip("pendulum")

from mayutils.environment.memoisation.clearing import clear_cache
from mayutils.environment.memoisation.memory import MemoryStore
from mayutils.objects.datetime import Duration

if TYPE_CHECKING:
    from pathlib import Path


def _populate(folder: Path, names: list[str]) -> list[Path]:
    """Create empty files under ``folder`` and return their paths.

    Parameters
    ----------
    folder
        Directory to create the files in; created if absent.
    names
        File names (with extensions) to create.

    Returns
    -------
        The created file paths, in the order of ``names``.
    """
    folder.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name in names:
        path = folder / name
        path.write_text("x", encoding="utf-8")
        paths.append(path)
    return paths


class TestClearStores:
    """Tests for clearing in-memory stores passed to :func:`clear_cache`."""

    def test_stores_are_cleared(self, tmp_path: Path) -> None:
        """In-memory stores are emptied when not in dry-run mode."""
        store = MemoryStore[int]()
        store.put("k", value=1)
        clear_cache(stores=[store], cache_folder=tmp_path)
        assert store.cache_info().currsize == 0

    def test_dry_run_does_not_clear_stores(self, tmp_path: Path) -> None:
        """Dry-run mode leaves in-memory stores untouched."""
        store = MemoryStore[int]()
        store.put("k", value=1)
        clear_cache(stores=[store], cache_folder=tmp_path, dry_run=True)
        assert store.cache_info().currsize == 1


class TestClearFiles:
    """Tests for the cache-folder scan and deletion in :func:`clear_cache`."""

    def test_missing_folder_returns_empty(self, tmp_path: Path) -> None:
        """A non-existent cache folder short-circuits to an empty list."""
        assert clear_cache(cache_folder=tmp_path / "does_not_exist") == []

    def test_all_files_deleted_without_filters(self, tmp_path: Path) -> None:
        """With no filters, every cache file is deleted and reported."""
        paths = _populate(tmp_path, ["a.pkl", "b.parquet"])
        deleted = clear_cache(cache_folder=tmp_path)
        assert set(deleted) == set(paths)
        assert not any(path.is_file() for path in paths)

    def test_recurses_into_subdirectories(self, tmp_path: Path) -> None:
        """Files in per-function subfolders are found via recursive globbing."""
        nested = _populate(tmp_path / "func", ["k.pkl"])
        deleted = clear_cache(cache_folder=tmp_path)
        assert deleted == nested
        assert not nested[0].is_file()

    def test_gitkeep_is_preserved(self, tmp_path: Path) -> None:
        """A ``.gitkeep`` marker is never deleted."""
        _populate(tmp_path, [".gitkeep"])
        deleted = clear_cache(cache_folder=tmp_path)
        assert deleted == []
        assert (tmp_path / ".gitkeep").is_file()

    def test_prefix_filter(self, tmp_path: Path) -> None:
        """Only files whose name starts with the prefix are deleted."""
        _populate(tmp_path, ["keep_me.pkl", "drop_this.pkl"])
        deleted = clear_cache(cache_folder=tmp_path, prefix="drop")
        assert [path.name for path in deleted] == ["drop_this.pkl"]
        assert (tmp_path / "keep_me.pkl").is_file()

    def test_suffix_filter(self, tmp_path: Path) -> None:
        """Only files whose extension matches the suffix are deleted."""
        _populate(tmp_path, ["a.pkl", "b.parquet"])
        deleted = clear_cache(cache_folder=tmp_path, suffix=".parquet")
        assert [path.name for path in deleted] == ["b.parquet"]
        assert (tmp_path / "a.pkl").is_file()

    def test_ttl_only_deletes_stale_files(self, tmp_path: Path) -> None:
        """With a TTL, only files older than the TTL are deleted."""
        old, fresh = _populate(tmp_path, ["old.pkl", "fresh.pkl"])
        old_time = time.time() - 3600
        os.utime(old, (old_time, old_time))
        deleted = clear_cache(cache_folder=tmp_path, ttl=Duration(minutes=1))
        assert deleted == [old]
        assert not old.is_file()
        assert fresh.is_file()


class TestClearDryRun:
    """Tests for dry-run mode on the file scan."""

    def test_dry_run_reports_without_deleting(self, tmp_path: Path) -> None:
        """Dry-run lists the candidate files but leaves them on disk."""
        paths = _populate(tmp_path, ["a.pkl", "b.pkl"])
        deleted = clear_cache(cache_folder=tmp_path, dry_run=True)
        assert set(deleted) == set(paths)
        assert all(path.is_file() for path in paths)
