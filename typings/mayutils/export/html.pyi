from _typeshed import Incomplete
from mayutils.environment.logging import Logger as Logger
from pathlib import Path

H2I: Incomplete
logger: Incomplete

def markdown_to_html(text: str) -> str: ...
def html_to_image(
    html: str,
    path: Path | str,
    css: str | None = None,
    size: tuple[int, int] | None = None,
    sleep_time: int = 1,
) -> Path: ...
def html_pill(
    text: str,
    background_colour: str,
    text_colour: str = "black",
    bold: bool = True,
    padding: tuple[float, float] = (0.2, 0.4),
    relative_font_size: float = 0.9,
    rounding: float = 5.625,
) -> str: ...
