"""
Provide helpers for working with Polars dataframes.

This module centralises Polars-specific transformation, inspection, and
conversion utilities shared across the wider :mod:`mayutils` codebase. It is
intended to cover both eager :class:`polars.DataFrame` and lazy
:class:`polars.LazyFrame` workflows, with functions favouring expression-based
APIs such as :func:`polars.col` so that schema inference and predicate pushdown
are preserved whenever possible. Future helpers added to this file should
continue to honour that eager-versus-lazy distinction and keep signatures
explicit about which variant they accept or return.

See Also
--------
polars.DataFrame : Eager columnar dataframe used by the helpers in this module.
polars.LazyFrame : Lazy query graph that defers execution until collection.
polars.col : Expression builder referenced for schema-aware transformations.
mayutils.objects.dataframes : Parent namespace hosting sibling dataframe helpers.

Examples
--------
>>> import polars as pl
>>> frame = pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
>>> frame.lazy().select(pl.col("a").sum()).collect().item()
6
"""
