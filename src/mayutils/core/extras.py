"""Resolve which optional extra provides a given optional dependency.

This module inspects the ``mayutils`` distribution metadata at runtime to
map importable module names back to the ``[project.optional-dependencies]``
extras that declare them, and exposes context managers that convert bare
:class:`ImportError` failures into actionable ``uv add``/``pip install``
hints. Mapping data is derived dynamically from the installed package
metadata: extras-to-distributions comes from parsing the ``Requires-Dist``
headers for ``extra == '<name>'`` markers, while distribution-to-modules
is read from the dist-info ``top_level.txt`` when the distribution is
installed, falling back to ``dist_name.replace("-", "_")`` when it is not
(so hints for distributions with non-obvious import names, such as
``pillow`` -> ``PIL`` or ``scikit-learn`` -> ``sklearn``, may be generic
when the dist is absent). The :func:`may_require_extras` context manager
is the primary entry point for submodules with heavy top-of-file imports
because it auto-resolves the matching extra(s) from ``pyproject.toml`` at
``ImportError`` time; :func:`requires_extras` remains available when a
specific hint must be forced.

Examples
--------
>>> from mayutils.core.extras import may_require_extras
>>> with may_require_extras():
...     import plotly.graph_objects as go  # doctest: +SKIP
"""

from __future__ import annotations

import contextlib
from functools import lru_cache
from importlib import metadata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

DISTRIBUTION_NAME = "mayutils"


def _normalise_dist_name(
    *,
    dist: str,
) -> str:
    """Canonicalise a PyPI distribution name for comparison.

    Applies PEP 503-style lower-casing, whitespace stripping, and
    underscore-to-hyphen conversion so that distribution names can be
    matched irrespective of how they appear in ``Requires-Dist`` metadata
    or user input.

    Parameters
    ----------
    dist : str
        Raw distribution name as it appears in packaging metadata or a
        user-supplied string (for example ``"Scikit_Learn"``).

    Returns
    -------
    str
        The canonical, lower-case, hyphen-separated form suitable for
        equality comparison against other normalised distribution names.
    """
    return dist.strip().lower().replace("_", "-")


def modules_for_distribution(
    *,
    dist: str,
) -> tuple[str, ...]:
    """Return the top-level importable modules shipped by ``dist``.

    Reads ``top_level.txt`` from the installed distribution's dist-info
    metadata when available, which is the authoritative source of the
    import names a distribution exposes. If the distribution is not
    installed or has no ``top_level.txt``, a single-element tuple is
    returned using the hyphen-to-underscore fallback — this is a best
    effort that is correct for most PyPI packages but can miss cases
    where the import name differs from the distribution name (e.g.
    ``pillow`` -> ``PIL``).

    Parameters
    ----------
    dist : str
        PyPI distribution name (the string that appears on the left-hand
        side of a ``Requires-Dist`` entry) whose import-time module
        names should be resolved.

    Returns
    -------
    tuple[str, ...]
        Top-level module names that ``import`` statements would target
        when using the distribution. Always non-empty; contains the
        fallback guess when metadata cannot be read.
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

    return (_normalise_dist_name(dist=dist).replace("-", "_"),)


def parse_requires_dist_line(
    *,
    line: str,
) -> tuple[str, str | None]:
    """Split a ``Requires-Dist`` metadata line into its component parts.

    Parses a single PEP 508 requirement string as it appears in the
    ``Requires-Dist`` headers of ``METADATA``, isolating the bare
    distribution name from any version specifiers, extras brackets, or
    environment markers, and identifying the ``extra == '<name>'``
    marker clause (if any) that associates the requirement with an
    optional-dependency group.

    Parameters
    ----------
    line : str
        Full ``Requires-Dist`` value, including any version specifiers
        and PEP 508 environment markers after a semicolon (for example
        ``"plotly>=5.0; extra == 'plotting'"``).

    Returns
    -------
    tuple[str, str | None]
        A two-tuple whose first element is the canonicalised-by-slicing
        distribution name with all specifier characters stripped, and
        whose second element is the name of the extras group the
        requirement belongs to, or ``None`` if the requirement is
        unconditional.
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
    """Build the module-to-extras lookup table from installed metadata.

    Iterates the ``Requires-Dist`` headers of the ``mayutils``
    distribution, keeps only entries guarded by an ``extra == '<name>'``
    marker, and expands each distribution into the top-level module
    names it exposes. The resulting mapping is the authoritative
    runtime view of which optional-dependency group(s) satisfy any
    given import. The result is memoised via :func:`functools.lru_cache`
    because the underlying metadata does not change during a process
    lifetime and parsing is non-trivial.

    Returns
    -------
    dict[str, frozenset[str]]
        Mapping from top-level module name to the set of extras whose
        requirement entries provide that module. Empty when the
        ``mayutils`` distribution itself cannot be located (e.g. during
        unusual editable-install scenarios).
    """
    try:
        meta = metadata.metadata(distribution_name=DISTRIBUTION_NAME)
    except metadata.PackageNotFoundError:
        return {}

    requires = meta.get_all(name="Requires-Dist") or []
    result: dict[str, set[str]] = {}

    for line in requires:
        dist_name, extra = parse_requires_dist_line(line=line)
        if extra is None or not dist_name:
            continue
        for module in modules_for_distribution(dist=dist_name):
            result.setdefault(module, set()).add(extra)

    return {key: frozenset(value) for key, value in result.items()}


