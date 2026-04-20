"""Secret resolution helpers backed by ``python-dotenv``.

This module provides a thin wrapper around :mod:`dotenv` that locates a
``.env`` file on disk and promotes its key/value pairs into
``os.environ`` so that downstream code can read credentials, API keys
and configuration toggles through the standard environment-variable
interface without hard-coding secrets in source.
"""

from pathlib import Path

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from dotenv import find_dotenv, load_dotenv


def load_secrets(
    *,
    env_file: Path | str | None = None,
) -> bool:
    """Load key/value pairs from a ``.env`` file into ``os.environ``.

    When no explicit path is supplied the function delegates to
    :func:`dotenv.find_dotenv`, which walks upwards from the current
    working directory searching for a ``.env`` file. Variables that are
    already present in the process environment take precedence and are
    not overwritten by the file's contents.

    Parameters
    ----------
    env_file : pathlib.Path or str or None, optional
        Filesystem location of the ``.env`` file to load. When
        ``None`` (the default) the location is auto-discovered by
        walking upwards from the current working directory until a
        ``.env`` file is found.

    Returns
    -------
    bool
        ``True`` when a ``.env`` file was located and at least one
        variable was injected into the process environment;
        ``False`` when no file was found or the file was empty.

    Notes
    -----
    Existing environment variables are preserved: entries in the
    ``.env`` file never override values already set in
    ``os.environ``. This makes the function safe to call multiple
    times and composes cleanly with shell-level configuration.

    Examples
    --------
    >>> load_secrets()  # doctest: +SKIP
    True
    >>> load_secrets(env_file=".env.local")  # doctest: +SKIP
    True
    """
    if env_file is None:
        env_file = find_dotenv()

    return load_dotenv(dotenv_path=env_file)
