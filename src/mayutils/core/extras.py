"""
Resolve which optional extra provides a given optional dependency.

This module inspects the ``mayutils`` distribution metadata at runtime to
map importable module names back to the ``[project.optional-dependencies]``
extras that declare them, and exposes context managers that convert bare
:class:`ImportError` failures into actionable ``uv add`` / ``pip install``
hints. Mapping data is derived dynamically from the installed package
metadata: extras-to-distributions comes from parsing the ``Requires-Dist``
headers for ``extra == '<name>'`` markers, while distribution-to-modules
is read from the dist-info ``top_level.txt`` when the distribution is
installed, falling back to ``dist_name.replace("-", "_")`` when it is not.
The :func:`may_require_extras` context manager is the primary entry point
for submodules with heavy top-of-file imports because it auto-resolves
the matching extras at ``ImportError`` time, while :func:`requires_extras`
remains available when a specific hint must be forced.

See Also
--------
importlib.metadata : Standard-library access to installed distribution
    metadata used to read ``Requires-Dist`` headers and ``top_level.txt``.
packaging.requirements.Requirement : PEP 508 requirement parser whose
    grammar describes the ``Requires-Dist`` strings this module handles.
mayutils.__init__.setup : Package bootstrap that pairs with these
    helpers to give optional imports clear failure modes.

Examples
--------
>>> from mayutils.core.extras import may_require_extras
>>> with may_require_extras():
...     import mayutils
>>> mayutils.__name__
'mayutils'
"""

from __future__ import annotations

import contextlib
from functools import lru_cache
from importlib import metadata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

DISTRIBUTION_NAME = "mayutils"

# Import names for distributions whose top-level module differs from the
# ``name.replace("-", "_")`` heuristic. ``modules_for_distribution`` reads the
# authoritative ``top_level.txt`` when a distribution is installed, but falls
# back to the heuristic when it is not — which is exactly when an install hint
# is needed. These overrides keep the hint actionable for the name-mismatched
# optional dependencies declared in ``pyproject.toml``. Keys are PEP 503
# normalised distribution names (see :func:`normalise_dist_name`).
DIST_MODULE_OVERRIDES: dict[str, tuple[str, ...]] = {
    "pillow": ("PIL",),
    "python-pptx": ("pptx",),
    "python-docx": ("docx",),
    "python-dotenv": ("dotenv",),
    "pymupdf": ("pymupdf", "fitz"),
    "scikit-learn": ("sklearn",),
    "google-api-python-client": ("googleapiclient",),
    "google-auth": ("google",),
    "google-cloud-storage": ("google",),
    "snowflake-connector-python": ("snowflake",),
    "snowflake-sqlalchemy": ("snowflake",),
    "gitpython": ("git",),
}


def normalise_dist_name(
    dist: str,
    /,
) -> str:
    """
    Canonicalise a PyPI distribution name for comparison.

    Applies PEP 503-style lower-casing, whitespace stripping, and
    underscore-to-hyphen conversion so that distribution names can be
    matched irrespective of how they appear in ``Requires-Dist`` metadata
    or user input. The canonical form is what
    :func:`importlib.metadata.distribution` expects and what
    :class:`packaging.requirements.Requirement` emits, so this keeps the
    lookup layer consistent across heterogeneous data sources.

    Parameters
    ----------
    dist
        Raw distribution name as it appears in packaging metadata or a
        user-supplied string (for example ``"Scikit_Learn"``).

    Returns
    -------
        The canonical, lower-case, hyphen-separated form suitable for
        equality comparison against other normalised distribution names.

    See Also
    --------
    modules_for_distribution : Consumes the canonical form to resolve
        importable module names from dist-info metadata.
    parse_requires_dist_line : Upstream parser that yields raw
        distribution names requiring normalisation.
    importlib.metadata : Library whose ``distribution`` and ``metadata``
        helpers assume PEP 503-normalised project names.
    packaging.requirements.Requirement : Reference parser that applies
        the same canonicalisation rules to ``Requires-Dist`` strings.
    mayutils.__init__.setup : Entry point that invokes these utilities
        when optional dependencies are resolved.

    Examples
    --------
    >>> from mayutils.core.extras import normalise_dist_name
    >>> normalise_dist_name(" Scikit_Learn ")
    'scikit-learn'
    >>> normalise_dist_name("Plotly")
    'plotly'
    """
    return dist.strip().lower().replace("_", "-")


