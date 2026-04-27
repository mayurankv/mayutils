"""
Expose the top-level ``mayutils`` package surface and runtime entry point.

This module defines the library's version string and the
:func:`setup` convenience function that wires up the optional runtime
features (logging formatting, Jupyter notebook display helpers and
Plotly templates). The package is deliberately layered so that the
import-time cost of ``import mayutils`` remains small: heavy optional
dependencies (Plotly, Snowflake, Selenium, Pendulum, Google API client)
live behind extras documented in ``docs/guides/dependency-groups.md``.
Consumers that have only installed the core distribution can still
import the package, and :func:`setup` degrades gracefully by emitting a
warning when an optional extra is missing instead of raising.

See Also
--------
mayutils.core.extras : Helpers for formatting missing-extra hints.
mayutils.environment.logging : Project-wide logging configuration.
mayutils.visualisation.notebook : Jupyter notebook display helpers.

Examples
--------
>>> import mayutils
>>> mayutils.setup()
"""

from importlib import metadata

__version__ = metadata.version(distribution_name="mayutils")


def setup() -> None:
    """
    Initialise the standard mayutils runtime environment.

    Configure the library's logging handler with the project-wide
    formatter, register the custom Plotly templates used by the
    visualisation helpers, and apply notebook display tweaks (pandas
    DataFrame rendering overrides and Jupyter display settings). The
    routine is intended to be called once near the start of a script,
    notebook or application entry point so that downstream
    :mod:`mayutils` modules emit consistently formatted output. Optional
    plotting and notebook steps are guarded by a single ``ImportError``
    handler so that core-only installations without the ``plotting`` or
    ``notebook`` extras degrade to a logged warning instead of raising.

    See Also
    --------
    mayutils.core.extras.format_missing_extra_hint : Render install hints for missing extras.
    mayutils.environment.logging.Logger : Logger factory that is configured here.
    mayutils.objects.dataframes.setup_pandas : Apply pandas display configuration.
    mayutils.visualisation.notebook.Notebook.setup : Install notebook display hooks.
    mayutils.visualisation.graphs.plotly.templates : Register custom Plotly templates on import.

    Examples
    --------
    >>> import mayutils
    >>> mayutils.setup()
    """
    from mayutils.environment.logging import Logger  # noqa: PLC0415

    Logger.configure()

    try:
        import mayutils.visualisation.graphs.plotly.templates  # noqa: F401, PLC0415
        from mayutils.objects.dataframes import setup_pandas  # noqa: PLC0415
        from mayutils.visualisation.notebook import Notebook  # noqa: PLC0415

        try:
            Notebook.setup()
        except RuntimeError:
            Logger.spawn().debug("Skipping notebook setup: no active IPython shell.")

        setup_pandas()

    except ImportError as err:
        from mayutils.core.extras import format_missing_extra_hint  # noqa: PLC0415

        missing = getattr(err, "name", None) or "dependency"
        Logger.spawn().warning(
            f"Skipping optional setup step: {err}. {format_missing_extra_hint(missing)}",
        )
