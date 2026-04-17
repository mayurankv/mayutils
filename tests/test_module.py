"""Package-level smoke tests for ``mayutils``."""

from __future__ import annotations


def test_version_is_string() -> None:
    """``mayutils.__version__`` is populated from installed distribution metadata."""
    import mayutils  # noqa: PLC0415

    assert isinstance(mayutils.__version__, str)
    assert mayutils.__version__


def test_setup_is_idempotent() -> None:
    """Calling :func:`mayutils.setup` twice is safe and a no-op on the second call."""
    import mayutils  # noqa: PLC0415

    mayutils.setup()
    mayutils.setup()