def modules_for_distribution(
    dist: str,
    /,
) -> tuple[str, ...]:
    """
    Return the top-level importable modules shipped by ``dist``.

    Reads ``top_level.txt`` from the installed distribution's dist-info
    metadata when available, which is the authoritative source of the
    import names a distribution exposes. If the distribution is not
    installed or has no ``top_level.txt``, the curated
    :data:`DIST_MODULE_OVERRIDES` table is consulted for distributions
    whose import name differs from the distribution name (for example
    ``pillow`` exposes ``PIL`` and ``scikit-learn`` exposes ``sklearn``).
    Distributions absent from both metadata and the override table fall
    back to a single-element tuple built with the hyphen-to-underscore
    heuristic, which is correct for most PyPI packages.

    Parameters
    ----------
    dist
        PyPI distribution name (the string that appears on the left-hand
        side of a ``Requires-Dist`` entry) whose import-time module
        names should be resolved.

    Returns
    -------
        Top-level module names that ``import`` statements would target
        when using the distribution. Always non-empty; contains the
        fallback guess when metadata cannot be read.

    See Also
    --------
    normalise_dist_name : Applied to build the fallback module name when
        ``top_level.txt`` is unavailable.
    load_extras_map : Consumer that expands each requirement into the
        set of modules this helper returns.
    importlib.metadata : Source of ``distribution`` and
        ``PackageNotFoundError`` used to locate dist-info metadata.
    packaging.requirements.Requirement : Describes the distribution
        names passed in by upstream parsing.
    mayutils.__init__.setup : Bootstrap layer that depends on these
        module lookups to give actionable hints.

    Examples
    --------
    >>> from mayutils.core.extras import modules_for_distribution
    >>> modules = modules_for_distribution("mayutils")
    >>> isinstance(modules, tuple)
    True
    >>> len(modules) >= 1
    True
    >>> "mayutils" in modules
    True
    """
    try:
        distribution = metadata.distribution(distribution_name=dist)
    except metadata.PackageNotFoundError:
        pass
    else:
        top_level = distribution.read_text(filename="top_level.txt")
        if top_level:
            modules = tuple(line.strip() for line in top_level.splitlines() if line.strip())
            if modules:
                return modules

    normalised = normalise_dist_name(dist)
    override = DIST_MODULE_OVERRIDES.get(normalised)
    if override is not None:
        return override

    return (normalised.replace("-", "_"),)


