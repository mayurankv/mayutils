from mayutils.environment.logging import Logging
from mayutils.objects.dataframes import (
    setup_dataframes,
)
from mayutils.visualisation.notebook import setup_notebooks


def setup() -> None:
    Logging.configure()
    setup_notebooks()
    setup_dataframes()


setup()

__version__ = "1.0.15"
