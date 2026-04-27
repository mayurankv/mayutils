"""
Provide Dask-specific dataframe helpers for the ``mayutils`` library.

This package is the Dask-specific namespace within
:mod:`mayutils.objects.dataframes`, grouping utilities that operate on
:class:`dask.dataframe.DataFrame` objects. The subpackage currently acts
as a re-export surface so downstream callers can import parallel and
out-of-core dataframe helpers from a single location, mirroring the
layout used by the sibling pandas and polars subpackages. Future helpers
registered here should preserve lazy task-graph semantics and favour
partition-aware APIs so Dask's scheduler can parallelise work without
triggering unintended materialisation of the full frame into memory.

See Also
--------
dask.dataframe.DataFrame : Partitioned, lazy dataframe used by helpers in this namespace.
dask.dataframe.Series : Partitioned series counterpart exposed by the Dask backend.
mayutils.objects.dataframes : Parent namespace hosting sibling dataframe helpers.
mayutils.objects.dataframes.pandas : Pandas counterpart exposing analogous utilities.
mayutils.objects.dataframes.modin : Modin counterpart for pandas-compatible distributed workflows.

Examples
--------
>>> import dask.dataframe as dd
>>> import pandas as pd
>>> from mayutils.objects.dataframes import dask as mu_dask
>>> frame = dd.from_pandas(pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]}), npartitions=2)
>>> int(frame["a"].sum().compute())
6
>>> mu_dask.__name__
'mayutils.objects.dataframes.dask'
"""
