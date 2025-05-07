import tomllib
from pathlib import Path

from mayutils.environment.logging import setup_logging
from mayutils.visualisation.notebook import setup_notebooks
from mayutils.objects.dataframes import (
    setup_dataframes,
)


def setup():
    setup_logging()
    setup_notebooks()
    setup_dataframes()


setup()

__version__ = "1.0.4"
