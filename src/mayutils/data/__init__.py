"""
Group data ingestion, caching and query-template utilities.

Bundle the `mayutils` helpers that deal with sourcing data for analysis
workflows. Expose unified readers spanning live database or API backends
and local filesystem stores, ship a collection of pre-written SQL query
templates, and establish the on-disk cache directory used by the caching
layer to memoise intermediate results between notebook sessions.

See Also
--------
mayutils.data.read : Unified readers for tabular sources and cached files.
mayutils.data.live : Live database and API-backed connectors.
mayutils.data.queries : Pre-written SQL query templates consumed by readers.

Notes
-----
The module-level ``CACHE_FOLDER`` constant resolves to the ``cache``
directory colocated with this package and is the default destination used
by the reader utilities when persisting cached payloads.

Examples
--------
>>> from mayutils.data import CACHE_FOLDER
>>> CACHE_FOLDER.name
'cache'
>>> CACHE_FOLDER.parent.name
'data'
"""

from pathlib import Path

CACHE_FOLDER = Path(__file__).parent / "cache"
