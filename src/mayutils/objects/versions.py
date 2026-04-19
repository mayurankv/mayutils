"""Semantic version manipulation helpers.

Thin wrapper around :mod:`packaging.version` that centralises the
release-bump semantics used by ``mayutils``' versioning scripts and any
caller that needs to advance a ``major.minor.patch`` triple without
reaching for a regex. The module depends on the optional ``packaging``
distribution and is guarded by
:func:`mayutils.core.extras.may_require_extras` so a missing install
surfaces an actionable hint instead of a bare ``ImportError``.
"""

from mayutils.core.extras import may_require_extras
from mayutils.environment.logging import Logger

with may_require_extras():
    from packaging.version import Version

logger = Logger.spawn()


def bump_version_string(
    version: str | Version,
    /,
    *,
    bump: str,
) -> Version:
    """Advance a semantic version by one release component.

    Coerces ``version`` to a :class:`packaging.version.Version` (parsing
    a string when needed), then constructs a new ``Version`` whose
    requested component is incremented by one. Lower-order components
    are reset to zero so ``minor`` and ``major`` bumps produce a clean
    release number rather than carrying stale patch or minor counts
    (e.g. bumping the minor of ``1.2.3`` yields ``1.3.0``, not
    ``1.3.3``).

    Parameters
    ----------
    version : str or packaging.version.Version
        Current release identifier. Strings are parsed via
        :class:`packaging.version.Version`, so any PEP 440 compliant
        form is accepted; a pre-parsed ``Version`` is used directly.
        Only the ``major``, ``minor`` and ``micro`` components are
        inspected — pre-release, post-release and local segments are
        dropped in the returned value.
    bump : {"major", "minor", "patch"}
        Which component to advance. ``"patch"`` increments the micro
        segment only; ``"minor"`` increments the minor segment and
        resets the patch to zero; ``"major"`` increments the major
        segment and resets both minor and patch to zero.

    Returns
    -------
    packaging.version.Version
        A freshly constructed ``Version`` representing the bumped
        release, normalised to the three-component ``major.minor.patch``
        form.

    Raises
    ------
    ValueError
        If ``bump`` is not one of ``"major"``, ``"minor"`` or
        ``"patch"``, indicating an unsupported release increment.
    packaging.version.InvalidVersion
        Propagated from :class:`packaging.version.Version` when a
        string ``version`` cannot be parsed as PEP 440.

    Examples
    --------
    >>> str(bump_version_string("1.2.3", bump="patch"))
    '1.2.4'
    >>> str(bump_version_string("1.2.3", bump="minor"))
    '1.3.0'
    >>> str(bump_version_string("1.2.3", bump="major"))
    '2.0.0'
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
