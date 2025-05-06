from rich.console import Console
from typing import get_args

from mayutils.core.types import Operation


COLOURS = dict(
    lightgreen="#73DBB6",
    darkgreen="#3BDB5F",
    cyan="#30D5DB",
    blue="#9299FD",
    yellow="#FFE989",
    orange="#FFBD8E",
    red="#F58B78",
    purple="#C592FD",
    lightpink="#FFCCFF",
    pink="#FF85FF",
)

OPACITIES = {
    "primary": 1.0,
    "secondary": 0.5,
    "tertiary": 0.4,
    "quaternary": 0.3,
}

FONT_SIZES = {}


DISPLAY_TYPE_ENV_VAR = "NB_DISPLAY_TYPE"
OPERATIONS: tuple = get_args(Operation.__value__)

CONSOLE = Console()  # TODO: Rich width for slides should be 72
