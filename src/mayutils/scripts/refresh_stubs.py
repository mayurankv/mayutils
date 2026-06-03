"""
Provide the command-line entry point for refreshing local pyright type stubs.

This module exposes a Typer application that inspects the project-local
``typings/`` directory, identifies the third-party packages for which
hand-curated or previously generated stubs already exist, confirms that
the packages still need external stubs (i.e. they do not ship a
``py.typed`` marker themselves and no community ``types-<pkg>`` stub is
installed), and regenerates their stubs via ``pyright --createstub``.
It is intended to be run after a dependency bump so that local stub
files stay in sync with the installed package signatures.

See Also
--------
pyright : Static type checker invoked to regenerate the ``.pyi`` stubs.
mypy : Alternative checker that also consumes the ``typings/`` overrides.
mayutils.scripts.clear_cache : Sibling maintenance CLI in ``mayutils.scripts``.

Examples
--------
>>> # Regenerate all stubs under ./typings via the console entry point:
>>> # $ refresh-stubs
>>> # Regenerate only stubs whose upstream version changed since HEAD:
>>> # $ refresh-stubs --since HEAD --jobs 8
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import tomllib
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib.metadata import distributions, packages_distributions
from pathlib import Path
from typing import cast

from mayutils.core.extras import may_require_extras
from mayutils.visualisation.console import CONSOLE

with may_require_extras():
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.table import Table
    from typer import Argument, Exit, Option, Typer


app = Typer()


def ships_py_typed(
    package: str,
    /,
) -> bool:
    """
    Detect whether ``package`` ships a PEP 561 ``py.typed`` marker.

    Resolves the import spec for ``package`` and then inspects every
    submodule search location (or the parent of ``spec.origin`` for
    single-file modules) for a ``py.typed`` sentinel file. A positive
    result indicates that the upstream maintainers bundle their own type
    information, so local stubs under ``typings/`` are redundant and the
    refresh driver will skip the package.

    Parameters
    ----------
    package
        Top-level importable name of the package to inspect, e.g.
        ``"numpy"``. Must be resolvable via
        :func:`importlib.util.find_spec` in the active environment.

    Returns
    -------
        ``True`` if the installed package declares itself typed, ``False``
        otherwise (including when the package cannot be located).

    See Also
    --------
    types_package_installed : Detect community ``types-<pkg>`` distributions.
    is_installed : Cheap importability probe used before this check.
    pyright : Static type checker that honours the same ``py.typed`` signal.
    mypy : Also honours PEP 561 ``py.typed`` when resolving third-party types.

    Examples
    --------
    A package that ships ``py.typed`` (e.g. ``rich``):

    >>> ships_py_typed("rich")  # doctest: +SKIP
    True

    A package without ``py.typed``:

    >>> ships_py_typed("snowflake")  # doctest: +SKIP
    False

    A package that is not installed returns ``False``:

    >>> ships_py_typed("definitely_not_installed_xyz123")
    False
    """
    spec = importlib.util.find_spec(name=package)
    if spec is None:
        return False

    locations = list(spec.submodule_search_locations or ())
    if not locations and spec.origin is not None:
        locations = [str(Path(spec.origin).parent)]

    return any((Path(location) / "py.typed").is_file() for location in locations)


def types_package_installed(
    package: str,
    /,
) -> bool:
    """
    Detect whether a community ``types-<package>`` stub distribution is installed.

    Normalises the package name to the PEP 503 ``types-<package>`` form
    (hyphen-separated, lowercase) and scans the metadata of every
    installed distribution for a case-insensitive match. When such a
    distribution exists the refresh driver skips regeneration so the
    community stubs remain authoritative rather than being shadowed by
    pyright's generated output.

    Parameters
    ----------
    package
        Top-level importable name of the runtime package. Underscores are
        converted to hyphens before comparison so that, e.g.,
        ``"python_dateutil"`` matches the ``types-python-dateutil``
        distribution.

    Returns
    -------
        ``True`` if a sibling distribution named ``types-<package>`` (any
        case, hyphen / underscore insensitive) is resolvable via
        :func:`importlib.metadata.distributions`, ``False`` otherwise.

    See Also
    --------
    ships_py_typed : Detect first-party ``py.typed`` markers.
    normalise_dist : Normalise distribution names for lock-file comparison.
    pyright : Type checker that prefers ``types-*`` stubs when they exist.
    mypy : Consumes the same ``types-*`` convention from typeshed.

    Examples
    --------
    >>> types_package_installed("requests")  # doctest: +SKIP
    True
    >>> types_package_installed("numpy")  # doctest: +SKIP
    False
    """
    target = f"types-{package.replace('_', '-')}".lower()
    return any((dist.metadata["Name"] or "").lower() == target for dist in distributions())


def is_installed(
    package: str,
    /,
) -> bool:
    """
    Detect whether ``package`` is importable in the active environment.

    Thin wrapper around :func:`importlib.util.find_spec` that returns a
    boolean rather than raising when the module is absent. The refresh
    driver calls this first so it can report "not installed" in the
    skipped table instead of letting ``pyright --createstub`` fail with a
    less actionable message further down the pipeline.

    Parameters
    ----------
    package
        Top-level importable name to probe, e.g. ``"requests"``.

    Returns
    -------
        ``True`` if :func:`importlib.util.find_spec` locates the module,
        ``False`` otherwise.

    See Also
    --------
    ships_py_typed : Follow-up check run only when the package is installed.
    is_namespace_package : Related spec-based probe for PEP 420 namespaces.
    pyright : Consumer of the generated stubs produced for installed packages.
    mypy : Also requires the package (or its stubs) to be importable.

    Examples
    --------
    >>> is_installed("os")
    True
    >>> is_installed("definitely_not_a_module")
    False
    """
    return importlib.util.find_spec(name=package) is not None


def is_namespace_package(
    package: str,
    /,
) -> bool:
    """
    Detect whether ``package`` is a PEP 420 namespace package.

    Namespace packages have no ``__init__`` module (``spec.origin is None``)
    but do expose a submodule search path. ``pyright --createstub`` refuses
    to stub such packages directly and must be invoked against each concrete
    subpackage instead, so the refresh driver uses this probe to decide
    whether to call :func:`expand_namespace` before dispatching to
    :func:`run_pyright`.

    Parameters
    ----------
    package
        Dotted import name to inspect, e.g. ``"zope"`` or
        ``"google.cloud"``.

    Returns
    -------
        ``True`` when the import spec declares no ``origin`` yet still has
        submodule search locations, ``False`` otherwise.

    See Also
    --------
    expand_namespace : Turn a namespace parent into stubbed child names.
    is_installed : Precondition for this probe to have a useful answer.
    pyright : Tool whose ``--createstub`` quirk motivates this helper.
    mypy : Also treats namespace packages specially when resolving imports.

    Examples
    --------
    Standard-library modules are not namespace packages:

    >>> is_namespace_package("os")
    False

    A namespace package like ``google`` (if installed):

    >>> is_namespace_package("google")  # doctest: +SKIP
    True
    """
    spec = importlib.util.find_spec(name=package)
    return spec is not None and spec.origin is None and bool(spec.submodule_search_locations)


def expand_namespace(
    package: str,
    /,
    *,
    typings: Path,
) -> list[str]:
    """
    Expand a namespace package into the concrete subpackages stubbed under ``typings``.

    Walks the immediate children of ``typings / package`` and emits a
    dotted name per stubbable subpackage so that ``pyright --createstub``
    can be invoked against each concrete child. When the namespace has no
    scaffolded subpackages under ``typings`` the function falls back to
    the bare ``[package]`` form, which succeeds for effectively
    single-module namespaces and otherwise surfaces a clear pyright
    error that prompts the maintainer to seed the subpackage folders.

    Parameters
    ----------
    package
        Top-level namespace package name, e.g. ``"google"``.
    typings
        Root of the local stubs directory. ``typings / package`` is
        inspected for immediate child directories that correspond to
        stubbable subpackages.

    Returns
    -------
        Dotted names of the form ``<package>.<subpackage>`` for every
        subdirectory under ``typings / package``. Falls back to
        ``[package]`` when no subdirectories exist so pyright can still
        be invoked against the namespace directly — this succeeds for
        namespaces that effectively expose a single top-level module
        (for example ``quarto_cli``) and surfaces a pyright error for
        genuinely multi-subpackage namespaces that need their stubs
        scaffolded first.

    See Also
    --------
    is_namespace_package : Decides whether expansion is required.
    stub_packages : Complementary listing of stubbed top-level packages.
    pyright : Target of ``--createstub`` dispatched per expanded name.
    mypy : Alternative consumer of the resulting per-subpackage stubs.

    Examples
    --------
    >>> from pathlib import Path
    >>> expand_namespace("not_a_namespace", typings=Path("/tmp/nope"))
    ['not_a_namespace']
    """
    root = typings / package
    if not root.is_dir():
        return [package]

    subs = sorted(child.name for child in root.iterdir() if child.is_dir() and not child.name.startswith(("_", ".")))
    if not subs:
        return [package]

    return [f"{package}.{sub}" for sub in subs]


def stub_packages(
    typings: Path,
    /,
) -> list[str]:
    """
    List top-level packages with stubs under ``typings``.

    Scans only the first level of the ``typings`` directory so that the
    refresh driver iterates exactly once per stubbed distribution.
    Hidden directories (``.``-prefixed) and private scaffolding
    (``_``-prefixed) are filtered out, and stand-alone ``.pyi`` siblings
    are treated as single-file stubs. The resulting list is sorted to
    make both dry-run output and downstream diffs deterministic across
    filesystems with different traversal orders.

    Parameters
    ----------
    typings
        Directory searched for stub roots. Each immediate subdirectory is
        treated as a separate package; top-level ``.pyi`` files are
        reported as stand-alone modules.

    Returns
    -------
        Package names (directory names or the stem of a top-level
        ``.pyi`` file), sorted alphabetically and de-duplicated.

    See Also
    --------
    expand_namespace : Second-pass expansion for namespace packages.
    filter_by_changed : Narrow this listing to packages affected by a diff.
    pyright : Consumer whose search path is rooted at this directory.
    mypy : Same directory is typically added to ``mypy_path`` as well.

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> tmp = tempfile.mkdtemp()
    >>> root = Path(tmp)
    >>> (root / "alpha").mkdir()
    >>> (root / "beta").mkdir()
    >>> (root / "_private").mkdir()
    >>> _ = (root / "gamma.pyi").write_text("")
    >>> stub_packages(root)
    ['alpha', 'beta', 'gamma']
    """
    names: set[str] = set()
    for child in typings.iterdir():
        if child.is_dir() and not child.name.startswith("_") and not child.name.startswith("."):
            names.add(child.name)
        elif child.is_file() and child.suffix == ".pyi":
            names.add(child.stem)

    return sorted(names)


_CHAINED_ASSIGN_RE = re.compile(
    pattern=r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$",
    flags=re.MULTILINE,
)
"""Match ``name = name = expression`` statements at the start of a line.

