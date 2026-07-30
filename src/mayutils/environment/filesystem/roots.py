"""
Provide repository and module root resolution helpers.

This submodule collects the path-discovery primitives used across
``mayutils``: locating the enclosing git working tree, resolving the
directory of the calling module, and returning the on-disk directory
that backs an imported package. The git helpers import ``gitpython``
lazily so the rest of the module stays usable even when the
``filesystem`` optional dependency group is not installed.

See Also
--------
mayutils.environment.filesystem.reading : Text-file I/O helpers built on
    top of the paths resolved here.
mayutils.environment.filesystem.encoding : Path serialisation helpers
    that typically operate on directories produced by these roots.
mayutils.environment.filesystem.metadata : File metadata queries
    (for example staleness checks) whose inputs usually originate from
    these roots.

Examples
--------
>>> from pathlib import Path
>>> from mayutils.environment.filesystem.roots import get_root
>>> root = get_root()
>>> isinstance(root, Path)
True
>>> (root / "pyproject.toml").exists()
True
"""

import inspect
from pathlib import Path


def get_root() -> Path:
    """
    Resolve the root directory of the enclosing git repository.

    The current working directory is walked upwards until a ``.git``
    directory is found, and the working tree of that repository is
    returned. When ``gitpython`` is not installed, or the current
    working directory is not part of any git repository, the function
    falls back to the current working directory. This makes it safe to
    call from scripts that may or may not be run from inside a
    checkout, regardless of whether the optional ``filesystem`` extra
    has been installed in the active environment.

    Returns
    -------
        Working-tree root of the repository that contains the current
        working directory, or the current working directory itself
        when no repository is detected or ``gitpython`` is unavailable.

    See Also
    --------
    git.Repo : Underlying git repository wrapper consulted to locate
        the working tree root when ``gitpython`` is installed.
    pathlib.Path : Path abstraction used to represent the returned
        directory on disk.
    get_module_root : Sibling helper that resolves the directory of
        the calling module rather than the repository root.

    Examples
    --------
    >>> from pathlib import Path
    >>> from mayutils.environment.filesystem import get_root
    >>> root = get_root()
    >>> isinstance(root, Path)
    True
    >>> (root / "pyproject.toml").exists()
    True
    """
    try:
        from git import InvalidGitRepositoryError, Repo
    except ImportError:
        return Path.cwd()

    try:
        return Path(
            Repo(
                path=".",
                search_parent_directories=True,
            ).working_dir
        )
    except InvalidGitRepositoryError:
        return Path.cwd()


def get_module_root() -> Path:
    """
    Resolve the directory of the module that invoked this function.

    The caller's frame is introspected to determine the source file of
    the module issuing the call, and the directory containing that
    file is returned. When the calling context is not associated with
    a source file (for example, an interactive REPL or an
    eval-generated frame), the repository root returned by
    :func:`get_root` is used instead. The behaviour is chosen so that
    notebook-style callers still receive a meaningful directory to
    anchor relative lookups against.

    Returns
    -------
        Directory containing the source file of the caller, or the
        repository root when no caller source file can be determined.

    See Also
    --------
    get_root : Fallback used when the caller does not have an
        associated source file on disk.
    pathlib.Path : Path abstraction used to represent the returned
        directory on disk.
    inspect.getmodule : Reflection primitive used internally to walk
        back to the module issuing the call.

    Examples
    --------
    >>> from pathlib import Path
    >>> from mayutils.environment.filesystem import get_module_root
    >>> module_root = get_module_root()
    >>> isinstance(module_root, Path)
    True
    >>> module_root.is_dir()
    True
    """
    defining_module = inspect.getmodule(inspect.currentframe())
    return Path(defining_module.__file__).parent if defining_module is not None and defining_module.__file__ is not None else get_root()


def get_module_path(
    module: object,
    /,
) -> Path:
    """
    Return the filesystem directory backing a package module.

    The first entry of the module's ``__path__`` attribute is
    returned. This attribute is populated by the Python import
    machinery for package modules, so this helper is intended for
    packages rather than plain modules. Namespace packages with
    multiple path entries are handled by taking the first entry only,
    which matches the directory that will be searched first when
    resolving submodules.

    Parameters
    ----------
    module
        Imported module (typically a package) whose on-disk location
        should be resolved. Must expose a non-empty ``__path__``
        attribute.

    Returns
    -------
        Directory from which ``module`` was loaded.

    Raises
    ------
    ValueError
        If ``module`` has no ``__path__`` attribute, indicating it is
        not a package, or if ``__path__`` is present but empty and so
        does not point at any directory.

    See Also
    --------
    get_module_root : Companion helper that resolves the directory of
        the currently executing module rather than an explicit one.
    pathlib.Path : Path abstraction used to represent the returned
        directory on disk.
    get_root : Repository-level analogue that locates the enclosing
        git working tree instead of a package directory.

    Examples
    --------
    >>> import mayutils
    >>> from mayutils.environment.filesystem import get_module_path
    >>> package_dir = get_module_path(mayutils)
    >>> isinstance(package_dir, Path)
    True
    >>> package_dir.name
    'mayutils'
    """
    paths = getattr(module, "__path__", None)
    if paths is None:
        msg = f"Module {module} does not have a __path__ attribute."
        raise ValueError(msg)

    try:
        return Path(paths[0])
    except IndexError as err:
        msg = f"Module {module} does not have a valid path."
        raise ValueError(msg) from err


__all__ = [
    "get_module_path",
    "get_module_root",
    "get_root",
]
