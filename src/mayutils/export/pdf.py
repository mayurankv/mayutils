from typing import Optional
import datetime
from subprocess import call
import os

from mayutils.export import OUTPUT_FOLDER

PDF_FOLDER = OUTPUT_FOLDER / "PDF"


def export_pdf(
    title: Optional[str] = None,
    template: Optional[str] = None,
    file_name: str = "report.ipynb",
    hide_code: bool = False,
) -> None:
    today = datetime.date.today().strftime(
        format="%Y_%m_%d",
    )

    filepath = (
        os.path.dirname(p=os.path.realpath(filename="__file__")) + "/" + file_name
    )

    file_title = (
        f"{title}_{today}" if title is not None else file_name.split(sep=".")[0]
    )
    output_filepath = PDF_FOLDER / file_title

    call(
        args=f"jupyter nbconvert {filepath} --output {output_filepath} --to pdf {'--no-input ' if hide_code else ''}{('--TemplateExporter.extra_template_basedirs=' + template) if template is not None else ''}",
        shell=True,
    )
