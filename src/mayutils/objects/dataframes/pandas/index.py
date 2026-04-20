"""Accessor utilities for pandas :class:`pandas.Index` objects.

This module registers helpers that extend the behaviour of pandas index
objects with operations that are not available on the native API. In
particular it exposes routines for converting a :class:`pandas.MultiIndex`
into a plain nested ``list`` structure, which is convenient when feeding
index metadata into downstream consumers (for example chart table headers
or serialisation layers) that expect simple Python containers rather than
a pandas index instance.
"""

from collections.abc import Hashable

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from pandas import Index, MultiIndex


class IndexUtilsAccessor:
    """Accessor that adds utility methods to a :class:`pandas.Index`.

    Instances of this class are bound to a single pandas index and expose
    additional methods, such as converting a multi-level index into plain
    nested Python lists, that are not provided by the native pandas index
    API.

    Parameters
    ----------
    index : pandas.Index
        The pandas index instance that the accessor is bound to; all
        methods on the accessor operate on this underlying index.

    Attributes
    ----------
    index : pandas.Index
        The pandas index instance the accessor wraps and delegates to
        when reading level values or performing type checks.
    """

    def __init__(
        self,
        index: Index,
    ) -> None:
        """Store the pandas index that subsequent method calls will target.

        Parameters
        ----------
        index : pandas.Index
            The pandas index instance to be wrapped by this accessor;
            it is assigned to :attr:`index` and used as the data source
            for every method on the accessor.
        """
        self.index = index

    def get_multiindex(
        self,
        *,
        transpose: bool = False,
    ) -> list[list[Hashable]]:
        """Convert the wrapped :class:`pandas.MultiIndex` into nested lists.

        Parameters
        ----------
        transpose : bool, default False
            Orientation of the returned nested list. When ``False`` the
            outer list iterates over index rows and each inner list
            contains the level values for that single row. When ``True``
            the outer list iterates over index levels and each inner list
            contains the values of that level across every row of the
            index.

        Returns
        -------
        list of list of Hashable
            A nested Python list containing the values of the underlying
            :class:`pandas.MultiIndex`, oriented according to
            ``transpose``.

        Raises
        ------
        TypeError
            Raised when the wrapped index is not an instance of
            :class:`pandas.MultiIndex` and therefore has no levels to
            flatten.
        """
        if not isinstance(self.index, MultiIndex):
            msg = "Index is not of type MultiIndex"
            raise TypeError(msg)

        return (
            list(map(list, self.index))
            if not transpose
            else [list(self.index.get_level_values(level=level)) for level in range(len(self.index.names))]
        )
