"""Data ingestion, caching and query-template utilities.

This package groups the `mayutils` helpers that deal with sourcing data for
analysis workflows. It exposes unified readers that span live database or API
backends and local filesystem stores, ships a bundle of pre-written SQL
query templates, and establishes the on-disk cache directory used by the
caching layer to memoise intermediate results between notebook sessions.

Notes
-----
The module-level ``CACHE_FOLDER`` constant resolves to the ``cache``
directory colocated with this package and is the default destination used by
the reader utilities when persisting cached payloads.
"""

from pathlib import Path

CACHE_FOLDER = Path(__file__).parent / "cache"
