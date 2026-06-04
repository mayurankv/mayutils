"""
Group runtime-facing helpers for interacting with the host environment.

This package collects the runtime-facing utilities of the ``mayutils``
library: components that manage execution context rather than pure data
transformations. It aggregates helpers for benchmarking execution time,
constructing database engines, resolving filesystem and git-aware paths,
structured logging, in-process memoisation, OAuth and key-management
flows, secret and ``.env`` ingestion, and webdriver factories used by the
export and scraping pipelines. Submodules are designed to be imported
individually so that optional dependencies declared as package extras
remain opt-in at install time.

See Also
--------
mayutils.environment.benchmarking : Lightweight timing and profiling helpers.
mayutils.environment.databases : SQLAlchemy and Snowflake engine factories.
mayutils.environment.filesystem : Git- and path-aware filesystem utilities.
mayutils.environment.logging : Rich-backed structured logger defaults.
mayutils.environment.memoisation : Caching decorators for expensive calls.
mayutils.environment.oauth : OAuth helpers and Fernet key generation.
mayutils.environment.secrets : ``.env`` parsing and secret loading helpers.
mayutils.environment.webdrivers : Selenium and Playwright factories.

Examples
--------
>>> from mayutils.environment.logging import Logger
>>> from mayutils.environment.memoisation import cache
>>> logger = Logger("pipeline")
>>> @cache
... def load_reference_data() -> dict[str, int]:
...     logger.info("Loading reference data")
...     return {"rows": 42}
>>> load_reference_data()["rows"]
42
"""
