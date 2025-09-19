# import warnings
from importlib import metadata

__version__ = metadata.version(distribution_name="mayutils")


def setup() -> None:
    from mayutils.environment.logging import Logger

    Logger.configure()

    try:
        from mayutils.objects.dataframes import setup_dataframes
        from mayutils.visualisation.notebook import setup_notebooks
        import mayutils.visualisation.graphs.plotly.templates  # noqa: F401

        setup_notebooks()
        setup_dataframes()

    except ImportError as err:
        Logger.spawn().warning(f"Error occurred during setup imports: {err}")

    # # TODO: Remove when dependency is upgraded
    # warnings.filterwarnings(
    #     action="ignore",
    #     message="You have an incompatible version of 'pyarrow' installed.*",
    #     category=UserWarning,
    #     module="snowflake.connector.options",
    # )


setup()