Used exclusively by :func:`canonicalise_chained_assignments` to work
around a pyright ``--createstub`` bug that shuffles the order of the
left-hand-side names between runs (for example ``Reduce = reduce`` on
one run and ``reduce = Reduce`` on the next), which otherwise makes
every regeneration rewrite the stub file even though the semantics are
unchanged.
"""


def canonicalise_chained_assignments(
    text: str,
    /,
) -> str:
    """
    Canonicalise chained-assignment LHS order in generated stub text.

    Pyright's ``--createstub`` emits lines of the form ``a = b = rhs``
    with non-deterministic ordering of ``a`` and ``b`` across runs. This
    helper sorts the two left-hand-side names alphabetically for every
    match of :data:`_CHAINED_ASSIGN_RE` so consecutive regenerations
    produce byte-identical output, which in turn stops diff-based stub
    caches from marking otherwise unchanged files as dirty.

    Parameters
    ----------
    text
        Full contents of a generated ``.pyi`` file.

    Returns
    -------
        The same text with every matching chained assignment rewritten
        so its two LHS names appear in sorted order. Lines that don't
        match the pattern are left untouched.

    See Also
    --------
    stabilise_chained_assignments : Apply this helper across a stub tree.
    _CHAINED_ASSIGN_RE : Regular expression driving the rewrite.
    pyright : Source of the non-deterministic output this helper stabilises.
    mypy : Unaffected consumer; the rewrite preserves semantics for both.

    Examples
    --------
    >>> canonicalise_chained_assignments("Reduce = reduce = _reduce_impl")
    'Reduce = reduce = _reduce_impl'
    >>> canonicalise_chained_assignments("reduce = Reduce = _reduce_impl")
    'Reduce = reduce = _reduce_impl'
    """

    def _sort(match: re.Match[str]) -> str:
        """
        Rewrite a single chained-assignment match with sorted LHS names.

        Helper closure used as the replacement callback for
        :meth:`re.Pattern.sub`. The two captured LHS identifiers are
        sorted alphabetically and reassembled with the original
        right-hand-side expression to keep the transform purely
        cosmetic.

        Parameters
        ----------
        match
            Match object produced by :data:`_CHAINED_ASSIGN_RE`, whose
            first two groups hold the LHS names and third group holds
            the RHS expression.

        Returns
        -------
            Replacement text of the form ``"<first> = <second> = <rhs>"``
            with ``first`` and ``second`` sorted alphabetically.

        See Also
        --------
        canonicalise_chained_assignments : Outer caller driving the rewrite.
        stabilise_chained_assignments : File-level wrapper applying both.
        pyright : Origin of the unordered LHS names this callback fixes.
        mypy : Same stub files are consumed without any observable change.

        Examples
        --------
        >>> import re
        >>> match = _CHAINED_ASSIGN_RE.search("reduce = Reduce = _impl")
        >>> _sort(match)
        'Reduce = reduce = _impl'
        """
        first, second = sorted((match.group(1), match.group(2)))

        return f"{first} = {second} = {match.group(3)}"

    return _CHAINED_ASSIGN_RE.sub(_sort, text)


def stabilise_chained_assignments(
    root: Path,
    /,
) -> None:
    r"""
    Rewrite every ``.pyi`` under ``root`` with chained assignments sorted.

    Walks ``root`` recursively and applies
    :func:`canonicalise_chained_assignments` to every ``.pyi`` file,
    only writing back when the canonical form differs. This is a
    targeted workaround for pyright's non-deterministic output — not a
    general formatter — so content that doesn't contain the specific
    pattern is left byte-identical and spurious diff churn in the
    ``typings/`` tree is suppressed.

    Parameters
    ----------
    root
        Stub package folder to stabilise. Usually
        ``typings/<package>/``.

    See Also
    --------
    canonicalise_chained_assignments : Per-file text rewrite used here.
    run_pyright : Producer of the stub files stabilised by this helper.
    pyright : Tool whose non-deterministic emission motivates the workaround.
    mypy : Downstream consumer that also benefits from the stable output.

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> tmp = tempfile.mkdtemp()
    >>> root = Path(tmp)
    >>> stub = root / "demo.pyi"
    >>> _ = stub.write_text("reduce = Reduce = _impl\\n", encoding="utf-8")
    >>> stabilise_chained_assignments(root)
    >>> stub.read_text(encoding="utf-8")
    'Reduce = reduce = _impl\\n'
    """
    for path in root.rglob(pattern="*.pyi"):
        original = path.read_text(encoding="utf-8")
        canonical = canonicalise_chained_assignments(original)
        if canonical != original:
            path.write_text(data=canonical, encoding="utf-8")


def normalise_dist(
    name: str,
    /,
) -> str:
    """
    Return the PEP 503 normalised form of a distribution name.

    Collapses any run of hyphens, underscores, or periods into a single
    hyphen and lowercases the result so that distribution names coming
    from wheels, ``uv.lock`` entries, and ``importlib.metadata`` compare
    equal regardless of formatting conventions. The refresh driver uses
    the normalised form as the canonical dictionary key when diffing
    lock files between revisions.

    Parameters
    ----------
    name
        Raw distribution name as read from metadata or a lock file,
        e.g. ``"Python.DateUtil"``.

    Returns
    -------
        PEP 503 normalised name, e.g. ``"python-dateutil"``.

    See Also
    --------
    lock_versions : Producer of ``{normalised_name: version}`` mappings.
    changed_distributions : Consumer that diffs two normalised maps.
    pyright : Tool that ultimately consumes the selected distributions.
    mypy : Same normalisation rules apply when resolving ``types-*`` stubs.

    Examples
    --------
    >>> normalise_dist("Python.DateUtil")
    'python-dateutil'
    >>> normalise_dist("types_requests")
    'types-requests'
    """
    dist_normalise_regex = re.compile(pattern=r"[-_.]+")

    return dist_normalise_regex.sub(repl="-", string=name).lower()


def lock_versions(
    text: str,
    /,
) -> dict[str, str]:
    r"""
    Extract ``{normalised_name: version}`` pairs from ``uv.lock`` text.

    Parses the TOML payload produced by ``uv lock``, iterates the
    ``package`` array, and records the pinned version for each entry
    under its PEP 503 normalised name. Entries without the expected
    string fields are skipped silently so malformed or partial lock
    files degrade to "no known versions" rather than raising, which lets
    the caller fall back to a full refresh.

    Parameters
    ----------
    text
        Full contents of a ``uv.lock`` file, already decoded to text.

    Returns
    -------
        Mapping from :func:`normalise_dist` output to pinned version
        string. Empty when the payload has no ``package`` array or the
        array is malformed.

    See Also
    --------
    normalise_dist : Normalisation applied to every key in the result.
    lock_versions_at_rev : Git-aware companion reading historical locks.
    changed_distributions : Consumer of the resulting mappings.
    pyright : Downstream tool whose stubs track these pinned versions.

    Examples
    --------
    >>> lock_versions("")
    {}
    >>> sample = '[[package]]\\nname = "Requests"\\nversion = "2.31.0"\\n'
    >>> lock_versions(sample)
    {'requests': '2.31.0'}
    """
    data: dict[str, object] = tomllib.loads(text)
    raw_packages: object = data.get("package")
    out: dict[str, str] = {}
    if not isinstance(raw_packages, list):
        return out

    for entry in raw_packages:  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(entry, dict):
            continue

        typed_entry = cast("dict[str, object]", entry)
        name = typed_entry.get("name")
        version = typed_entry.get("version")

        if isinstance(name, str) and isinstance(version, str):
            out[normalise_dist(name)] = version

    return out


def lock_versions_at_rev(
    lock: Path,
    /,
    *,
    rev: str,
) -> dict[str, str] | None:
    """
    Return ``uv.lock`` contents at git ``rev`` as ``{name: version}``, or ``None`` on failure.

    Shells out to ``git show <rev>:./<lock>`` from the lock file's
    directory so the caller can diff the current working-tree lock
    against an arbitrary historical revision without a ``git checkout``.
    Any error from ``git`` (missing executable, bad revision,
    non-repository) or TOML parser is captured and converted to
    ``None`` so the refresh CLI can gracefully fall back to a full
    rebuild.

    Parameters
    ----------
    lock
        Path to the working-tree ``uv.lock``. Only the basename is
        passed to ``git show``; the parent is used as the subprocess
        working directory.
    rev
        Git revision to inspect, e.g. ``"HEAD"``, ``"origin/main"``, or
        a commit SHA.

    Returns
    -------
        Mapping produced by :func:`lock_versions` when the historical
        lock can be read and parsed, else ``None``.

    See Also
    --------
    lock_versions : Pure-text counterpart used on the current lock file.
    changed_distributions : Primary consumer comparing two lock snapshots.
    pyright : Tool whose stub regeneration is gated on this diff.
    mypy : Alternative consumer; stubs remain usable across both checkers.

    Examples
    --------
    >>> from pathlib import Path
    >>> lock_versions_at_rev(Path("uv.lock"), rev="HEAD")  # doctest: +SKIP
    {'requests': '2.31.0', 'pandas': '2.2.2', ...}

    Returns ``None`` when the revision or file cannot be read:

    >>> lock_versions_at_rev(Path("uv.lock"), rev="nonexistent-ref")  # doctest: +SKIP
    """
    try:
        result = subprocess.run(
            args=["git", "show", f"{rev}:./{lock.name}"],
            cwd=lock.parent,
            capture_output=True,
            text=True,
            check=True,
        )

    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    try:
        return lock_versions(result.stdout)

    except tomllib.TOMLDecodeError:
        return None


def changed_distributions(
    lock: Path,
    /,
    *,
    rev: str,
) -> set[str] | None:
    """
    Return normalised distribution names whose version changed vs ``rev``.

    Reads the current working-tree lock file and the historical version
    at ``rev`` via :func:`lock_versions_at_rev`, then diffs the two maps
    to surface any added, removed, or version-shifted distribution.
    This drives the ``--since`` flag on the CLI so stubs are only
    regenerated for packages that actually moved, saving significant
    time on large ``typings/`` trees where most packages are untouched.

    Parameters
    ----------
    lock
        Path to the working-tree ``uv.lock``.
    rev
        Git revision to compare against (typically ``"HEAD"``).

    Returns
    -------
        Names that changed (including new or removed distributions), or
        ``None`` when the comparison cannot be performed — for instance
        when the lock file did not exist at ``rev``, when the project
        isn't a git repository, or when either side fails to parse.
        Callers should treat ``None`` as "refresh everything" rather
        than "nothing changed".

    See Also
    --------
    lock_versions_at_rev : Git-aware reader used for the historical side.
    lock_versions : Text-only reader used for the working-tree side.
    filter_by_changed : Maps the returned set onto importable package names.
    pyright : Tool whose stub refresh is gated on this diff.

    Examples
    --------
    >>> from pathlib import Path
    >>> changed_distributions(Path("uv.lock"), rev="HEAD")  # doctest: +SKIP
    {'requests', 'pandas'}

    Returns ``None`` when the comparison cannot be performed:

    >>> changed_distributions(Path("uv.lock"), rev="nonexistent-ref")  # doctest: +SKIP
    """
    before = lock_versions_at_rev(lock, rev=rev)
    if before is None:
        return None

    try:
        after = lock_versions(lock.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None

    changed: set[str] = {name for name, version in after.items() if before.get(name) != version}
    changed.update(before.keys() - after.keys())

    return changed


def filter_by_changed(
    packages: list[str],
    /,
    *,
    changed: set[str],
) -> list[str]:
    """
    Keep only ``packages`` whose providing distribution is in ``changed``.

    Uses :func:`importlib.metadata.packages_distributions` to map each
    importable package name onto the wheel(s) that provide it, then
    checks the PEP 503 normalised distribution names against the
    supplied change set. Packages with no discoverable distribution
    (e.g. vendored namespaces not installed under a wheel) are kept as a
    safe default, so an unrecognised entry never silently gets skipped
    when the CLI is invoked with ``--since``.

    Parameters
    ----------
    packages
        Top-level importable package names emitted by
        :func:`stub_packages`.
    changed
        PEP 503 normalised distribution names produced by
        :func:`changed_distributions`.

    Returns
    -------
        Subset of ``packages`` whose providing distribution intersects
        ``changed``, plus any package with no discoverable distribution.

    See Also
    --------
    changed_distributions : Producer of the ``changed`` argument.
    normalise_dist : Applied to each candidate distribution name.
    stub_packages : Source of the ``packages`` argument.
    pyright : Tool run on the filtered package list.

    Examples
    --------
    Only packages whose distribution changed are kept:

    >>> filter_by_changed(  # doctest: +SKIP
    ...     ["requests", "yaml"],
    ...     changed={"requests"},
    ... )  # doctest: +SKIP
    ['requests']

    Packages with no discoverable distribution are kept as a safe default:

    >>> filter_by_changed(  # doctest: +SKIP
    ...     ["unknown"],
    ...     changed={"requests"},
    ... )  # doctest: +SKIP
    ['unknown']
    """
    mapping = packages_distributions()
    kept: list[str] = []
    for package in packages:
        dists = mapping.get(package) or mapping.get(package.split(".", maxsplit=1)[0])
        if not dists:
            kept.append(package)
            continue

        if any(normalise_dist(dist) in changed for dist in dists):
            kept.append(package)

    return kept


def run_pyright(
    package: str,
    /,
    *,
    typings: Path,
) -> subprocess.CompletedProcess[str]:
    """
    Invoke ``pyright --createstub`` for ``package``.

    Runs the pyright CLI as a subprocess, capturing both streams so the
    orchestrator can decide whether to report success, surface an error
    row in the skipped table, or log stdout in verbose mode. The
    subprocess is launched with ``typings.parent`` as the working
    directory so pyright's default ``<cwd>/typings/<package>`` output
    layout lines up with the expectations of :func:`stub_packages` and
    :func:`stabilise_chained_assignments`.

    Parameters
    ----------
    package
        Top-level importable name passed to ``pyright --createstub``.
    typings
        Directory into which pyright should emit regenerated stubs. The
        command is executed with ``typings.parent`` as the working
        directory so pyright writes into ``<cwd>/typings/<package>``
        following its default convention.

    Returns
    -------
        Result of the subprocess call, with ``stdout`` / ``stderr``
        captured for inspection by the caller.

    See Also
    --------
    stabilise_chained_assignments : Post-processing applied on success.
    refresh : Command that dispatches this helper in a thread pool.
    pyright : External CLI invoked here to produce ``.pyi`` files.
    mypy : Alternative checker; this helper only targets pyright output.

    Examples
    --------
    >>> from pathlib import Path
    >>> result = run_pyright("requests", typings=Path("typings"))  # doctest: +SKIP
    >>> result.returncode  # doctest: +SKIP
    0
    """
    return subprocess.run(
        args=["pyright", "--createstub", package],
        cwd=typings.parent,
        capture_output=True,
        text=True,
        check=False,
    )


def apply_plotly_overlay(
    *,
    dry_run: bool = False,
) -> None:
    """
    Re-apply the bespoke plotly stub overrides on top of the pyright baseline.

    ``pyright --createstub plotly`` regenerates ``typings/plotly/`` from the
    live package, overwriting the hand-curated overrides, so this overlay
    step runs the plotly generator afterwards to restore them and rewrite
    the in-source trace and chart stubs. The plotly generator is imported
    lazily so :func:`refresh` stays usable without the ``plotting`` extra,
    and a missing ``plotly-stubs`` distribution is reported and skipped
    rather than raised.

    Parameters
    ----------
    dry_run
        If ``True``, preview the overlay without writing any files.

    See Also
    --------
    refresh : Orchestrator that invokes this after refreshing ``plotly``.
    mayutils.scripts.generate_plotly_stubs.generate_stubs : Generator run here.

    Examples
    --------
    >>> apply_plotly_overlay(dry_run=True)  # doctest: +SKIP
    """
    from mayutils.scripts.generate_plotly_stubs import generate_stubs  # noqa: PLC0415

    CONSOLE.print("\n[bold]Applying plotly stub overrides...[/bold]")
    try:
        count = generate_stubs(dry_run=dry_run)
    except FileNotFoundError as error:
        CONSOLE.print(f"[yellow]Skipped plotly overlay: {error}[/yellow]")
        return

    if not dry_run and count == 0:
        CONSOLE.print("[yellow]plotly overlay produced 0 stubs — check plotly-stubs.[/yellow]")


@app.command()
def refresh(  # noqa: C901, PLR0912, PLR0915
    typings: Path = Argument(  # noqa: B008
        Path("typings"),
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        writable=True,
        resolve_path=True,
        help="Root ``typings/`` folder to refresh",
    ),
    *,
    include_typed: bool = Option(
        False,  # noqa: FBT003
        "--include-typed",
        help="Regenerate even for packages that ship their own ``py.typed``",
    ),
    dry_run: bool = Option(
        False,  # noqa: FBT003
        "--dry-run",
        "-n",
        help="List packages that would be refreshed, do not invoke pyright",
    ),
    verbose: bool = Option(
        False,  # noqa: FBT003
        "--verbose",
        "-v",
        help="Stream pyright stdout/stderr for each package",
    ),
    since: str | None = Option(
        None,
        "--since",
        help=(
            "Only refresh packages whose distribution version changed in "
            "``uv.lock`` relative to this git revision (e.g. ``HEAD``). "
            "Falls back to refreshing everything when the lock cannot be "
            "read at the given revision."
        ),
    ),
    lock: Path = Option(  # noqa: B008
        Path("uv.lock"),
        "--lock",
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Path to the ``uv.lock`` consulted when ``--since`` is set.",
    ),
    jobs: int = Option(
        max(os.cpu_count() or 4, 1),
        "--jobs",
        "-j",
        min=1,
        help="Number of parallel ``pyright --createstub`` workers.",
    ),
) -> None:
    """
    Regenerate ``pyright`` stubs for each package already present in ``typings/``.

    Walks the top level of ``typings`` for existing stub packages, drops any
    package that no longer requires third-party stubs (either because it
    ships its own ``py.typed`` marker or because a community
    ``types-<package>`` distribution is installed), and runs
    ``pyright --createstub`` for the remainder in a bounded
    :class:`~concurrent.futures.ThreadPoolExecutor`. Packages that are no
    longer importable are reported and skipped, namespace packages are
    expanded into their stubbed subpackages, and successful output is
    post-processed with :func:`stabilise_chained_assignments` so diff
    detection against the previous run stays stable.

    Parameters
    ----------
    typings
        Directory that holds existing stub packages, each as a subfolder.
        Typer validates that the path exists and is writable.
    include_typed
        When ``True`` the runtime ``py.typed`` guard is ignored and pyright
        is run for every discovered package. Useful when an upstream
        package declares itself typed but the project wants to keep local
        overrides in sync anyway.
    dry_run
        When ``True`` the command enumerates the work that would be done
        (including reasons for any skips) but never invokes pyright.
    verbose
        When ``True`` pyright's output is streamed for every package that
        succeeds; errors are always surfaced regardless of this flag.
    since
        Optional git revision (for example ``"HEAD"``) used to narrow
        the refresh to distributions whose version changed in
        ``uv.lock`` since that revision. When the lock file cannot be
        read at the revision the command falls back to refreshing every
        package rather than silently skipping work.
    lock
        Path to the ``uv.lock`` consulted when ``since`` is provided.
        Typer resolves the path so relative invocations from
        subdirectories still work.
    jobs
        Maximum number of parallel ``pyright --createstub`` workers.
        Effective concurrency is clamped to the refreshable package
        count so short runs never spin up more threads than needed.

    Raises
    ------
    typer.Exit
        Raised without an exit code when ``typings`` contains no stub
        packages, when ``since`` indicates no relevant changes, or when
        ``dry_run`` is set; raised with code ``1`` when at least one
        pyright invocation fails.

    See Also
    --------
    stub_packages : Initial listing consumed by this command.
    filter_by_changed : ``--since`` support consulted before dispatch.
    run_pyright : Per-package subprocess dispatched from the thread pool.
    stabilise_chained_assignments : Post-processing run on success.
    pyright : External tool invoked to regenerate each stub.
    mypy : Alternative checker that also consumes the refreshed stubs.

    Examples
    --------
    >>> # Regenerate every stub under ./typings:
    >>> # $ refresh-stubs
    >>> # Refresh only packages whose uv.lock entry changed since HEAD~1,
    >>> # with eight parallel pyright workers and verbose logging:
    >>> # $ refresh-stubs --since HEAD~1 --jobs 8 -v
    >>> # Show the plan without invoking pyright:
    >>> # $ refresh-stubs --dry-run
    """
    packages = stub_packages(typings)

    if not packages:
        CONSOLE.print(f"[green]No stub packages under {typings}; nothing to refresh.[/green]")
        raise Exit

    CONSOLE.print(f"[blue]Discovered {len(packages)} stub package(s) under {typings}[/blue]")

    if since is not None:
        changed = changed_distributions(lock, rev=since)
        if changed is None:
            CONSOLE.print(f"[yellow]Could not diff {lock.name} against {since}; refreshing all packages.[/yellow]")
        elif not changed:
            CONSOLE.print(f"[green]No distributions changed in {lock.name} since {since}.[/green]")
            raise Exit
        else:
            filtered = filter_by_changed(packages, changed=changed)

            if not filtered:
                CONSOLE.print(f"[green]No stubbed distributions changed in {lock.name} since {since}.[/green]")
                raise Exit

            CONSOLE.print(f"[blue]{len(filtered)}/{len(packages)} stub package(s) affected by changes since {since}[/blue]")
            packages = filtered

    refreshable: list[str] = []
    skipped: list[tuple[str, str]] = []

    for package in packages:
        if not is_installed(package):
            skipped.append((package, "not installed"))
            continue

        if not include_typed and ships_py_typed(package):
            skipped.append((package, "ships py.typed"))
            continue

        if types_package_installed(package):
            skipped.append((package, "types-* stub installed"))
            continue

        if is_namespace_package(package):
            refreshable.extend(expand_namespace(package, typings=typings))
        else:
            refreshable.append(package)

    if skipped:
        table = Table(title=f"[yellow]Skipped {len(skipped)} package(s)[/yellow]", show_header=True)
        table.add_column(header="Package")
        table.add_column(header="Reason", style="dim")
        for package, reason in skipped:
            table.add_row(package, reason)
        CONSOLE.print(table)

    if not refreshable:
        CONSOLE.print("[green]All stub packages are up-to-date or unnecessary.[/green]")
        raise Exit

    action = "Would refresh" if dry_run else "Refreshing"
    CONSOLE.print(f"[cyan]{action} {len(refreshable)} package(s):[/cyan] {', '.join(refreshable)}")

    if dry_run:
        if "plotly" in refreshable:
            apply_plotly_overlay(dry_run=True)
        raise Exit

    failures: list[tuple[str, str]] = []
    refreshed: list[str] = []

    workers = max(1, min(jobs, len(refreshable)))

    with Progress(
        SpinnerColumn(style="bold blue"),
        TextColumn(text_format="[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=CONSOLE,
        transient=not verbose,
    ) as progress:
        task = progress.add_task(
            description=f"[cyan]Running pyright --createstub ({workers} worker(s))...",
            total=len(refreshable),
        )

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(run_pyright, package, typings=typings): package for package in refreshable}

            for future in as_completed(futures):
                package = futures[future]
                result = future.result()

                if result.returncode != 0:
                    failures.append((package, result.stderr.strip() or result.stdout.strip()))
                    CONSOLE.print(f"[bold red]:x: {package}:[/bold red] pyright exited with {result.returncode}")
                else:
                    refreshed.append(package)
                    target = typings.joinpath(*package.split("."))
                    if target.is_dir():
                        stabilise_chained_assignments(target)
                    if verbose:
                        CONSOLE.print(f"[green]:white_check_mark: {package}[/green]")
                        if result.stdout.strip():
                            CONSOLE.print(result.stdout.rstrip())

                progress.update(task_id=task, description=f"[bold yellow]{package}")
                progress.advance(task_id=task)

    if failures:
        CONSOLE.print(f"[bold red]:warning: {len(failures)} failure(s):[/bold red]")
        for package, output in failures:
            CONSOLE.print(f"[red]- {package}[/red]\n{output}")
        raise Exit(code=1)

    CONSOLE.print(f"[green]:white_check_mark: Refreshed {len(refreshed)} package(s) in {typings}.[/green]")

    if "plotly" in refreshed:
        apply_plotly_overlay()


if __name__ == "__main__":
    app()
