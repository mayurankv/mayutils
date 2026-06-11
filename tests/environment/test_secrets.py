"""Tests for ``mayutils.environment.secrets``."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

pytest.importorskip("dotenv")

from mayutils.environment import secrets
from mayutils.environment.secrets import load_secrets

if TYPE_CHECKING:
    from pathlib import Path


def write_env(path: Path, contents: str) -> Path:
    """Write ``contents`` to a ``.env`` file at ``path``.

    Returns
    -------
        The path written to, for convenient chaining.
    """
    path.write_text(contents, encoding="utf-8")
    return path


class TestLoadSecretsReturn:
    """Tests for :func:`load_secrets` — the boolean load result."""

    def test_returns_true_when_vars_loaded(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A populated ``.env`` file injects variables and returns ``True``."""
        monkeypatch.delenv("ALPHA", raising=False)
        env_file = write_env(tmp_path / ".env", "ALPHA=one\nBETA=two\n")

        assert load_secrets(env_file=env_file) is True
        assert secrets.__dict__  # module imported cleanly

    def test_returns_false_for_missing_file(
        self,
        tmp_path: Path,
    ) -> None:
        """Pointing at a non-existent file is a no-op returning ``False``."""
        missing = tmp_path / "does-not-exist.env"

        assert load_secrets(env_file=missing) is False

    def test_returns_false_for_empty_file(
        self,
        tmp_path: Path,
    ) -> None:
        """An empty ``.env`` file loads nothing and returns ``False``."""
        env_file = write_env(tmp_path / ".env", "")

        assert load_secrets(env_file=env_file) is False


class TestLoadSecretsValues:
    """Tests for :func:`load_secrets` — the values promoted into ``os.environ``."""

    def test_injects_into_environ(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Key/value pairs from the file appear in ``os.environ``."""
        monkeypatch.delenv("FROM_FILE", raising=False)
        env_file = write_env(tmp_path / ".env", "FROM_FILE=value\n")

        load_secrets(env_file=env_file)
        import os

        assert os.environ["FROM_FILE"] == "value"

    @pytest.mark.parametrize(
        ("line", "key", "expected"),
        [
            ("PLAIN=hello", "PLAIN", "hello"),
            ('QUOTED="spaced value"', "QUOTED", "spaced value"),
            ("EMPTY=", "EMPTY", ""),
            ("WITH_EQUALS=a=b=c", "WITH_EQUALS", "a=b=c"),
        ],
    )
    def test_value_parsing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        line: str,
        key: str,
        expected: str,
    ) -> None:
        """Plain, quoted, empty and embedded-equals values parse correctly."""
        monkeypatch.delenv(key, raising=False)
        env_file = write_env(tmp_path / ".env", f"{line}\n")

        load_secrets(env_file=env_file)
        import os

        assert os.environ[key] == expected


class TestLoadSecretsPrecedence:
    """Tests for :func:`load_secrets` — environment beats file contents."""

    def test_existing_env_var_is_not_overwritten(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A variable already in ``os.environ`` takes precedence over the file."""
        monkeypatch.setenv("PRECEDENCE", "from-shell")
        env_file = write_env(tmp_path / ".env", "PRECEDENCE=from-file\n")

        load_secrets(env_file=env_file)
        import os

        assert os.environ["PRECEDENCE"] == "from-shell"

    def test_new_keys_still_loaded_alongside_precedence(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Existing keys are preserved while genuinely new keys are still injected."""
        monkeypatch.setenv("KEEP", "shell")
        monkeypatch.delenv("FRESH", raising=False)
        env_file = write_env(tmp_path / ".env", "KEEP=file\nFRESH=file\n")

        load_secrets(env_file=env_file)
        import os

        assert os.environ["KEEP"] == "shell"
        assert os.environ["FRESH"] == "file"


class TestLoadSecretsDiscovery:
    """Tests for :func:`load_secrets` — auto-discovery when no path is given."""

    def test_none_delegates_to_find_dotenv(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """With ``env_file=None`` the path is resolved via :func:`dotenv.find_dotenv`."""
        monkeypatch.delenv("DISCOVERED", raising=False)
        discovered = write_env(tmp_path / ".env", "DISCOVERED=yes\n")
        monkeypatch.setattr(secrets, "find_dotenv", lambda: str(discovered))

        assert load_secrets() is True
        import os

        assert os.environ["DISCOVERED"] == "yes"

    def test_none_with_no_file_found_returns_false(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When discovery finds nothing the loader degrades to a ``False`` no-op."""
        monkeypatch.setattr(secrets, "find_dotenv", lambda: "")

        assert load_secrets() is False
