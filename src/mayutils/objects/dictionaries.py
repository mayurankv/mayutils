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


def invert_dict[K: Hashable, V: Hashable](
    mapping: Mapping[K, V],
    /,
) -> dict[V, K]:
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
