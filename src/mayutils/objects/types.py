"""Shared typing aliases (``Scale``, ``Operation``, recursive dict/list containers)."""

from __future__ import annotations

from typing import TypeVar

K = TypeVar(name="K")
V = TypeVar(name="V")


class RecursiveDict[K, V](
    dict[K, "V | RecursiveDict[K, V]"],
):
    """Arbitrarily nested mapping — value may be a leaf ``V`` or another :class:`RecursiveDict`.

    Subclass of :class:`dict` that aliases the generic type
    ``dict[K, V | RecursiveDict[K, V]]``. Used for tree-shaped data
    such as nested configs or icicle-chart payloads.

    Type Parameters
    ---------------
    K
        Key type of the mapping.
    V
        Leaf value type; nested dicts are allowed via the recursive
        alias.

    Examples
    --------
    >>> RecursiveDict[str, int]({"a": 1, "b": {"c": 2}})
    {'a': 1, 'b': {'c': 2}}
    """
