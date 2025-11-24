from _typeshed import Incomplete
from mayutils.export import OUTPUT_FOLDER as OUTPUT_FOLDER
from mayutils.objects.datetime import Date as Date
from mayutils.visualisation.notebook import (
    not_nbconvert as not_nbconvert,
    write_markdown as write_markdown,
)
from pathlib import Path

WARNING: str
SLIDES_FOLDER: Incomplete

def is_slides() -> bool: ...
def subtitle_text(
    authors: list[str] = ["Mayuran Visakan"],
    confidential: bool = False,
    updated: Date = ...,
) -> None: ...
def export_slides(
    title: str | None = None,
    file_path: Path | str = "report.ipynb",
    theme: tuple[str, str] | None = None,
    serve: bool = False,
    light: bool = False,
    rerun: bool = True,
) -> Path | None: ...