def parse_requires_dist_line(
    line: str,
    /,
) -> tuple[str, str | None]:
    """
    Split a ``Requires-Dist`` metadata line into its component parts.

    Parses a single PEP 508 requirement string as it appears in the
    ``Requires-Dist`` headers of ``METADATA``, isolating the bare
    distribution name from any version specifiers, extras brackets, or
    environment markers. The ``extra == '<name>'`` marker clause, if
    present, is extracted so the caller can associate the requirement
    with an optional-dependency group. Other marker clauses such as
    ``python_version`` or ``sys_platform`` are ignored for this purpose
    because they do not partition requirements by extras.

    Parameters
    ----------
    line
        Full ``Requires-Dist`` value, including any version specifiers
        and PEP 508 environment markers after a semicolon (for example
        ``"plotly>=5.0; extra == 'plotting'"``).

    Returns
    -------
        A two-tuple whose first element is the distribution name with
        all specifier characters stripped, and whose second element is
        the name of the extras group the requirement belongs to, or
        ``None`` if the requirement is unconditional.

    See Also
    --------
    load_extras_map : Primary consumer that feeds each parsed line into
        the module-to-extras lookup table.
    normalise_dist_name : Used downstream to canonicalise the extracted
        distribution name.
    importlib.metadata : Provides the ``Requires-Dist`` values this
        function parses.
    packaging.requirements.Requirement : Reference parser for PEP 508
        requirement strings; used here in a lightweight form to avoid
        a hard dependency.
    mayutils.__init__.setup : Consumer that relies on the parsed
        extras to surface install hints.

    Examples
    --------
    >>> from mayutils.core.extras import parse_requires_dist_line
    >>> parse_requires_dist_line("plotly>=5.0; extra == 'plotting'")
    ('plotly', 'plotting')
    >>> parse_requires_dist_line("numpy>=1.24")
    ('numpy', None)
    """
    dep, _, markers = line.partition(";")
    dist_name = (
        dep.split("[", maxsplit=1)[0]
        .split(">", maxsplit=1)[0]
        .split("<", maxsplit=1)[0]
        .split("=", maxsplit=1)[0]
        .split("!", maxsplit=1)[0]
        .split("~", maxsplit=1)[0]
        .strip()
    )
    extra: str | None = None
    for clause in markers.split("and"):
        clause_stripped = clause.strip()
        if clause_stripped.startswith("extra"):
            extra = clause_stripped.split("==", maxsplit=1)[-1].strip().strip("'\"")
            break

    return dist_name, extra


@lru_cache(maxsize=1)
def load_extras_map() -> dict[str, frozenset[str]]:
    """
    Build the module-to-extras lookup table from installed metadata.

    Iterates the ``Requires-Dist`` headers of the ``mayutils``
    distribution, keeps only entries guarded by an ``extra == '<name>'``
    marker, and expands each distribution into the top-level module
    names it exposes. The resulting mapping is the authoritative
    runtime view of which optional-dependency group(s) satisfy any
    given import. The result is memoised via
    :func:`functools.lru_cache` because the underlying metadata does
    not change during a process lifetime and parsing is non-trivial.

    Returns
    -------
        Mapping from top-level module name to the set of extras whose
        requirement entries provide that module. Empty when the
        ``mayutils`` distribution itself cannot be located (for example
        during unusual editable-install scenarios).

    See Also
    --------
    parse_requires_dist_line : Parses the individual requirement lines
        consumed here.
    modules_for_distribution : Expands each requirement's distribution
        name into importable module names.
    extras_for_module : Primary consumer that queries this table at
        ``ImportError`` time.
    importlib.metadata : Provides the ``Requires-Dist`` headers this
        function iterates.
    packaging.requirements.Requirement : Describes the PEP 508 grammar
        of the strings processed here.
    mayutils.__init__.setup : Relies on the populated map to surface
        install hints to end users.

    Examples
    --------
    >>> from mayutils.core.extras import load_extras_map
    >>> mapping = load_extras_map()
    >>> isinstance(mapping, dict)
    True
    >>> len(mapping) > 0
    True
    """
    try:
        meta = metadata.metadata(distribution_name=DISTRIBUTION_NAME)
    except metadata.PackageNotFoundError:
        return {}

    requires = meta.get_all(name="Requires-Dist") or []
    result: dict[str, set[str]] = {}

    for line in requires:
        dist_name, extra = parse_requires_dist_line(line)
        if extra is None or not dist_name:
            continue
        for module in modules_for_distribution(dist_name):
            result.setdefault(module, set()).add(extra)

    return {key: frozenset(value) for key, value in result.items()}


