from _typeshed import Incomplete
from mayutils.export import OUTPUT_FOLDER as OUTPUT_FOLDER

PDF_FOLDER: Incomplete

def export_pdf(
    title: str | None = None,
    template: str | None = None,
    file_name: str = "report.ipynb",
    hide_code: bool = False,
) -> None: ...
