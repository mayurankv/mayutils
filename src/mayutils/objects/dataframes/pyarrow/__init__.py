"""
Provide PyArrow-specific dataframe helpers for the ``mayutils`` library.

This package is the PyArrow-specific namespace within
:mod:`mayutils.objects.dataframes`, grouping utilities that operate on
:class:`pyarrow.Table`, :class:`pyarrow.RecordBatch`, and related Arrow
data structures. The subpackage currently acts as a re-export surface
so downstream callers can import interoperability helpers between
Arrow and the other dataframe backends from a single location, mirroring
the layout used by the sibling pandas and polars subpackages. Future
helpers registered here should preserve Arrow's zero-copy semantics and
explicit schema typing so the format remains a lossless bridge between
engines rather than a lowest-common-denominator row representation.

See Also
--------
pyarrow.Table : Columnar in-memory table used by helpers in this namespace.
pyarrow.RecordBatch : Columnar batch primitive composed into Arrow tables.
pyarrow.Schema : Typed schema that governs conversions to and from Arrow.
mayutils.objects.dataframes : Parent namespace hosting sibling dataframe helpers.
mayutils.objects.dataframes.pandas : Pandas counterpart that interoperates via ``to_pandas``.
mayutils.objects.dataframes.polars : Polars counterpart that consumes Arrow zero-copy.

Examples
--------
>>> import pyarrow as pa
>>> from mayutils.objects.dataframes import pyarrow as mu_pyarrow
>>> table = pa.table({"a": [1, 2, 3], "b": [4, 5, 6]})
>>> table.num_rows
3
>>> mu_pyarrow.__name__
'mayutils.objects.dataframes.pyarrow'
"""
