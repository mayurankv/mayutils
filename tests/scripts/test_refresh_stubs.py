"""Tests for the plotly overlay orchestration in ``mayutils.scripts.refresh_stubs``.

The refresher CLI depends on the ``cli`` and ``console`` extras (Typer
and rich), so the module is skipped at collection time when they are not
importable. The overlay step is exercised by faking ``pyright`` and
spying on the plotly generator rather than running either for real.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

pytest.importorskip("typer")
pytest.importorskip("rich")

from typer.testing import CliRunner

from mayutils.scripts import generate_plotly_stubs, refresh_stubs

if TYPE_CHECKING:
    from pathlib import Path


runner = CliRunner()


def _fake_pyright_success(
    package: str,
    /,
    *,
    typings: Path,
) -> subprocess.CompletedProcess[str]:
    """Stand in for :func:`refresh_stubs.run_pyright`, reporting unconditional success.

    Returns
    -------
        A completed process with return code ``0`` and empty output.
    """
    del package, typings
    return subprocess.CompletedProcess(args=["pyright"], returncode=0, stdout="", stderr="")


class TestPlotlyOverlayOrchestration:
    """The refresher runs the plotly overlay exactly when pyright refreshed ``plotly``."""

    @pytest.fixture(autouse=True)
    def _passthrough_filters(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Let every discovered package survive the refresh filters and fake ``pyright``."""

        def _installed(_package: str, /) -> bool:
            return True

        def _untyped(_package: str, /) -> bool:
            return False

        monkeypatch.setattr(refresh_stubs, "is_installed", _installed)
        monkeypatch.setattr(refresh_stubs, "ships_py_typed", _untyped)
        monkeypatch.setattr(refresh_stubs, "types_package_installed", _untyped)
        monkeypatch.setattr(refresh_stubs, "is_namespace_package", _untyped)
        monkeypatch.setattr(refresh_stubs, "run_pyright", _fake_pyright_success)

    def test_overlay_runs_when_plotly_refreshed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """``plotly`` in the refreshed set triggers the plotly stub overlay."""
        captured: list[bool] = []

        def _only_plotly(_typings: Path, /) -> list[str]:
            return ["plotly"]

        def _spy(*_args: object, dry_run: bool = False) -> int:
            captured.append(dry_run)
            return 4

        monkeypatch.setattr(refresh_stubs, "stub_packages", _only_plotly)
        monkeypatch.setattr(generate_plotly_stubs, "generate_stubs", _spy)

        result = runner.invoke(refresh_stubs.app, [str(tmp_path)])

        assert result.exit_code == 0
        assert captured == [False]

    def test_overlay_skipped_when_plotly_not_refreshed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """A refresh that never touches ``plotly`` does not run the overlay."""
        captured: list[bool] = []

        def _no_plotly(_typings: Path, /) -> list[str]:
            return ["requests"]

        def _spy(*_args: object, dry_run: bool = False) -> int:
            captured.append(dry_run)
            return 4

        monkeypatch.setattr(refresh_stubs, "stub_packages", _no_plotly)
        monkeypatch.setattr(generate_plotly_stubs, "generate_stubs", _spy)

        result = runner.invoke(refresh_stubs.app, [str(tmp_path)])

        assert result.exit_code == 0
        assert captured == []
