"""
Provide filesystem and repository-aware path utilities.

The submodules grouped under this package collect small helpers for
working with paths on disk in a way that is aware of the surrounding
git repository, of the calling Python module, and of cache-file
freshness:

* :mod:`mayutils.environment.filesystem.roots` — repository and
  module root discovery (:func:`get_root`, :func:`get_module_root`,
  :func:`get_module_path`).
* :mod:`mayutils.environment.filesystem.reading` — defensive text
  file reader (:func:`read_file`).
* :mod:`mayutils.environment.filesystem.encoding` — URL-safe path
  tokeniser and inverse (:func:`encode_path`, :func:`decode_path`).
* :mod:`mayutils.environment.filesystem.metadata` — mtime-backed
  cache-freshness check (:func:`is_file_stale`).

All public names from each submodule are re-exported here so existing
imports such as ``from mayutils.environment.filesystem import
get_root`` continue to resolve unchanged.

See Also
--------
mayutils.environment.memoisation : File-backed caches that lean on
    :func:`is_file_stale` to decide whether a stored artifact is
    still valid.
mayutils.data.queries : SQL template discovery that uses
    :func:`get_root` and :func:`read_file` to locate and load query
    files from the enclosing project.

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

from mayutils.environment.filesystem.encoding import decode_path, encode_path
from mayutils.environment.filesystem.metadata import is_file_stale
from mayutils.environment.filesystem.reading import read_file
from mayutils.environment.filesystem.roots import (
    get_module_path,
    get_module_root,
    get_root,
)

__all__ = [
    "decode_path",
    "encode_path",
    "get_module_path",
    "get_module_root",
    "get_root",
    "is_file_stale",
    "read_file",
]
