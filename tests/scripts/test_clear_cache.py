"""Tests for ``mayutils.scripts.clear_cache``.

The cache-clearing CLI is a thin Typer wrapper around
:func:`mayutils.environment.memoisation.clearing.clear_cache`. It depends on
the ``cli`` extra (Typer) for the command surface and, via the interactive
delegate, the ``console`` extra (rich); the module is skipped at collection
time when those are not importable.

End-to-end deletion is exercised against ``tmp_path`` so no real user cache is
ever touched, and forwarding of the parsed options to the core function is
verified by monkeypatching :func:`clear_cache` in the script's namespace with
a spy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

pytest.importorskip("typer")
pytest.importorskip("rich")

from typer.testing import CliRunner

from mayutils.scripts import clear_cache

if TYPE_CHECKING:
    from pathlib import Path


runner = CliRunner()


def _write_files(folder: Path, names: list[str]) -> list[Path]:
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


class TestConfirmationPrompt:
    """Tests for the interactive confirmation guard on real deletion."""

    def test_declining_leaves_files_and_exits_cleanly(self, tmp_path: Path) -> None:
        """Answering ``n`` raises ``Exit`` with code 0 and deletes nothing."""
        paths = _write_files(tmp_path, ["a.pkl", "b.pkl"])
        result = runner.invoke(clear_cache.app, [str(tmp_path)], input="n\n")
        assert result.exit_code == 0
        assert all(path.is_file() for path in paths)

    def test_accepting_deletes_files(self, tmp_path: Path) -> None:
        """Answering ``y`` proceeds to delete the cache files."""
        paths = _write_files(tmp_path, ["a.pkl", "b.pkl"])
        result = runner.invoke(clear_cache.app, [str(tmp_path)], input="y\n")
        assert result.exit_code == 0
        assert not any(path.is_file() for path in paths)


class TestForceFlag:
    """Tests for ``--force`` / ``-f`` skipping the confirmation prompt."""

    def test_force_deletes_without_prompt(self, tmp_path: Path) -> None:
        """``--force`` deletes every file without asking for confirmation."""
        paths = _write_files(tmp_path, ["a.pkl", "b.pkl"])
        result = runner.invoke(clear_cache.app, [str(tmp_path), "--force"])
        assert result.exit_code == 0
        assert not any(path.is_file() for path in paths)

    def test_short_force_flag(self, tmp_path: Path) -> None:
        """The ``-f`` short option behaves identically to ``--force``."""
        paths = _write_files(tmp_path, ["a.pkl"])
        result = runner.invoke(clear_cache.app, [str(tmp_path), "-f"])
        assert result.exit_code == 0
        assert not paths[0].is_file()


class TestDryRunFlag:
    """Tests for ``--dry-run`` / ``-n`` previewing without deleting."""

    def test_dry_run_preserves_files_without_prompt(self, tmp_path: Path) -> None:
        """``--dry-run`` lists candidates, deletes nothing, and skips the prompt."""
        paths = _write_files(tmp_path, ["a.pkl", "b.pkl"])
        result = runner.invoke(clear_cache.app, [str(tmp_path), "--dry-run"])
        assert result.exit_code == 0
        assert all(path.is_file() for path in paths)

    def test_short_dry_run_flag(self, tmp_path: Path) -> None:
        """The ``-n`` short option behaves identically to ``--dry-run``."""
        paths = _write_files(tmp_path, ["a.pkl"])
        result = runner.invoke(clear_cache.app, [str(tmp_path), "-n"])
        assert result.exit_code == 0
        assert paths[0].is_file()


class TestNameFilters:
    """Tests for the ``--prefix`` and ``--suffix`` name filters."""

    def test_prefix_filter_only_deletes_matches(self, tmp_path: Path) -> None:
        """``--prefix`` restricts deletion to files whose name starts with it."""
        _write_files(tmp_path, ["drop_this.pkl", "keep_me.pkl"])
        result = runner.invoke(clear_cache.app, [str(tmp_path), "--force", "--prefix", "drop"])
        assert result.exit_code == 0
        assert not (tmp_path / "drop_this.pkl").is_file()
        assert (tmp_path / "keep_me.pkl").is_file()

    def test_suffix_filter_only_deletes_matches(self, tmp_path: Path) -> None:
        """``--suffix`` restricts deletion to files with the matching extension."""
        _write_files(tmp_path, ["a.pkl", "b.parquet"])
        result = runner.invoke(clear_cache.app, [str(tmp_path), "--force", "--suffix", ".parquet"])
        assert result.exit_code == 0
        assert (tmp_path / "a.pkl").is_file()
        assert not (tmp_path / "b.parquet").is_file()

    def test_gitkeep_is_preserved(self, tmp_path: Path) -> None:
        """A ``.gitkeep`` marker survives an unfiltered force-clear."""
        _write_files(tmp_path, [".gitkeep", "a.pkl"])
        result = runner.invoke(clear_cache.app, [str(tmp_path), "--force"])
        assert result.exit_code == 0
        assert (tmp_path / ".gitkeep").is_file()
        assert not (tmp_path / "a.pkl").is_file()


class TestArgumentValidation:
    """Tests for Typer-level validation of the ``folder`` argument."""

    def test_missing_folder_is_usage_error(self, tmp_path: Path) -> None:
        """A non-existent folder fails Typer's ``exists=True`` check with code 2."""
        result = runner.invoke(clear_cache.app, [str(tmp_path / "does_not_exist")])
        assert result.exit_code == 2  # noqa: PLR2004

    def test_file_argument_is_usage_error(self, tmp_path: Path) -> None:
        """Passing a file rather than a directory fails ``dir_okay``/``file_okay``."""
        target = tmp_path / "a_file.pkl"
        target.write_text("x", encoding="utf-8")
        result = runner.invoke(clear_cache.app, [str(target)])
        assert result.exit_code == 2  # noqa: PLR2004


class TestForwardingToCore:
    """Tests that parsed options are forwarded to :func:`clear_cache`."""

    def test_options_forwarded_to_clear_cache(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """All flags map onto the core call, which always runs interactively."""
        captured: dict[str, object] = {}

        def _spy(**kwargs: object) -> list[Path]:
            captured.update(kwargs)
            return []

        monkeypatch.setattr(clear_cache, "clear_cache", _spy)

        result = runner.invoke(
            clear_cache.app,
            [str(tmp_path), "-f", "-p", "model_", "-s", ".parquet", "-n"],
        )

        assert result.exit_code == 0
        assert captured["prefix"] == "model_"
        assert captured["suffix"] == ".parquet"
        assert captured["dry_run"] is True
        assert captured["interactive"] is True
        assert captured["cache_folder"] == tmp_path.resolve()

    def test_defaults_forwarded_when_no_options(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """With ``--force`` only, prefix/suffix default to ``None`` and dry-run is off."""
        captured: dict[str, object] = {}

        def _spy(**kwargs: object) -> list[Path]:
            captured.update(kwargs)
            return []

        monkeypatch.setattr(clear_cache, "clear_cache", _spy)

        result = runner.invoke(clear_cache.app, [str(tmp_path), "--force"])

        assert result.exit_code == 0
        assert captured["prefix"] is None
        assert captured["suffix"] is None
        assert captured["dry_run"] is False
