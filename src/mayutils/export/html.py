import time
from typing import Optional
from pathlib import Path
from html2image import Html2Image
from markdown import markdown
from mayutils.environment.logging import Logger

H2I = Html2Image()
logger = Logger.spawn()


def markdown_to_html(
    text: str,
) -> str:
    return markdown(
        text=text,
    ).replace(
        "\n",
        "<br>",
    )


def html_to_image(
    html: str,
    path: Path | str,
    css: Optional[str] = None,
    size: Optional[tuple[int, int]] = None,
    sleep_time: int = 1,
) -> Path:
    path = Path(path)

    kwargs = {}

    if size is not None:
        kwargs["size"] = size

    H2I.screenshot(
        html_str=html,
        css_str=css or "",
        save_as=path.name,
        **kwargs,
    )

    time.sleep(0.5)
    while not path.exists():
        logger.debug(f"Waiting {sleep_time} second for {path} to be created...")
        time.sleep(sleep_time)

    Path(path.name).replace(target=path)

    return path


def html_pill(
    text: str,
    background_colour: str,
    text_colour: str = "black",
    bold: bool = True,
    padding: tuple[float, float] = (0.2, 0.4),
    relative_font_size: float = 0.9,
    rounding: float = 5.625,
) -> str:
    return f'<span style="display: inline-block; background-color: {background_colour}; color: {text_colour}; padding: {padding[0]}em {padding[1]}em; border-radius: {rounding}em; font-size: {relative_font_size}em; font-weight: {"bold" if bold else "normal"};">{text}</span>'
