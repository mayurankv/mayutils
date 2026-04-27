"""
Provide Modin-specific dataframe helpers for the ``mayutils`` library.

This package is the Modin-specific namespace within
:mod:`mayutils.objects.dataframes`, grouping utilities that operate on
:class:`modin.pandas.DataFrame` objects. The subpackage currently acts
as a re-export surface so downstream callers can import distributed,
pandas-compatible dataframe helpers from a single location, mirroring
the layout used by the sibling pandas and polars subpackages. Future
helpers registered here should preserve Modin's drop-in pandas API
contract and avoid operations that defeat its transparent
parallelisation, so existing pandas code can continue to execute on
Modin without rewrites.

See Also
--------
modin.pandas.DataFrame : Distributed, pandas-compatible dataframe used by helpers in this namespace.
modin.pandas.Series : Distributed series counterpart exposed by the Modin backend.
mayutils.objects.dataframes : Parent namespace hosting sibling dataframe helpers.
mayutils.objects.dataframes.pandas : Pandas counterpart exposing analogous utilities.
mayutils.objects.dataframes.dask : Dask counterpart for lazy, partitioned workflows.

Examples
--------
>>> import mayutils.objects.dataframes.modin as md
>>> md.__name__
'mayutils.objects.dataframes.modin'
"""