def extras_for_module(
    *,
    module_name: str,
) -> frozenset[str]:
    """Resolve the optional-dependency extras that supply a given import.

    Walks the dotted components of ``module_name`` from the most specific
    prefix to the least specific, returning the first match found in the
    extras map. This prefix walk means a failed ``import
    plotly.graph_objects`` still resolves to the extras that ship
    ``plotly``, even though only the top-level package appears in
    ``top_level.txt``.

    Parameters
    ----------
    module_name : str
        Dotted import path of the module whose provenance is being
        queried (for example ``"plotly.graph_objects"``). The exact
        string as reported by :attr:`ImportError.name` is suitable.

    Returns
    -------
    frozenset[str]
        Names of the extras groups whose requirements include a
        distribution exposing ``module_name`` (or any ancestor dotted
        prefix). Empty when no declared extra ships the module, in
        which case callers should fall back to a generic message.
    """
    mapping = load_extras_map()
    parts = module_name.split(".")
    for index in range(len(parts), 0, -1):
        candidate = ".".join(parts[:index])
        if candidate in mapping:
            return mapping[candidate]
    return frozenset()


def format_missing_extra_hint(
    *,
    module_name: str,
    extras: tuple[str, ...] | None = None,
) -> str:
    """Build a human-readable install hint for a missing optional dependency.

    Produces the diagnostic string appended to :class:`ImportError`
    messages raised inside :func:`requires_extras` and
    :func:`may_require_extras`. The wording changes depending on whether
    a single extra, multiple extras, or no extras satisfy the failing
    import, so that users see an actionable command wherever possible.

    Parameters
    ----------
    module_name : str
        Dotted import path that failed to resolve, typically sourced
        from :attr:`ImportError.name`. Used both in the rendered message
        and as the lookup key against the extras map when ``extras`` is
        omitted.
    extras : tuple[str, ...] | None, optional
        Explicit override of the extras groups to suggest, bypassing the
        automatic lookup. Supply this when a submodule is known to
        depend on multiple extras simultaneously or when the automatic
        resolution would be incorrect (for example for namespaced
        imports not present in ``top_level.txt``). When ``None``, the
        extras are resolved via :func:`extras_for_module`.

    Returns
    -------
    str
        A ready-to-display diagnostic ending in a ``uv add`` / ``pip
        install`` suggestion naming the relevant extras, or a generic
        "not installed" fallback when no extra is known to ship the
        module.
    """
    hint_extras = tuple(sorted(extras)) if extras else tuple(sorted(extras_for_module(module_name=module_name)))
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
) -> Iterator[None]:
    """Re-raise any :class:`ImportError` with an explicit install hint.

    Context manager intended to wrap the optional-dependency imports at
    the top of a submodule. When an :class:`ImportError` escapes the
    ``with`` block, the original exception is chained and a new
    :class:`ImportError` is raised whose message includes an install
    suggestion naming the extras passed as arguments. Use this variant
    when the caller needs to force a specific hint — for example when a
    namespaced import is not present in the extras map or when multiple
    extras must be installed together.

    Parameters
    ----------
    *extras : str
        Names of extras (groups defined in
        ``[project.optional-dependencies]`` of ``pyproject.toml``) that
        together satisfy the wrapped imports. When empty, the hint is
        derived automatically from the failing module name, matching
        the behaviour of :func:`may_require_extras`.

    Yields
    ------
    None
        Control is yielded once, during which the guarded imports
        execute.

    Raises
    ------
    ImportError
        Chained from the original import failure, with the install hint
        appended to the message so it surfaces in tracebacks and
        REPL output.

    Examples
    --------
    >>> from mayutils.core.extras import requires_extras
    >>> with requires_extras("plotting"):
    ...     import plotly  # doctest: +SKIP
    """
    try:
        yield

    except ImportError as err:
        module_name = getattr(err, "name", None) or "dependency"
        hint = format_missing_extra_hint(
            module_name=module_name,
            extras=extras or None,
        )
        original = err.msg if hasattr(err, "msg") else str(err)
        msg = f"{original}\n{hint}"

        raise ImportError(msg, name=module_name) from err


@contextlib.contextmanager
def may_require_extras() -> Iterator[None]:
    """Re-raise any :class:`ImportError` with an auto-resolved install hint.

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
    None
        Control is yielded once, during which the guarded imports
        execute.

    Raises
    ------
    ImportError
        Chained from the original import failure, with the
        automatically resolved install hint appended to the message so
        it surfaces in tracebacks.

    Examples
    --------
    >>> from mayutils.core.extras import may_require_extras
    >>> with may_require_extras():
    ...     import plotly  # doctest: +SKIP
    """
    with requires_extras():
        yield
