"""
Provide utilities for transforming and manipulating Python dictionaries.

This module collects helpers that operate on :class:`~collections.abc.Mapping`
instances and return new :class:`dict` objects. The helpers are designed to
preserve the input mapping and to work with arbitrary hashable key and value
types through generic type parameters, enabling static type checkers to infer
the resulting dict's key and value types from the argument.

See Also
--------
collections.ChainMap : Layered lookup across multiple mappings.
dict.update : In-place shallow merge of two dictionaries.
typing.Mapping : Structural protocol describing read-only mappings.

Examples
--------
>>> from mayutils.objects.dictionaries import invert_dict
>>> invert_dict({"a": 1, "b": 2})
{1: 'a', 2: 'b'}
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from mayutils.objects.types import RecursiveMapping, SupportsStr


def invert_dict[Key: Hashable, Value: Hashable](
    mapping: Mapping[Key, Value],
    /,
) -> dict[Value, Key]:
    """
    Swap the keys and values of a mapping to produce a reversed dictionary.

    The function iterates over ``mapping`` in insertion order and assigns each
    original value as a key in the returned dict, pointing to the original key.
    When multiple original keys share the same value, the key encountered last
    during iteration overwrites any earlier association, so the caller is
    responsible for guaranteeing value uniqueness whenever a bijective
    inversion is required. The algorithm performs a single ``O(n)`` pass over
    the input and allocates a fresh :class:`dict`, leaving ``mapping`` untouched.

    Parameters
    ----------
    mapping
        Source mapping whose key-value pairs should be reversed. Keys may be
        any hashable type ``K``, and values must satisfy ``V: Hashable`` so
        that they can serve as dictionary keys in the result.

    Returns
    -------
        A newly constructed dictionary in which every value from ``mapping``
        becomes a key mapped to the original key. The input mapping is not
        mutated.

    See Also
    --------
    dict.items : Source iterator used to enumerate the pairs being swapped.
    collections.ChainMap : Alternative when layering lookups rather than
        flipping them.
    typing.Mapping : Structural interface accepted by the ``mapping`` argument.

    Examples
    --------
    >>> invert_dict({"a": 1, "b": 2})
    {1: 'a', 2: 'b'}
    >>> invert_dict({"a": 1, "b": 1})  # later key wins on collisions
    {1: 'b'}
    """
    return {value: key for key, value in mapping.items()}


def flatten_dict(
    mapping: RecursiveMapping[str, SupportsStr],
    /,
    *,
    prefix: str = "",
    separator: str = "_",
) -> list[str]:
    """
    Recursively flatten a nested mapping into ``key{sep}value`` strings.

    Walks the mapping depth-first and joins each path of keys with the
    separator, appending the leaf value at the end.

    Parameters
    ----------
    mapping
        Input mapping, possibly containing nested dicts.
    prefix
        Key prefix prepended to each output token.
    separator
        Separator between key segments and between key and value.

    Returns
    -------
    list[str]
        Flat list of ``key_value`` strings.

    See Also
    --------
    invert_dict : Swap keys and values of a flat mapping.

    Examples
    --------
    >>> flatten_dict({"a": 1, "b": {"c": 2}})
    ['a_1', 'b_c_2']
    >>> flatten_dict({"x": "y"}, prefix="p")
    ['p_x_y']
    """
    parts: list[str] = []

    for key, value in mapping.items():
        full_key = f"{prefix}{separator}{key}" if prefix else key

        if isinstance(value, Mapping):
            parts.extend(flatten_dict(cast("RecursiveMapping[str, SupportsStr]", value), prefix=full_key, separator=separator))
        else:
            parts.append(f"{full_key}{separator}{value}")

    return parts
