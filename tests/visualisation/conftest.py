"""Shared fixtures for ``mayutils.visualisation`` tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from IPython.core.interactiveshell import InteractiveShell


@pytest.fixture(scope="session")
def ip() -> InteractiveShell:
    """
    Boot a real IPython :class:`InteractiveShell` once per test session.

    :func:`IPython.testing.globalipapp.start_ipython` returns the singleton
    test shell on repeat calls, so the fixture is safe to depend on from
    many tests in the same session.

    Returns
    -------
    InteractiveShell
        The session-scoped IPython shell installed by
        :func:`IPython.testing.globalipapp.start_ipython`.
    """
    pytest.importorskip("IPython")
    from IPython.testing.globalipapp import start_ipython  # noqa: PLC0415

    shell = start_ipython()
    if shell is None:
        pytest.skip("IPython test shell could not be initialised.")

    return shell
