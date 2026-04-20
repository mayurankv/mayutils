"""Environment, configuration, and infrastructure helpers.

This package groups the runtime-facing utilities of the ``mayutils`` library:
components that interact with the host environment rather than with pure data
transformations. It collects helpers for benchmarking execution, constructing
database engines, resolving filesystem and git-aware paths, structured
logging, in-process memoisation, OAuth and key-management flows, secret and
``.env`` ingestion, and webdriver factories used by the export and scraping
pipelines. Submodules are designed to be imported individually so optional
dependencies (declared as package extras) remain opt-in.

Submodules
----------
benchmarking
    Lightweight timing and profiling helpers for measuring code execution.
databases
    SQLAlchemy and Snowflake engine factories (``snowflake`` extra).
filesystem
    Git- and path-aware filesystem helpers (``filesystem`` extra for git
    integration).
logging
    Rich-backed :class:`Logger` with structured defaults for consistent
    console and file output.
memoisation
    Caching decorators for memoising expensive function calls across runs.
oauth
    OAuth helpers, including Fernet key generation, used for authenticating
    against external services (``google``/``keyring`` extras).
secrets
    ``.env`` parsing and secret loading utilities.
webdrivers
    Selenium and Playwright webdriver factories (``web`` extra) used for
    headless browser automation.
"""
