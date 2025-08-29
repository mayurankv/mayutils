from pathlib import Path
from typing import Optional
from datetime import date
from subprocess import call
import os
from shlex import quote as escape
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from mayutils.visualisation.notebook import (
    not_nbconvert,
    write_markdown,
)
from mayutils.export import OUTPUT_FOLDER

WARNING = "Not an ipython notebook"

try:
    from IPython import get_ipython  # type: ignore

    ipython = get_ipython()

    if ipython is None:
        raise ValueError(WARNING)

except ImportError:
    raise ValueError(WARNING)

SLIDES_FOLDER = OUTPUT_FOLDER / "Slides"


def is_slides() -> bool:
    return os.getenv(key="_NBCONVERT_OUTPUT_FORMAT", default=None) == "slides"


def subtitle_text(
    authors: list[str] = ["Mayuran Visakan"],
    confidential: bool = False,
    updated: date = date.today(),
) -> None:
    if not is_slides():
        return

    write_markdown(f"**Last Updated: {updated}**")
    write_markdown(f"*By {', '.join(authors)}*")

    if confidential:
        write_markdown(
            "**<font style='color: red; font-size: 16px'>CONFIDENTIAL</font>**",
            "**<font style='font-size: 16px'>FOR SPECIFIC RECIPIENTS ONLY - Please get in touch before using or sharing any data from this pack</font>**",
        )


def export_slides(
    title: Optional[str] = None,
    file_name: str = "report.ipynb",
    theme: Optional[tuple[str, str]] = None,
    serve: bool = False,
    light: bool = False,
) -> Path | None:
    if not not_nbconvert():
        return None

    today = date.today().strftime(
        format="%Y_%m_%d",
    )

    filepath = (
        os.path.dirname(p=os.path.realpath(filename="__file__")) + "/" + file_name
    )

    file_title = (
        f"{title}_{today}"
        if title is not None
        else f"{file_name.split(sep='.')[0]}_{today}"
    )
    output_filepath = SLIDES_FOLDER / file_title

    with Progress(
        SpinnerColumn(),
        TextColumn(text_format="[progress.description]{task.description}"),
        TimeElapsedColumn(),
        transient=True,
    ) as progress:
        progress.add_task(
            description="[white]Exporting...[/]",
            total=None,
        )
        call(
            args=f"_NBCONVERT_OUTPUT_FORMAT=slides jupyter nbconvert {escape(filepath)} --output {escape(str(output_filepath))} --execute {'' if theme is None else ('--template=' + theme[0])} --to slides --no-input --no-prompt{'' if not serve else ' --post serve'} --SlidesExporter.reveal_scroll=True --SlidesExporter.reveal_number=c/t --SlidesExporter.reveal_theme={'simple' if light else 'night'} {'' if theme is None else ('--TemplateExporter.extra_template_basedirs=' + theme[1])}",
            shell=True,
        )

    return SLIDES_FOLDER / f"{file_title}.slides.html"
