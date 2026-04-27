"""Tests for ``mayutils.visualisation.notebook``.

The suite is split into two halves: the first runs under plain CPython
with no IPython shell active and asserts that every notebook helper
raises ``RuntimeError`` so callers fail fast at the misuse site, and the
second uses an IPython :class:`InteractiveShell` provided by the
session-scoped ``ip`` fixture to exercise the shell-bound code paths.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mayutils.visualisation.notebook import Notebook

if TYPE_CHECKING:
    from IPython.core.interactiveshell import InteractiveShell


class TestOutsideNotebook:
    """Tests for :class:`Notebook` helpers when no IPython shell is active."""

    def test_get_shell_raises_when_no_shell(self) -> None:
        """``get_shell`` raises ``RuntimeError`` when no IPython shell is active."""
        with pytest.raises(RuntimeError, match="No active IPython shell"):
            Notebook.get_shell()

    def test_get_shell_raises_when_get_ipython_returns_none(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``get_shell`` raises ``RuntimeError`` even when IPython is importable but no shell exists."""
        from IPython.core import getipython  # noqa: PLC0415

        monkeypatch.setattr(target=getipython, name="get_ipython", value=lambda: None)
        with pytest.raises(RuntimeError, match="No active IPython shell"):
            Notebook.get_shell()

    def test_setup_raises_when_no_shell(self) -> None:
        """``setup`` propagates the ``get_shell`` ``RuntimeError`` to callers."""
        with pytest.raises(RuntimeError, match="No active IPython shell"):
            Notebook.setup(printing=False)

    def test_apply_css_raises_when_no_shell(self) -> None:
        """``apply_css`` refuses to inject styles outside an IPython shell."""
        with pytest.raises(RuntimeError, match="No active IPython shell"):
            Notebook.apply_css(".dataframe {font-family: monospace;}")

    def test_write_markdown_raises_when_no_shell(self) -> None:
        """``write_markdown`` refuses to render outside an IPython shell."""
        with pytest.raises(RuntimeError, match="No active IPython shell"):
            Notebook.write_markdown("# heading")

    def test_write_latex_raises_when_no_shell(self) -> None:
        """``write_latex`` refuses to render outside an IPython shell."""
        with pytest.raises(RuntimeError, match="No active IPython shell"):
            Notebook.write_latex(r"E = mc^{2}")

    def test_mayutils_setup_swallows_no_shell(self) -> None:
        """:func:`mayutils.setup` skips the notebook bootstrap when no shell is active."""
        import mayutils  # noqa: PLC0415

        mayutils.setup()


class TestWithLiveShell:
    """Tests for :class:`Notebook` helpers using a real IPython shell."""

    def test_get_shell_returns_active_shell(self, ip: InteractiveShell) -> None:
        """``get_shell`` returns the live shell when one is running."""
        assert Notebook.get_shell() is ip

    def test_setup_runs_with_live_shell(self, ip: InteractiveShell) -> None:
        """``setup`` completes without raising when an IPython shell is active."""
        del ip
        Notebook.setup(printing=False)

    def test_write_markdown_runs_with_live_shell(self, ip: InteractiveShell) -> None:
        """``write_markdown`` displays each fragment without raising."""
        del ip
        Notebook.write_markdown("# heading", "*emphasis*")

    def test_write_latex_runs_with_live_shell(self, ip: InteractiveShell) -> None:
        """``write_latex`` displays each math source without raising."""
        del ip
        Notebook.write_latex(r"E = mc^{2}", r"a^{2} + b^{2} = c^{2}")

    def test_apply_css_runs_with_live_shell(self, ip: InteractiveShell) -> None:
        """``apply_css`` accepts both injection methods without raising."""
        del ip
        Notebook.apply_css(".dataframe {font-family: monospace;}", method="js")
        Notebook.apply_css(".dataframe {color: red;}", method="html")
