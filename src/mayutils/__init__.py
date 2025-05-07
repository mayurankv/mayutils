from mayutils.environment.logging import setup_logging
from mayutils.objects.dataframes import (
    setup_dataframes,
)
from mayutils.visualisation.notebook import setup_notebooks


def setup():
    setup_logging()
    setup_notebooks()
    setup_dataframes()


setup()

__version__ = "1.0.6"
