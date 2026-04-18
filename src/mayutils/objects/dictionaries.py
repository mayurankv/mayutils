"""Dictionary helpers."""

from __future__ import annotations

from collections.abc import Hashable, Mapping


def invert_dict[K: Hashable, V: Hashable](
    mapping: Mapping[K, V],
    /,
) -> dict[V, K]:
    """Return a new dict with keys and values swapped.

    Both keys and values of ``mapping`` must be hashable. If two
    original keys share the same value, the last key encountered during
    iteration wins — the caller is responsible for ensuring values are
    unique when a bijective inversion is required.

    Parameters
    ----------
    mapping : Mapping[K, V]
        The mapping to invert. Values must be hashable (``V: Hashable``)
        so they can serve as keys in the returned dict.

    Returns
    -------
    dict[V, K]
        A new dict mapping each value in ``mapping`` to its
        corresponding key.

    Examples
    --------
    >>> invert_dict({"a": 1, "b": 2})
    {1: 'a', 2: 'b'}
    >>> invert_dict({"a": 1, "b": 1})  # later key wins on collisions
    {1: 'b'}
    """
    return {value: key for key, value in mapping.items()}
