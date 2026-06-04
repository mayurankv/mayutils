"""Tests for ``mayutils.scripts.generate_plotly_stubs``.

The plotly stub generator depends on the ``cli`` and ``plotting`` extras
(Typer plus the ``plotly-stubs`` distribution it reads from
``site-packages``), so the module is skipped at collection time when
those are not importable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

pytest.importorskip("typer")
pytest.importorskip("plotly")

from typer.testing import CliRunner

from mayutils.scripts import generate_plotly_stubs

if TYPE_CHECKING:
    from pathlib import Path


runner = CliRunner()


class TestGenerateStubs:
    """Tests for :func:`generate_stubs` — the public orchestration core."""

    def test_dry_run_returns_non_negative_count(self) -> None:
        """A real dry run reads the project stubs and returns a count without writing."""
        total = generate_plotly_stubs.generate_stubs(dry_run=True)

        assert isinstance(total, int)
        assert total >= 0

    def test_returns_zero_without_raising_when_nothing_generated(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """When every sub-generator yields nothing the core returns 0 rather than raising."""

        def _fake_root() -> Path:
            return tmp_path

        def _no_check(_stubs_root: Path) -> None:
            return None

        def _no_list(**_kwargs: object) -> list[str]:
            return []

        def _no_basedatatypes(**_kwargs: object) -> bool:
            return False

        def _no_template(*_args: object, **_kwargs: object) -> list[str]:
            return []

        monkeypatch.setattr(generate_plotly_stubs, "find_stubs_root", _fake_root)
        monkeypatch.setattr(generate_plotly_stubs, "check_upstream", _no_check)
        monkeypatch.setattr(generate_plotly_stubs, "generate_trace_stubs", _no_list)
        monkeypatch.setattr(generate_plotly_stubs, "generate_chart_stubs", _no_list)
        monkeypatch.setattr(generate_plotly_stubs, "generate_basedatatypes_stub", _no_basedatatypes)
        monkeypatch.setattr(generate_plotly_stubs, "generate_template_stubs", _no_template)
        monkeypatch.setattr(generate_plotly_stubs, "generate_subcomponent_stubs", _no_list)

        assert generate_plotly_stubs.generate_stubs(dry_run=True) == 0


class TestGenerateCommand:
    """Tests for the Typer ``generate`` command wrapping :func:`generate_stubs`."""

    def test_command_forwards_dry_run_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The command delegates to the core, forwarding ``traces_dir`` and ``--dry-run``."""
        captured: dict[str, object] = {}

        def _spy(*_args: object, traces_dir: object = None, dry_run: bool = False) -> int:
            captured["traces_dir"] = traces_dir
            captured["dry_run"] = dry_run
            return 3

        monkeypatch.setattr(generate_plotly_stubs, "generate_stubs", _spy)

        result = runner.invoke(generate_plotly_stubs.app, ["--dry-run"])

        assert result.exit_code == 0
        assert captured["dry_run"] is True
        assert captured["traces_dir"] is not None
