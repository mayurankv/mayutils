import warnings
from mayutils.environment.logging import Logger
from mayutils.objects.dataframes import (
    setup_dataframes,
)
from mayutils.visualisation.notebook import setup_notebooks


def setup() -> None:
    Logger.configure()
    setup_notebooks()
    setup_dataframes()

    # TODO: Remove when dependency is upgraded
    warnings.filterwarnings(
        action="ignore",
        message="You have an incompatible version of 'pyarrow' installed.*",
        category=UserWarning,
        module="snowflake.connector.options",
    )


setup()

__version__ = "1.0.70"
