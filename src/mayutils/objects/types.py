"""Shared typing primitives for structured data containers.

This module defines reusable typing constructs used across ``mayutils`` for
representing JSON payloads, recursively nested mappings and lightweight
structural protocols. ``JsonString`` and ``JsonParsed`` distinguish the
raw serialised form of JSON from its parsed Python representation at the
type level, while :class:`RecursiveDict` models tree-shaped data whose
leaves share a common value type. The :class:`SupportsStr` protocol is
used to constrain inputs to anything that can be coerced to ``str`` via
``__str__``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NewType, Protocol

JsonString = NewType("JsonString", str)
"""str: Distinct string subtype marking values that hold a serialised JSON document.

Used as an annotation to differentiate a raw JSON payload awaiting
parsing from an arbitrary ``str``, providing stricter static checks on
functions that consume or produce serialised JSON.
"""

JsonParsed = NewType("JsonParsed", Mapping[str, Any])
"""Mapping[str, Any]: Distinct mapping subtype marking parsed JSON object payloads.

Represents the in-memory result of decoding a JSON object into a
string-keyed mapping, keeping parsed payloads typed separately from
generic mappings in the call graph.
"""


class RecursiveDict[K, V](
    dict[K, "V | RecursiveDict[K, V]"],
):
    """Dictionary whose values are either leaves or further nested dictionaries.

    This class is a generic subclass of :class:`dict` whose value type is
    the recursive union ``V | RecursiveDict[K, V]``. It is intended for
    tree-shaped payloads such as nested configuration trees or
    hierarchical chart data where each node may carry either a terminal
    value or a further mapping of the same shape.

    Parameters
    ----------
    K
        Type of the mapping keys at every level of the tree.
    V
        Type of the leaf values; interior nodes are :class:`RecursiveDict`
        instances parameterised by the same ``K`` and ``V``.

    Examples
    --------
    >>> RecursiveDict[str, int]({"a": 1, "b": {"c": 2}})
    {'a': 1, 'b': {'c': 2}}
    """


class SupportsStr(Protocol):
    """Structural protocol for objects convertible to :class:`str`.

    Any object exposing a ``__str__`` method returning a :class:`str`
    satisfies this protocol, making it usable wherever a stringifiable
    value is expected without requiring a concrete base class.
    """

    def __str__(
        self,
    ) -> str:
        """Return the string representation of the object.

        Returns
        -------
        str
            Human-readable string form of the implementing object.
        """
        ...
