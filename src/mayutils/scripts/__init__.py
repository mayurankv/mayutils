"""Entry-point scripts exposed as console commands.

This package groups together the command-line entry points shipped with
``mayutils``. Each submodule defines a console script.

Submodules
----------
clear_cache
    ``clear_cache`` CLI (``cli`` extra: typer + rich progress).
refresh_stubs
    ``refresh_stubs`` CLI — regenerate pyright stubs for packages in
    ``typings/`` that still require third-party stubs (``cli`` extra).
"""
