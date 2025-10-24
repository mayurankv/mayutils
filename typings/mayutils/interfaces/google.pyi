import polars as pl
from _typeshed import Incomplete
from google.oauth2.credentials import Credentials as Credentials
from mayutils.objects.colours import Colour as Colour
from mayutils.objects.dataframes import column_to_excel as column_to_excel
from pandas import DataFrame
from pathlib import Path
from typing import Any, Self

DriveService = Any
SlidesService = Any
SlidesInternal = Any
SlideInternal = Any
File = Any
SheetsService = Any
SheetsInternal = Any
SheetInternal = Any

class Drive:
    service: Incomplete
    def __init__(self, drive_service: DriveService) -> None: ...
    def files(self) -> Any: ...
    @classmethod
    def from_creds(cls, creds: Credentials) -> Self: ...
    def query_files(
        self,
        query: str,
        spaces: str = "drive",
        supportsAllDrives: bool = True,
        includeItemsFromAllDrives: bool = True,
        **kwargs,
    ) -> Any: ...
    def find_file(
        self, file_name: str, folder_id: str | None = None
    ) -> File | None: ...
    def find_file_id(self, file_name: str, **kwargs) -> str: ...
    def delete_file_by_id(self, file_id: str) -> None: ...
    def delete_file_by_name(
        self, file_name: str, supportsAllDrives: bool = True, **kwargs
    ) -> None: ...
    def upload(self, file_path: Path | str, folder_id: str | None = None) -> str: ...
    def get(self, file_path: Path | str, force_upload: bool = False) -> str: ...

class Slides:
    id: str
    service: SlidesService
    internal: SlidesInternal
    def __init__(
        self, presentation: SlidesInternal, slides_service: SlidesService
    ) -> None: ...
    @property
    def height(self) -> float: ...
    @property
    def width(self) -> float: ...
    @property
    def link(self) -> str: ...
    def slide(self, slide_number: int) -> SlideInternal: ...
    @property
    def slides(self) -> list[SlideInternal]: ...
    def slide_id(self, slide_number: int) -> SlideInternal: ...
    @property
    def title(self) -> Any: ...
    def open(self) -> None: ...
    def get_thumbnail_url(self, slide_number: int) -> str: ...
    def display(self, slide_number: int | None = None, **kwargs) -> None: ...
    def update(self, requests: list[dict]) -> Self: ...
    @staticmethod
    def service_from_creds(creds: Credentials) -> SlidesService: ...
    @classmethod
    def fresh_from_creds(
        cls, presentation_name: str, creds: Credentials, template: str | None = None
    ) -> Self: ...
    @classmethod
    def retrieve_from_id(
        cls, presentation_id: str, slides_service: SlidesService
    ) -> Self: ...
    @classmethod
    def retrieve_from_name(
        cls, presentation_name: str, drive: Drive, slides_service: SlidesService
    ) -> Self: ...
    @classmethod
    def create_new(
        cls, presentation_name: str, slides_service: SlidesService
    ) -> Self: ...
    @classmethod
    def create_from_template(
        cls,
        presentation_name: str,
        template_name: str,
        drive: Drive,
        slides_service: SlidesService,
    ) -> Self: ...
    @classmethod
    def get(
        cls,
        presentation_name: str,
        drive: Drive,
        slides_service: SlidesService,
        template: str | None = None,
    ) -> Self: ...
    def reset(self, drive: Drive) -> Self: ...
    def copy_slide(
        self, slide_number: int | None = None, to_position: int | None = None
    ) -> Self: ...
    def delete_slide(self, slide_number: int) -> Self: ...
    def move_slide(self, slide_number: int, to_position: int) -> Self: ...
    def insert_text(
        self,
        text: str,
        slide_number: int | None = None,
        height: float | None = None,
        width: float | None = None,
        x_shift: float | None = None,
        y_shift: float | None = None,
        element_id: str = ...,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        strikethrough: bool = False,
        font_size: int | None = None,
        font_family: str | None = None,
        colour: Colour | str | None = None,
        background_colour: Colour | str | None = None,
        link: str | None = None,
        **kwargs,
    ) -> Self: ...
    def insert_image(
        self,
        image_path: Path | str,
        slide_number: int | None = None,
        height: float | None = None,
        width: float | None = None,
        x_shift: float | None = None,
        y_shift: float | None = None,
        element_id: str = ...,
        drive: Drive | None = None,
        force_upload: bool = False,
    ) -> Self: ...

