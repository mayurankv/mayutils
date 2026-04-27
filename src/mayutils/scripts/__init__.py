"""
Expose console entry-point scripts shipped with ``mayutils``.

Group the command-line utilities that are registered under
``[project.scripts]`` in ``pyproject.toml`` and installed onto the
user's ``PATH`` alongside the library. Each submodule implements a
``typer`` application whose ``app`` callable is exported as the script
target, so installing the ``cli`` extra surfaces the commands as
first-class console tools for maintenance and code-generation tasks.
Importing the package remains cheap because the submodules only pull in
heavy dependencies such as ``typer`` and ``rich`` when the scripts are
actually invoked.

See Also
--------
mayutils.scripts.clear_cache : ``clear_cache`` CLI that wipes the
    memoisation cache folder with a ``typer`` entry point and ``rich``
    progress reporting.
mayutils.scripts.refresh_stubs : ``refresh_stubs`` CLI that regenerates
    pyright stubs in ``typings/`` for third-party packages that still
    require type information.
mayutils.environment.oauth : Hosts ``generate_fernet_key``, the callable
    exposed as the ``generate_encryption_key`` console entry point.
typer : Third-party framework used to build the script interfaces.

Examples
--------
>>> from mayutils.scripts import clear_cache, refresh_stubs
>>> callable(clear_cache.app)
True
>>> callable(refresh_stubs.app)
True
"""
