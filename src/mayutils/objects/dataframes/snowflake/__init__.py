"""
Provide Snowflake-specific dataframe helpers for the ``mayutils`` library.

This package is the Snowflake-specific namespace within
:mod:`mayutils.objects.dataframes`, grouping utilities that operate on
Snowpark :class:`snowflake.snowpark.DataFrame` objects and the
pandas-to-Snowflake bridges exposed through
:mod:`snowflake.connector.pandas_tools`. The subpackage currently acts
as a re-export surface so downstream callers can import warehouse-native
dataframe helpers from a single location, mirroring the layout used by
the sibling pandas and polars subpackages. Future helpers registered
here should push computation into the Snowflake engine where possible,
relying on Snowpark's lazy query compilation so analytic workloads
execute against the warehouse rather than pulling full result sets to
the client.

See Also
--------
snowflake.snowpark.DataFrame : Lazy warehouse dataframe used by helpers in this namespace.
snowflake.connector.pandas_tools : Bulk ``write_pandas`` bridge between pandas and Snowflake.
snowflake.connector.connect : Primary entry point for building Snowflake sessions.
mayutils.objects.dataframes : Parent namespace hosting sibling dataframe helpers.
mayutils.objects.dataframes.pandas : Pandas counterpart commonly paired with Snowflake round-trips.

Examples
--------
>>> from mayutils.objects.dataframes import snowflake as mu_snowflake
>>> mu_snowflake.__name__
'mayutils.objects.dataframes.snowflake'
"""
