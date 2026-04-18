"""Resolve which optional extra provides a given optional dependency.

All mapping data is derived dynamically from the installed package metadata:

1. **Extras → distributions** come from the package's ``Requires-Dist``
   headers (parsed for ``extra == '<name>'`` markers).
2. **Distribution → importable modules** — for installed distributions,
   the ``top_level.txt`` file in the dist-info metadata is read. For
   uninstalled distributions, the naive fallback is
   ``dist_name.replace("-", "_")``, which means hints for distributions
   with non-obvious import names (e.g. ``pillow`` → ``PIL``,
   ``scikit-learn`` → ``sklearn``) may be generic if the dist isn't
   installed at the point the hint is rendered.

The :func:`requires_extras` context manager is the primary entry point for
submodules with heavy top-of-file imports — pass the extras explicitly so
the hint is authoritative regardless of installed-metadata availability.

Examples
--------
>>> from mayutils.core.extras import requires_extras
>>> with requires_extras("plotting"):
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
    return dist.strip().lower().replace("_", "-")


def _modules_for_distribution(
    *,
    dist: str,
) -> tuple[str, ...]:
    """Return the top-level importable modules for ``dist``.

    Parameters
    ----------
    dist : str
        Dist.

    Returns
    -------
    tuple[str, ...]
        The return value.
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


def _parse_requires_dist_line(line: str) -> tuple[str, str | None]:
    """Split a ``Requires-Dist`` line into ``(dist_name, extra_or_None)``.

    Parameters
    ----------
    line : str
        Line.

    Returns
    -------
    tuple[str, str | None]
        The return value.
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
def _load_extras_map() -> dict[str, frozenset[str]]:
    """Return ``{module_name: frozenset(extras_providing_it)}``.

    Returns
    -------
    dict[str, frozenset[str]]
        The return value.
    """
    try:
        meta = metadata.metadata(distribution_name=DISTRIBUTION_NAME)
    except metadata.PackageNotFoundError:
        return {}

    requires = meta.get_all(name="Requires-Dist") or []
    result: dict[str, set[str]] = {}

    for line in requires:
        dist_name, extra = _parse_requires_dist_line(line=line)
        if extra is None or not dist_name:
            continue
        for module in _modules_for_distribution(dist=dist_name):
            result.setdefault(module, set()).add(extra)

    return {key: frozenset(value) for key, value in result.items()}


def extras_for_module(
    *,
    module_name: str,
) -> frozenset[str]:
    """Return the extras that provide ``module_name`` (or any parent module).

    Parameters
    ----------
    module_name : str
        Dotted import path (e.g. ``"plotly.graph_objects"``).

    Returns
    -------
    frozenset[str]
        Extras whose distributions include a module matching ``module_name``
        or any of its ancestor dotted prefixes. Empty when no match is found.
    """
    mapping = _load_extras_map()
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

    Parameters
    ----------
    module_name : str
        The import name that failed to resolve.
    extras : tuple[str, ...] | None
        Override the extras resolved automatically (e.g. when a submodule
        depends on multiple extras at once).

    Returns
    -------
    str
        A message ending in a ``uv add``/``pip install`` suggestion, or a
        generic fallback when no extra is known.
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
    """Re-raise any :class:`ImportError` with an install hint.

    Use at the top of a submodule whose imports depend on optional extras.

    Parameters
    ----------
    *extras : str
        One or more extras (groups defined in
        ``[project.optional-dependencies]``) that together satisfy the
        wrapped imports.

    Raises
    ------
    ImportError
        Chained from the original, with the hint appended to ``.msg`` so it
        surfaces in tracebacks.

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
