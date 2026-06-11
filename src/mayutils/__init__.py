"""Expose the top-level ``mayutils`` package surface and runtime entry point."""

from importlib import metadata

__version__ = metadata.version(distribution_name="mayutils")


def setup(
    *,
    logging: bool = True,
    plotly: bool = True,
    notebook: bool = True,
    pandas: bool = True,
) -> None:
    """
    Initialise the standard mayutils runtime environment.

    Configures logging, registers Plotly templates, sets up IPython
    display hooks and pandas options based on the supplied flags.

    Parameters
    ----------
    logging
        When ``True``, install Rich console and rotating file handlers
        on the root logger via :meth:`Logger.configure`.
    plotly
        When ``True``, register the custom Plotly templates via
        :func:`register_templates`.
    notebook
        When ``True``, configure IPython display hooks via
        :meth:`mayutils.visualisation.notebook.Notebook.setup`.
    pandas
        When ``True``, apply default pandas display options via
        :func:`mayutils.objects.dataframes.setup_pandas`.

    See Also
    --------
    mayutils.environment.logging.Logger.configure : Logging setup.
    mayutils.visualisation.graphs.plotly.templates.register_templates :
        Plotly template registration.

    Examples
    --------
    >>> from mayutils import setup
    >>> setup(logging=False, plotly=False, notebook=False, pandas=False)
    """
    from mayutils.core.extras import format_missing_extra_hint
    from mayutils.environment.logging import Logger

    if logging:
        Logger.configure()

    if plotly:
        try:
            from mayutils.visualisation.graphs.plotly.templates import register_templates

            register_templates()
        except ImportError as err:
            missing = getattr(err, "name", None) or "dependency"
            Logger.spawn().warning(
                f"Skipping Plotly template registration: {err}. {format_missing_extra_hint(missing)}",
            )

    if notebook:
        try:
            from mayutils.visualisation.notebook import Notebook

            Notebook.setup()
        except ImportError as err:
            missing = getattr(err, "name", None) or "dependency"
            Logger.spawn().warning(
                f"Skipping notebook setup: {err}. {format_missing_extra_hint(missing)}",
            )
        except RuntimeError:
            Logger.spawn().debug("Skipping notebook setup: no active IPython shell.")

    if pandas:
        try:
            from mayutils.objects.dataframes import setup_pandas

            setup_pandas()
        except ImportError as err:
            missing = getattr(err, "name", None) or "dependency"
            Logger.spawn().warning(
                f"Skipping pandas setup: {err}. {format_missing_extra_hint(missing)}",
            )
