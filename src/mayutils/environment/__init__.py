"""Environment, configuration and infra helpers.

Submodules
----------
benchmarking
    Lightweight timing helpers.
databases
    SQLAlchemy / Snowflake engine factories (``snowflake`` extra).
filesystem
    Git- and path-aware helpers (``filesystem`` extra for git integration).
logging
    Rich-backed :class:`Logger` with structured defaults.
memoisation
    Caching decorators.
oauth
    OAuth helpers, including Fernet key generation (``google``/``keyring`` extras).
secrets
    ``.env`` and secret loading.
webdrivers
    Selenium/Playwright webdriver factories (``web`` extra).
"""
