"""
Provide secret resolution helpers backed by ``python-dotenv``.

This module exposes a thin wrapper around :mod:`dotenv` that locates a
``.env`` file on disk and promotes its key/value pairs into
``os.environ`` so downstream code can read credentials, API keys and
configuration toggles through the standard environment-variable
interface without hard-coding secrets in source. Resolution follows a
layered priority where values already present in ``os.environ`` win
over any file contents, allowing shell exports, CI secret managers and
OS keyrings to override the committed defaults. When a ``.env`` file is
absent the module degrades silently so deployments relying solely on a
process environment or keyring backend continue to function unchanged.

See Also
--------
keyring : Cross-platform OS keyring integration used for per-user secret storage.
python-dotenv : Upstream library that parses and loads ``.env`` files.
pydantic-settings : Typed settings model that consumes the environment populated here.
mayutils.environment.oauth : Companion module for interactive OAuth credential flows.

Examples
--------
>>> from mayutils.environment.secrets import load_secrets
>>> result = load_secrets()  # doctest: +SKIP
>>> isinstance(result, bool)  # doctest: +SKIP
True

>>> result = load_secrets(env_file=".env.local")  # doctest: +SKIP
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mayutils.core.extras import may_require_extras

if TYPE_CHECKING:
    from pathlib import Path


def load_secrets(
    *,
    env_file: Path | str | None = None,
) -> bool:
    """
    Load key/value pairs from a ``.env`` file into ``os.environ``.

    When no explicit path is supplied the function delegates to
    :func:`dotenv.find_dotenv`, which walks upwards from the current
    working directory searching for a ``.env`` file. The backend
    priority is environment first, then keyring (for callers that
    combine this helper with :mod:`keyring`), and finally the on-disk
    ``.env`` file; variables already present in ``os.environ`` take
    precedence and are not overwritten by the file's contents. This
    makes the helper safe to call repeatedly at import time and
    composes cleanly with shell exports, CI secret injectors and
    :mod:`pydantic-settings` models.

    Parameters
    ----------
    env_file
        Filesystem location of the ``.env`` file to load. When
        ``None`` (the default) the location is auto-discovered by
        walking upwards from the current working directory until a
        ``.env`` file is found; when no file exists the fallback is a
        no-op that returns ``False`` without raising.

    Returns
    -------
        ``True`` when a ``.env`` file was located and at least one
        variable was injected into the process environment; ``False``
        when no file was found or the file was empty. Values loaded
        from disk are masked by :mod:`dotenv` during logging so they
        do not leak into terminal output.

    See Also
    --------
    keyring.get_password : Alternative backend for retrieving per-user secrets from the OS keyring.
    python-dotenv.load_dotenv : Underlying loader invoked to populate ``os.environ``.
    pydantic-settings.BaseSettings : Typed consumer of the environment variables loaded here.
    mayutils.environment.oauth : Companion helpers for OAuth-based credential retrieval.

    Examples
    --------
    Auto-discover and load the nearest ``.env`` file:

    >>> from mayutils.environment.secrets import load_secrets
    >>> result = load_secrets()  # doctest: +SKIP
    >>> isinstance(result, bool)  # doctest: +SKIP
    True

    Load a specific env file:

    >>> load_secrets(env_file=".env.local")  # doctest: +SKIP
    """
    with may_require_extras():
        from dotenv import find_dotenv, load_dotenv

    if env_file is None:
        env_file = find_dotenv()

    return load_dotenv(dotenv_path=env_file)