def extras_for_module(
    module_name: str,
    /,
) -> frozenset[str]:
    """
    Resolve the optional-dependency extras that supply a given import.

    Walks the dotted components of ``module_name`` from the most
    specific prefix to the least specific, returning the first match
    found in the extras map. This prefix walk means a failed
    ``import plotly.graph_objects`` still resolves to the extras that
    ship ``plotly``, even though only the top-level package appears in
    ``top_level.txt``. Returning an empty frozenset signals that no
    declared extra ships the module, in which case callers should fall
    back to a generic "not installed" message.

    Parameters
    ----------
    module_name
        Dotted import path of the module whose provenance is being
        queried (for example ``"plotly.graph_objects"``). The exact
        string as reported by :attr:`ImportError.name` is suitable.

    Returns
    -------
        Names of the extras groups whose requirements include a
        distribution exposing ``module_name`` (or any ancestor dotted
        prefix). Empty when no declared extra ships the module.

    See Also
    --------
    load_extras_map : Source of the underlying lookup table.
    format_missing_extra_hint : Primary consumer that formats the
        extras returned here into a user-facing message.
    importlib.metadata : Ultimate source of the data used to build the
        extras map.
    packaging.requirements.Requirement : Describes the PEP 508 grammar
        of the underlying metadata.
    mayutils.__init__.setup : Downstream consumer that relies on these
        lookups to surface install hints.

    Examples
    --------
    >>> from mayutils.core.extras import extras_for_module
    >>> isinstance(extras_for_module("plotly.graph_objects"), frozenset)
    True
    """
    mapping = load_extras_map()
    parts = module_name.split(".")
    for index in range(len(parts), 0, -1):
        candidate = ".".join(parts[:index])
        if candidate in mapping:
            return mapping[candidate]
    return frozenset()


def format_missing_extra_hint(
    module_name: str,
    /,
    *,
    extras: tuple[str, ...] | None = None,
) -> str:
    """
    Build a human-readable install hint for a missing optional dependency.

    Produces the diagnostic string appended to :class:`ImportError`
    messages raised inside :func:`requires_extras` and
    :func:`may_require_extras`. The wording changes depending on whether
    a single extra, multiple extras, or no extras satisfy the failing
    import, so that users see an actionable command wherever possible.
    Keeping this formatting in one place ensures both context managers
    and any future callers emit identical guidance.

    Parameters
    ----------
    module_name
        Dotted import path that failed to resolve, typically sourced
        from :attr:`ImportError.name`. Used both in the rendered message
        and as the lookup key against the extras map when ``extras`` is
        omitted.
    extras
        Explicit override of the extras groups to suggest, bypassing the
        automatic lookup. Supply this when a submodule is known to
        depend on multiple extras simultaneously or when the automatic
        resolution would be incorrect (for example for namespaced
        imports not present in ``top_level.txt``). When ``None``, the
        extras are resolved via :func:`extras_for_module`.

    Returns
    -------
        A ready-to-display diagnostic ending in a ``uv add`` /
        ``pip install`` suggestion naming the relevant extras, or a
        generic "not installed" fallback when no extra is known to ship
        the module.

    See Also
    --------
    extras_for_module : Consulted to auto-resolve extras when none are
        supplied explicitly.
    requires_extras : Context manager that emits this hint on failure
        with a caller-provided extras list.
    may_require_extras : Context manager that emits this hint on
        failure using the auto-resolved extras.
    importlib.metadata : Foundation of the extras map this helper
        ultimately reads from.
    packaging.requirements.Requirement : PEP 508 grammar underlying the
        extras-to-distribution resolution.
    mayutils.__init__.setup : Consumer that relies on the resulting
        message to guide installation.

    Examples
    --------
    >>> from mayutils.core.extras import format_missing_extra_hint
    >>> hint = format_missing_extra_hint(
    ...     "plotly.graph_objects",
    ...     extras=("plotting",),
    ... )
    >>> "mayutils[plotting]" in hint
    True
    """
    hint_extras = tuple(sorted(extras)) if extras else tuple(sorted(extras_for_module(module_name)))
    if not hint_extras:
        return f"Optional dependency '{module_name}' is not installed."

    if len(hint_extras) == 1:
        extra = hint_extras[0]
        return (
            f"Optional dependency '{module_name}' is not installed. "
            f'Install it with: uv add "mayutils[{extra}]" '
            f'(or pip install "mayutils[{extra}]").'
        )

    options = " or ".join(f'"mayutils[{extra}]"' for extra in hint_extras)

    return f"Optional dependency '{module_name}' is not installed. It is available from any of: {options}."


