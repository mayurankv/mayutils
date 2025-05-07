import tomllib
from pathlib import Path

from mayutils.environment.logging import setup_logging
from mayutils.visualisation.notebook import setup_notebooks
from mayutils.objects.dataframes import (
    setup_dataframes,
)


class Setup(object):
    initialised: bool = False

    @staticmethod
    def initialise() -> None:
        if Setup.initialised:
            return

        setup_logging()
        setup_notebooks()
        setup_dataframes()

        Setup.initialised = True


Setup.initialise()

__version__ = 1.0.3
