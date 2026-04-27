"""
Provide Polars-specific dataframe helpers for the ``mayutils`` library.

This package is the Polars-specific namespace within
:mod:`mayutils.objects.dataframes`, grouping utilities that operate on
:class:`polars.DataFrame` and :class:`polars.LazyFrame` objects. The
subpackage currently acts as a re-export surface so downstream callers
can import Polars helpers from a single location, mirroring the layout
used by the sibling pandas subpackage. Future helpers registered here
should keep eager-versus-lazy semantics explicit and favour
expression-based APIs so schema inference and predicate pushdown are
preserved wherever possible.

See Also
--------
polars.DataFrame : Eager columnar dataframe used by helpers in this namespace.
polars.LazyFrame : Lazy query graph that defers execution until ``collect``.
mayutils.objects.dataframes : Parent namespace hosting sibling dataframe helpers.
mayutils.objects.dataframes.pandas : Pandas counterpart exposing analogous utilities.

Examples
--------
>>> import polars as pl
>>> from mayutils.objects.dataframes import polars as mu_polars
>>> frame = pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
>>> frame.lazy().select(pl.col("a").sum()).collect().item()
6
>>> mu_polars.__name__
'mayutils.objects.dataframes.polars'
"""