@contextlib.contextmanager
def requires_extras(
    *extras: str,
) -> Generator[None]:
    """
    Re-raise any :class:`ImportError` with an explicit install hint.

    Context manager intended to wrap the optional-dependency imports at
    the top of a submodule. When an :class:`ImportError` escapes the
    ``with`` block, the original exception is chained and a new
    :class:`ImportError` is raised whose message includes an install
    suggestion naming the extras passed as arguments. Use this variant
    when the caller needs to force a specific hint, for example when a
    namespaced import is not present in the extras map or when multiple
    extras must be installed together.

    Parameters
    ----------
    *extras
        Names of extras (groups defined in
        ``[project.optional-dependencies]`` of ``pyproject.toml``) that
        together satisfy the wrapped imports. When empty, the hint is
        derived automatically from the failing module name, matching
        the behaviour of :func:`may_require_extras`.

    Yields
    ------
        Control is yielded once, during which the guarded imports
        execute.

    Raises
    ------
    ImportError
        Chained from the original import failure, with the install hint
        appended to the message so it surfaces in tracebacks and
        REPL output.

    See Also
    --------
    may_require_extras : Zero-argument variant that derives the hint
        automatically from ``pyproject.toml``.
    format_missing_extra_hint : Formats the hint appended to the
        re-raised exception.
    extras_for_module : Consulted when ``extras`` is empty to match the
        behaviour of :func:`may_require_extras`.
    importlib.metadata : Source of the metadata backing the hint.
    packaging.requirements.Requirement : Describes the PEP 508 grammar
        underlying the extras resolution.
    mayutils.__init__.setup : Downstream consumer that relies on this
        guard to turn silent import failures into actionable messages.

    Examples
    --------
    >>> from mayutils.core.extras import requires_extras
    >>> with requires_extras("plotting"):
    ...     import mayutils
    >>> mayutils.__name__
    'mayutils'
    >>> try:
    ...     with requires_extras("plotting"):
    ...         import definitely_not_a_real_module_xyz
    ... except ImportError as err:
    ...     "mayutils[plotting]" in str(err)
    True
    """
    try:
        yield

    except ImportError as err:
        module_name = getattr(err, "name", None) or "dependency"
        hint = format_missing_extra_hint(
            module_name,
            extras=extras or None,
        )
        original = err.msg if hasattr(err, "msg") else str(err)
        msg = f"{original}\n{hint}"

        raise ImportError(msg, name=module_name) from err


@contextlib.contextmanager
def may_require_extras() -> Generator[None]:
    """
    Re-raise any :class:`ImportError` with an auto-resolved install hint.

    Behaves like :func:`requires_extras` but takes no arguments: the
    failing import's module name is looked up against the extras map
    derived from ``pyproject.toml`` via :func:`extras_for_module`, so
    the hint stays authoritative without the call site needing to
    repeat the group name. This is the preferred entry point for
    submodules with heavy top-of-file imports because it removes the
    maintenance burden of keeping the wrapper argument in sync with
    the extras declaration.

    Yields
    ------
        Control is yielded once, during which the guarded imports
        execute.

    See Also
    --------
    requires_extras : Variant that accepts an explicit extras list when
        automatic resolution is insufficient.
    extras_for_module : Performs the auto-resolution consulted here.
    format_missing_extra_hint : Formats the appended diagnostic.
    importlib.metadata : Source of the metadata backing the hint.
    packaging.requirements.Requirement : Describes the PEP 508 grammar
        underlying the extras resolution.
    mayutils.__init__.setup : Downstream consumer that wraps heavy
        top-of-file imports with this guard.

    Examples
    --------
    >>> from mayutils.core.extras import may_require_extras
    >>> with may_require_extras():
    ...     import mayutils
    >>> mayutils.__name__
    'mayutils'
    >>> try:
    ...     with may_require_extras():
    ...         import definitely_not_a_real_module_xyz
    ... except ImportError as err:
    ...     "not installed" in str(err)
    True
    """
    with requires_extras():
        yield
