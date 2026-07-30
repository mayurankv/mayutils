"""
Provide accessor utilities for pandas :class:`pandas.Index` objects.

This module registers helpers that extend the behaviour of pandas index
objects with operations that are not available on the native API. In
particular it exposes routines for converting a :class:`pandas.MultiIndex`
into a plain nested ``list`` structure, which is convenient when feeding
index metadata into downstream consumers (for example chart table headers
or serialisation layers) that expect simple Python containers rather than
a pandas index instance.

See Also
--------
pandas.Index : Base index class being wrapped by the accessor.
pandas.MultiIndex : Hierarchical index flattened by :meth:`IndexUtilsAccessor.get_multiindex`.
pandas.RangeIndex : Lightweight integer index that can also be wrapped.

Examples
--------
>>> import pandas as pd
>>> from mayutils.objects.dataframes.pandas.index import IndexUtilsAccessor
>>> mi = pd.MultiIndex.from_tuples([("a", 1), ("a", 2), ("b", 1)], names=["g", "n"])
>>> IndexUtilsAccessor(mi).get_multiindex()
[['a', 1], ['a', 2], ['b', 1]]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mayutils.core.extras import may_require_extras

if TYPE_CHECKING:
    from collections.abc import Hashable

    from pandas import Index


class IndexUtilsAccessor:
    """
    Attach convenience methods to a bound :class:`pandas.Index` instance.

    Instances of this class are bound to a single pandas index and expose
    additional methods, such as converting a multi-level index into plain
    nested Python lists, that are not provided by the native pandas index
    API. The accessor leaves the underlying index untouched and preserves
    its level order, sort state and uniqueness guarantees, so downstream
    callers can keep relying on any invariants the index already satisfies.

    Parameters
    ----------
    index
        The pandas index instance that the accessor is bound to; all
        methods on the accessor operate on this underlying index.

    Attributes
    ----------
    index
        The pandas index instance the accessor wraps and delegates to
        when reading level values or performing type checks.

    See Also
    --------
    pandas.Index : Base class whose instances are wrapped by this accessor.
    pandas.MultiIndex : Hierarchical index consumed by :meth:`get_multiindex`.
    pandas.RangeIndex : Integer index variant that is also accepted as input.

    Examples
    --------
    >>> import pandas as pd
    >>> from mayutils.objects.dataframes.pandas.index import IndexUtilsAccessor
    >>> idx = pd.MultiIndex.from_tuples([("x", 1), ("y", 2)], names=["g", "n"])
    >>> accessor = IndexUtilsAccessor(idx)
    >>> accessor.index.names
    FrozenList(['g', 'n'])
    """

    def __init__(
        self,
        index: Index,
    ) -> None:
        """
        Bind the pandas index that subsequent method calls will target.

        The provided index is stored as :attr:`index` without any copying
        or reordering, so level order, monotonic sort state and any
        uniqueness guarantees attached to the original object remain
        intact. Methods on the accessor therefore operate on the exact
        pandas instance supplied by the caller.

        Parameters
        ----------
        index
            The pandas index instance to be wrapped by this accessor;
            it is assigned to :attr:`index` and used as the data source
            for every method on the accessor.

        See Also
        --------
        IndexUtilsAccessor : Containing accessor that owns this initialiser.
        pandas.Index : Type expected for the ``index`` parameter.
        pandas.MultiIndex : Hierarchical index variant the accessor supports.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.pandas.index import IndexUtilsAccessor
        >>> accessor = IndexUtilsAccessor(pd.Index([1, 2, 3], name="n"))
        >>> accessor.index.name
        'n'
        """
        self.index = index

    def get_multiindex(
        self,
        *,
        transpose: bool = False,
    ) -> list[list[Hashable]]:
        """
        Convert the wrapped :class:`pandas.MultiIndex` into nested lists.

        The method iterates the underlying index in its existing order,
        so any monotonic sort state or level ordering on the original
        :class:`pandas.MultiIndex` is reflected in the returned nested
        list. When ``transpose`` is ``False`` the result is row oriented
        and each inner list corresponds to one index entry; when ``True``
        it is level oriented and each inner list contains every value at
        that level, which is useful for building hierarchical chart or
        table headers. Uniqueness of the index is not altered, so repeated
        tuples in the source index also appear repeatedly in the output.

        Parameters
        ----------
        transpose
            Orientation of the returned nested list. When ``False`` the
            outer list iterates over index rows and each inner list
            contains the level values for that single row. When ``True``
            the outer list iterates over index levels and each inner list
            contains the values of that level across every row of the
            index.

        Returns
        -------
            A nested Python list containing the values of the underlying
            :class:`pandas.MultiIndex`, oriented according to
            ``transpose``.

        Raises
        ------
        TypeError
            Raised when the wrapped index is not an instance of
            :class:`pandas.MultiIndex` and therefore has no levels to
            flatten.

        See Also
        --------
        pandas.MultiIndex : Hierarchical index type this method consumes.
        pandas.MultiIndex.get_level_values : Pandas helper used when
            transposing the index into level oriented lists.
        pandas.Index : Base class from which :class:`pandas.MultiIndex`
            inherits.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.pandas.index import IndexUtilsAccessor
        >>> mi = pd.MultiIndex.from_tuples(
        ...     [("a", 1), ("a", 2), ("b", 1)],
        ...     names=["g", "n"],
        ... )
        >>> IndexUtilsAccessor(mi).get_multiindex()
        [['a', 1], ['a', 2], ['b', 1]]
        >>> IndexUtilsAccessor(mi).get_multiindex(transpose=True)
        [['a', 'a', 'b'], [1, 2, 1]]
        """
        with may_require_extras():
            from pandas import MultiIndex

        if not isinstance(self.index, MultiIndex):
            msg = "Index is not of type MultiIndex"
            raise TypeError(msg)

        return (
            list(map(list, self.index))
            if not transpose
            else [list(self.index.get_level_values(level=level)) for level in range(len(self.index.names))]
        )
