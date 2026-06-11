"""
Provide semantic version manipulation helpers.

Thin wrapper around :mod:`packaging.version` that centralises the
release-bump semantics used by ``mayutils``' versioning scripts and any
caller that needs to advance a ``major.minor.patch`` triple without
reaching for a regex. The module depends on the optional ``packaging``
distribution and is guarded by
:func:`mayutils.core.extras.may_require_extras` so a missing install
surfaces an actionable hint instead of a bare ``ImportError``. PEP 440
ordering rules govern how the resulting versions compare against
pre-release or post-release siblings. Also provides discovery and
resolution of time-effective versioned modules and values, vectorised
over timestamp arrays.

See Also
--------
packaging.version.Version : PEP 440 compliant version parser and
    comparator used as the canonical type within this module.
importlib.metadata.version : Standard library helper that resolves a
    distribution's installed version string, suitable input for
    :func:`bump_version_string`.
bump_version_string : Sibling helper that advances a version by a named
    release component.

Examples
--------
>>> from mayutils.objects.versions import bump_version_string
>>> str(bump_version_string("1.2.3", bump="patch"))
'1.2.4'
>>> str(bump_version_string("1.2.3", bump="minor"))
'1.3.0'
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from mayutils.core.extras import may_require_extras
from mayutils.environment.logging import Logger

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from types import ModuleType

    import numpy as np
    from numpy.typing import NDArray

with may_require_extras():
    from packaging.version import Version

logger = Logger.spawn()


def bump_version_string(
    version: str | Version,
    /,
    *,
    bump: str,
) -> Version:
    """
    Advance a semantic version by one release component.

    Coerces ``version`` to a :class:`packaging.version.Version` (parsing
    a string when needed), then constructs a new ``Version`` whose
    requested component is incremented by one. Lower-order components
    are reset to zero so ``minor`` and ``major`` bumps produce a clean
    release number rather than carrying stale patch or minor counts
    (e.g. bumping the minor of ``1.2.3`` yields ``1.3.0``, not
    ``1.3.3``). Any PEP 440 pre-release, post-release or local segment
    on the input is discarded because the result is always a plain
    three-component release, which orders strictly after every
    pre-release of the same release number.

    Parameters
    ----------
    version
        Current release identifier. Strings are parsed via
        :class:`packaging.version.Version`, so any PEP 440 compliant
        form is accepted; a pre-parsed ``Version`` is used directly.
        Only the ``major``, ``minor`` and ``micro`` components are
        inspected and pre-release, post-release and local segments are
        dropped in the returned value.
    bump
        Which component to advance. ``"patch"`` increments the micro
        segment only; ``"minor"`` increments the minor segment and
        resets the patch to zero; ``"major"`` increments the major
        segment and resets both minor and patch to zero.

    Returns
    -------
        A freshly constructed ``Version`` representing the bumped
        release, normalised to the three-component ``major.minor.patch``
        form and guaranteed to compare greater than ``version`` under
        PEP 440 ordering.

    Raises
    ------
    ValueError
        If ``bump`` is not one of ``"major"``, ``"minor"`` or
        ``"patch"``, indicating an unsupported release increment.

    See Also
    --------
    packaging.version.Version : Underlying PEP 440 compliant version
        type whose ``major``, ``minor`` and ``micro`` attributes drive
        the bump arithmetic.
    importlib.metadata.version : Standard library helper that returns
        the currently installed distribution version string, typical
        input to this function for release automation.

    Examples
    --------
    >>> str(bump_version_string("1.2.3", bump="patch"))
    '1.2.4'
    >>> str(bump_version_string("1.2.3", bump="minor"))
    '1.3.0'
    >>> str(bump_version_string("1.2.3", bump="major"))
    '2.0.0'
    >>> str(bump_version_string("2.0.0a1", bump="patch"))
    '2.0.1'
    """
    if isinstance(version, str):
        version = Version(version)

    if bump == "patch":
        return Version(version=f"{version.major}.{version.minor}.{version.micro + 1}")

    if bump == "minor":
        return Version(version=f"{version.major}.{version.minor + 1}.0")

    if bump == "major":
        return Version(version=f"{version.major + 1}.0.0")

    msg = f"Unknown part to bump: {bump}"
    raise ValueError(msg)


@dataclass(frozen=True)
class VersionedModule:
    """
    A module discovered under a ``v<N>/`` directory.

    Attributes
    ----------
    module : ModuleType
        The imported Python module.
    version : int
        Integer version extracted from the directory name (e.g. ``0`` from ``v0/``).
    implemented_timestamp : np.datetime64
        Value of the module's ``__implemented__`` attribute, used for routing.
    """

    module: ModuleType
    version: int
    implemented_timestamp: np.datetime64


def discover_versioned_modules(
    *,
    directory: Path,
    module_prefix: str,
    module_filename: str,
) -> list[VersionedModule] | None:
    """
    Scan ``{directory}/v*/module_filename`` for ``__implemented__`` timestamps.

    Parameters
    ----------
    directory : Path
        Parent directory containing ``v0/``, ``v1/``, ... sub-directories.
        Version sub-directories must be named ``v<int>`` (e.g. ``v0``,
        ``v1``); a directory whose name starts with ``v`` but is not
        followed by a valid integer (e.g. ``vendor/``) will raise
        ``ValueError`` when the version number is extracted.
    module_prefix : str
        Dotted import prefix for the versioned modules (e.g. ``"myapp.plugins"``).
    module_filename : str
        Filename to look for inside each version directory (e.g. ``"plugin.py"``).

    Returns
    -------
    list[VersionedModule] | None
        Modules sorted by ``__implemented__`` timestamp, or ``None`` if
        *directory* doesn't exist or contains no valid versions.
    """
    with may_require_extras():
        import numpy as np

    if not directory.is_dir():
        return None

    versions: list[VersionedModule] = []

    for version_dir in sorted(directory.iterdir()):
        if not version_dir.is_dir() or not version_dir.name.startswith("v"):
            continue

        module_file = version_dir / module_filename
        if not module_file.exists():
            continue

        module_path = f"{module_prefix}.{version_dir.name}.{module_filename.removesuffix('.py')}"
        mod = importlib.import_module(module_path)

        implemented_str = getattr(mod, "__implemented__", None)
        if implemented_str is None:
            continue

        versions.append(
            VersionedModule(
                module=mod,
                version=int(version_dir.name[1:]),
                implemented_timestamp=np.datetime64(implemented_str),
            ),
        )

    if len(versions) == 0:
        return None

    return sorted(
        versions,
        key=lambda v: (int(v.implemented_timestamp.astype(np.int64)), v.version),
    )


def resolve_module_version_index(
    *,
    implemented_timestamps: NDArray[np.datetime64],
    timestamps: NDArray[np.datetime64],
) -> NDArray[np.intp]:
    """
    Return the per-element module index into a sorted version list (vectorised).

    Parameters
    ----------
    implemented_timestamps : NDArray[np.datetime64]
        Sorted array of ``__implemented__`` timestamps from discovered modules.
    timestamps : NDArray[np.datetime64]
        Timestamp for each element.

    Returns
    -------
    NDArray[np.intp]
        Index into *implemented_timestamps* for each element, selecting
        the most recent version implemented on or before that timestamp,
        clamped to the earliest version for timestamps preceding all versions.
    """
    with may_require_extras():
        import numpy as np

    indices = (
        np.searchsorted(
            implemented_timestamps,
            timestamps,
            side="right",
        )
        - 1
    )
    return np.clip(indices, 0, len(implemented_timestamps) - 1)


def resolve_versions(
    *,
    versions: list[VersionedModule],
    timestamps: NDArray[np.datetime64],
) -> NDArray[np.intp]:
    """
    Resolve the active module version number per element.

    Parameters
    ----------
    versions : list[VersionedModule]
        Available module versions, sorted by implementation timestamp.
    timestamps : NDArray[np.datetime64]
        Timestamp per element.

    Returns
    -------
    NDArray[np.intp]
        Version number per element.
    """
    with may_require_extras():
        import numpy as np

    raw_indices = resolve_module_version_index(
        implemented_timestamps=np.asarray(
            [v.implemented_timestamp for v in versions],
            dtype="datetime64[us]",
        ),
        timestamps=timestamps,
    )

    return np.asarray(
        [v.version for v in versions],
        dtype=np.intp,
    )[raw_indices]


def apply_func_to_versioned_value(
    *,
    array: NDArray[Any],
    timestamps: NDArray[np.datetime64],
    versioned_value: dict[np.datetime64, Any],
    func: Callable[[NDArray[Any], Any], NDArray[Any]],
    dtype: type[np.bool_ | np.intp | np.int64 | np.float64 | np.str_] | str = "bool",
) -> NDArray[Any]:
    """
    Apply a function to each element using the time-appropriate versioned parameter.

    Parameters
    ----------
    array : NDArray[Any]
        Input array to process.
    timestamps : NDArray[np.datetime64]
        Timestamp per element used to resolve the active version.
    versioned_value : dict[np.datetime64, Any]
        Mapping from effective date to the parameter value for that version.
        Insertion order does not matter; values are resolved against
        date-sorted keys.
    func : Callable[[NDArray[Any], Any], NDArray[Any]]
        Function to apply, called with (array_slice, version_value) per version group.
    dtype : type or str, optional
        Data type of the output array, by default ``"bool"``.

    Returns
    -------
    NDArray[Any]
        Result array with the same shape as ``array``.
    """
    with may_require_extras():
        import numpy as np

    version_indices = resolve_version_indices(
        version_values=versioned_value,
        timestamps=timestamps,
    )

    sorted_values = [value for _, value in sorted(versioned_value.items())]

    versioned_return = np.empty(array.shape, dtype=dtype)
    for version_index in np.unique(version_indices):
        mask = version_indices == version_index
        versioned_return[mask] = func(array[mask], sorted_values[version_index])

    return versioned_return


def resolve_version_indices(
    *,
    version_values: dict[np.datetime64, Any],
    timestamps: NDArray[np.datetime64],
) -> NDArray[np.intp]:
    """
    Find the index of the most recent config date <= each timestamp.

    Parameters
    ----------
    version_values : dict[np.datetime64, Any]
        Mapping from effective date to a versioned parameter value.
    timestamps : NDArray[np.datetime64]
        Timestamp for each element.

    Returns
    -------
    NDArray[np.intp]
        Index (into the date-sorted keys of *version_values*) of the
        active version for each element, clamped to the earliest version
        for timestamps preceding all versions.
    """
    with may_require_extras():
        import numpy as np

    sorted_version_values = dict(sorted(version_values.items()))
    indices = (
        np.searchsorted(
            np.asarray(
                list(sorted_version_values.keys()),
                dtype="datetime64[us]",
            ),
            timestamps,
            side="right",
        )
        - 1
    )
    return np.clip(
        indices,
        0,
        len(version_values) - 1,
    )