class Sheet:
    service: SheetsService
    internal: SheetInternal
    id: str
    parent: Incomplete
    def __init__(
        self, sheet: SheetInternal, parent: Sheets, sheets_service: SheetsService
    ) -> None: ...
    @property
    def title(self) -> str: ...
    @property
    def index(self) -> int: ...
    @property
    def rows(self) -> int: ...
    @property
    def columns(self) -> int: ...
    def to_arrays(self, range: str | None = None) -> list: ...
    def to_pandas(self, range: str | None = None) -> DataFrame: ...
    def to_polars(self, range: str | None = None) -> pl.DataFrame: ...
    @property
    def df(self) -> DataFrame: ...
    def update_values(
        self, range: str, values: list[list[Any]], as_user: bool = True
    ) -> Self: ...
    def insert(
        self, range: str | None, values: list[list[Any]], as_user: bool = True
    ) -> Self: ...
    def insert_df(
        self,
        range: str | None,
        df: DataFrame,
        as_user: bool = True,
        index_name: str = "Index",
    ) -> Self: ...

class Sheets:
    service: SheetsService
    internal: SheetsInternal
    id: str
    def __init__(
        self, sheets: SheetsInternal, sheets_service: SheetsService
    ) -> None: ...
    @property
    def link(self) -> str: ...
    def sheet(self, sheet_number: int) -> Sheet: ...
    def sheet_from_name(self, sheet_name: str) -> Sheet: ...
    @property
    def sheets(self) -> list[Sheet]: ...
    @property
    def title(self) -> str: ...
    def open(self) -> None: ...
    def refresh(self) -> Self: ...
    def update(self, requests: list[dict]) -> Self: ...
    def update_values(
        self, range: str, values: list[list[Any]], as_user: bool = True
    ) -> Self: ...
    @staticmethod
    def service_from_creds(creds: Credentials) -> SheetsService: ...
    @classmethod
    def fresh_from_creds(
        cls, sheets_name: str, creds: Credentials, template: str | None = None
    ) -> Self: ...
    @classmethod
    def retrieve_from_id(
        cls, sheets_id: str, sheets_service: SheetsService
    ) -> Self: ...
    @classmethod
    def retrieve_from_name(
        cls, sheets_name: str, drive: Drive, sheets_service: SheetsService
    ) -> Self: ...
    @classmethod
    def create_new(cls, sheets_name: str, sheets_service: SheetsService) -> Self: ...
    @classmethod
    def create_from_template(
        cls,
        sheets_name: str,
        template_name: str,
        drive: Drive,
        sheets_service: SheetsService,
    ) -> Self: ...
    @classmethod
    def get(
        cls,
        sheets_name: str,
        drive: Drive,
        sheets_service: SheetsService,
        template: str | None = None,
    ) -> Self: ...
    def reset(self, drive: Drive) -> Self: ...
    def rename_sheet(self, sheet: Sheet, new_title: str) -> Self: ...
    def move_sheet(self, sheet: Sheet, to_position: int | None = None) -> Self: ...
    def copy_sheet(
        self,
        sheet: Sheet | None = None,
        new_title: str | None = None,
        to_position: int | None = None,
    ) -> Self: ...
    def delete_sheet(self, sheet: Sheet) -> Self: ...
    def insert_sheet(
        self, new_title: str | None = None, to_position: int | None = None
    ) -> Self: ...
    def add_sheet_from_dataframe(
        self,
        df: DataFrame,
        new_title: str | None = None,
        to_position: int | None = None,
        as_user: bool = False,
        **kwargs,
    ) -> Self: ...
