"""Tests for ``mayutils.environment.filesystem.roots``.

These cover the three path-discovery primitives:

* :func:`get_root` — walk up to the enclosing git working tree, with a
  cwd fallback when there is no repository (or no gitpython).
* :func:`get_module_root` — directory of the module backing the call.
* :func:`get_module_path` — on-disk directory of an imported package.

The git helpers depend on gitpython (the ``filesystem`` extra), so the
suite is skipped at collection time when ``git`` is not importable. The
git-aware tests build throwaway repositories under ``tmp_path`` via
``git init`` and never touch the real checkout this code lives in.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("git")

import git

import mayutils
from mayutils.environment.filesystem import roots
from mayutils.environment.filesystem.roots import (
    get_module_path,
    get_module_root,
    get_root,
)


def _git_init(path: Path) -> None:
    """Initialise a throwaway git repository at ``path``."""
    git.Repo.init(path=path)


class TestGetRootFound:
    """Tests for :func:`get_root` when the cwd lives inside a git repository."""

    def test_returns_repo_root_from_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Called from the repository root, it returns that root."""
        _git_init(tmp_path)
        monkeypatch.chdir(tmp_path)
        assert get_root().resolve() == tmp_path.resolve()

    def test_returns_repo_root_from_nested_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Called from a nested subdirectory, it walks up to the working tree root."""
        _git_init(tmp_path)
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        assert get_root().resolve() == tmp_path.resolve()

    def test_returns_path_instance(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The returned value is a :class:`~pathlib.Path`."""
        _git_init(tmp_path)
        monkeypatch.chdir(tmp_path)
        assert isinstance(get_root(), Path)


class TestGetRootFallback:
    """Tests for :func:`get_root` when no repository or gitpython is available."""

    def test_no_repo_falls_back_to_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Outside any git repository, the current working directory is returned."""
        monkeypatch.chdir(tmp_path)
        assert get_root().resolve() == tmp_path.resolve()

    def test_missing_gitpython_falls_back_to_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When ``import git`` fails, the helper degrades to the cwd even inside a repo.

        The lazy ``from git import ...`` inside :func:`get_root` is forced to
        raise :class:`ImportError` by removing ``git`` from ``sys.modules`` and
        blocking its (re-)import, exercising the ``except ImportError`` branch
        without uninstalling the optional dependency.
        """
        _git_init(tmp_path)
        monkeypatch.chdir(tmp_path)

        monkeypatch.delitem(sys.modules, "git", raising=False)
        monkeypatch.setattr(sys, "meta_path", [_ImportBlocker("git"), *sys.meta_path])

        assert get_root().resolve() == tmp_path.resolve()


class _ImportBlocker:
    """A ``sys.meta_path`` finder that makes importing one module fail."""

    def __init__(self, blocked: str, /) -> None:
        self._blocked = blocked

    def find_spec(
        self,
        name: str,
        path: object = None,
        target: object = None,
    ) -> None:
        """Raise :class:`ImportError` for the blocked module, else defer.

        Returning ``None`` (the implicit fall-through) tells the import system
        to consult the next finder for any module other than the blocked one.

        Raises
        ------
        ImportError
            When ``name`` is the blocked module.
        """
        del path, target
        if name == self._blocked or name.startswith(f"{self._blocked}."):
            msg = f"import of {name} blocked for testing"
            raise ImportError(msg, name=name)


class TestGetModuleRoot:
    """Tests for :func:`get_module_root` — directory of the resolved module."""

    def test_returns_path_instance(self) -> None:
        """The returned value is a :class:`~pathlib.Path`."""
        assert isinstance(get_module_root(), Path)

    def test_returns_existing_directory(self) -> None:
        """The resolved root is an existing directory on disk."""
        assert get_module_root().is_dir()

    def test_resolves_to_roots_module_directory(self) -> None:
        """It returns the directory of ``roots.py`` itself (current behaviour).

        :func:`get_module_root` introspects ``inspect.currentframe()`` and
        resolves it via :func:`inspect.getmodule`, which yields the module the
        call site is *defined in* — always :mod:`mayutils.environment.filesystem.roots`
        — rather than an arbitrary external caller. The directory is therefore
        the ``filesystem`` package directory regardless of who calls it.
        """
        assert get_module_root() == Path(roots.__file__).parent
        assert get_module_root().name == "filesystem"


class TestGetModulePath:
    """Tests for :func:`get_module_path` — on-disk directory of a package."""

    def test_top_level_package(self) -> None:
        """A top-level package resolves to its own source directory."""
        package_dir = get_module_path(mayutils)
        assert isinstance(package_dir, Path)
        assert package_dir.name == "mayutils"

    def test_subpackage(self) -> None:
        """A subpackage resolves to its nested directory."""
        import mayutils.environment  # noqa: PLC0415

        assert get_module_path(mayutils.environment).name == "environment"

    def test_directory_exists(self) -> None:
        """The resolved package directory exists on disk."""
        assert get_module_path(mayutils).is_dir()

    def test_uses_first_path_entry(self) -> None:
        """For a multi-entry ``__path__``, the first entry is taken."""
        fake = types.ModuleType("fake_namespace_pkg")
        fake.__dict__["__path__"] = ["/first/entry", "/second/entry"]
        assert get_module_path(fake) == Path("/first/entry")

    def test_non_package_raises(self) -> None:
        """A plain module without ``__path__`` raises ``ValueError``."""
        import math  # noqa: PLC0415

        with pytest.raises(ValueError, match="does not have a __path__ attribute"):
            get_module_path(math)

    def test_empty_path_raises(self) -> None:
        """A package whose ``__path__`` is empty raises ``ValueError``."""
        fake = types.ModuleType("empty_pkg")
        fake.__dict__["__path__"] = []
        with pytest.raises(ValueError, match="does not have a valid path"):
            get_module_path(fake)
