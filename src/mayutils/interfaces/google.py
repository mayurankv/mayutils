from __future__ import annotations
from pathlib import Path
from typing import Optional, Self, Any
import uuid
from base64 import b64encode
import mimetypes

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import webbrowser

from pandas import DataFrame
from mayutils.objects.dataframes import column_to_excel
import polars as pl

from mayutils.objects.colours import Colour

DriveService = Any
SlidesService = Any
SlidesInternal = Any
SlideInternal = Any
File = Any

SheetsService = Any
SheetsInternal = Any
SheetInternal = Any


class Drive(object):
    def __init__(
        self,
        drive_service: DriveService,
    ) -> None:
        self.service = drive_service

    def files(
        self,
    ) -> Any:
        return self.service.files()

    @classmethod
    def from_creds(
        cls,
        creds: Credentials,
    ) -> Self:
        drive_service: DriveService = build(
            serviceName="drive",
            version="v3",
            credentials=creds,
        )

        return cls(
            drive_service=drive_service,
        )

    def query_files(
        self,
        query: str,
        spaces: str = "drive",
        supportsAllDrives: bool = True,
        includeItemsFromAllDrives: bool = True,
        **kwargs,
    ) -> Any:
        results = (
            self.files()
            .list(
                q=query,
                spaces=spaces,
                supportsAllDrives=supportsAllDrives,
                includeItemsFromAllDrives=includeItemsFromAllDrives,
                **kwargs,
            )
            .execute()
        )

        return results

    def find_file(
        self,
        file_name: str,
        folder_id: Optional[str] = None,
    ) -> File | None:
        query = f"name = '{file_name}' and trashed = false"
        if folder_id is not None:
            query += f" and '{folder_id}' in parents"

        results = self.query_files(
            query=query,
            fields="files(id, name)",
        )

        file = (results.get("files", []) or [None])[0]

        return file

    def find_file_id(
        self,
        file_name: str,
        **kwargs,
    ) -> str:
        file: File | None = self.find_file(
            file_name=file_name,
            **kwargs,
        )
        if not file:
            raise FileNotFoundError(f"File '{file_name}' not found.")

        file_id: str | None = file.get("id", None)
        if not file_id:
            raise ValueError(f"File '{file_name}' has no ID.")

        return file_id

    def delete_file_by_id(
        self,
        file_id: str,
    ) -> None:
        self.files().delete(fileId=file_id).execute()

    def delete_file_by_name(
        self,
        file_name: str,
        supportsAllDrives: bool = True,
        **kwargs,
    ) -> None:
        self.files().delete(
            fileId=self.find_file_id(
                file_name=file_name,
                **kwargs,
            ),
            supportsAllDrives=supportsAllDrives,
        ).execute()

    def _create_media(
        self,
        file_path: Path,
        folder_id: Optional[str] = None,
    ) -> tuple[MediaFileUpload, dict[str, Any]]:
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        mimetype = mimetypes.guess_type(url=file_path)[0]
        if not mimetype:
            raise ValueError(f"Could not determine mime type for {file_path}")

        file_metadata = {
            "name": file_path.name,
            "mimeType": mimetype,
            **({"parents": [folder_id]} if folder_id is not None else {}),
        }

        media = MediaFileUpload(
            filename=str(file_path),
            mimetype=mimetype,
            resumable=True,
        )

        return media, file_metadata

    def _upload(
        self,
        file_path: Path,
        folder_id: Optional[str] = None,
    ) -> str:
        media, file_metadata = self._create_media(
            file_path=file_path,
            folder_id=folder_id,
        )

        uploaded_file = (
            self.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields="id",
                supportsAllDrives=True,
            )
            .execute()
        )

        uploaded_file_id: str | None = uploaded_file.get("id", None)
        if not uploaded_file_id:
            raise ValueError(f"Failed to upload file: {file_path}")

        return uploaded_file_id

    def _update(
        self,
        file_path: Path,
        file_id: str,
        folder_id: Optional[str] = None,
    ) -> str:
        media, file_metadata = self._create_media(
            file_path=file_path,
            folder_id=folder_id,
        )

        updated_file = (
            self.files()
            .update(
                fileId=file_id,
                supportsAllDrives=True,
                media_body=media,
            )
            .execute()
        )

        updated_file_id: str | None = updated_file.get("id", None)
        if not updated_file_id:
            raise ValueError(f"Failed to upload file: {file_path}")

        return updated_file_id

    def upload(
        self,
        file_path: Path | str,
        folder_id: Optional[str] = None,
    ) -> str:
        file_path = Path(file_path)

        try:
            file_id = self.find_file_id(file_name=file_path.name)
        except (FileNotFoundError, ValueError):
            file_id = None

        if file_id is not None:
            return self._update(
                file_path=file_path,
                file_id=file_id,
                folder_id=folder_id,
            )
        else:
            return self._upload(
                file_path=file_path,
                folder_id=folder_id,
            )

    def get(
        self,
        file_path: Path | str,
        force_upload: bool = False,
    ) -> str:
        file_path = Path(file_path)

        try:
            file_id = self.find_file_id(file_name=str(file_path))
            if force_upload:
                self.delete_file_by_id(file_id=file_id)
                file_id = self.upload(file_path=file_path)

        except FileNotFoundError:
            file_id = self.upload(file_path=file_path)

        return file_id


class Slides(object):
    def __init__(
        self,
        presentation: SlidesInternal,
        slides_service: SlidesService,
    ) -> None:
        self.id: str = presentation["presentationId"]
        self.service: SlidesService = slides_service
        self.internal: SlidesInternal = presentation

    @property
    def height(
        self,
    ) -> float:
        return self.internal["pageSize"]["height"]["magnitude"] / 12700

    @property
    def width(
        self,
    ) -> float:
        return self.internal["pageSize"]["width"]["magnitude"] / 12700

    @property
    def link(
        self,
    ) -> str:
        return f"https://docs.google.com/presentation/d/{self.id}/edit"

    def slide(
        self,
        slide_number: int,
    ) -> SlideInternal:
        if slide_number < 1 or slide_number > len(self.internal["slides"]):
            raise IndexError(
                f"Slide number {slide_number} is out of range. Presentation has {len(self.internal['slides'])} slides."
            )

        return self.internal["slides"][slide_number - 1]

    @property
    def slides(
        self,
    ) -> list[SlideInternal]:
        return [
            self.slide(slide_number=slide_idx + 1)
            for slide_idx in range(len(self.internal["slides"]))
        ]

    def slide_id(
        self,
        slide_number: int,
    ) -> SlideInternal:
        return self.slide(slide_number=slide_number)["objectId"]

    @property
    def title(
        self,
    ) -> Any:
        return self.internal["title"]

    def open(
        self,
    ) -> None:
        webbrowser.open(url=self.link)

    def get_thumbnail_url(
        self,
        slide_number: int,
    ) -> str:
        slide_id = self.slides[slide_number - 1]["objectId"]
        url = (
            self.service.presentations()
            .pages()
            .getThumbnail(
                presentationId=self.id,
                pageObjectId=slide_id,
            )
            .execute()["contentUrl"]
        )

        return url

    def display(
        self,
        slide_number: Optional[int] = None,
        **kwargs,
    ) -> None:
        if slide_number is not None:
            url = self.get_thumbnail_url(slide_number=slide_number)

            try:
                from IPython.core.display import Image
                from IPython.display import display

                display(
                    Image(
                        url=url,
                        **kwargs,
                    )
                )
            except ImportError:
                print(f"URL: `{url}`")

        else:
            for slide_idx in range(len(self.slides)):
                self.display(slide_number=slide_idx + 1)

    def _repr_mimebundle_(
        self,
        include=None,
        exclude=None,
    ):
        url = self.get_thumbnail_url(slide_number=1)

        return {
            "text/html": f'<img src="{url}" style="max-width: 100%;">',
        }

    def update(
        self,
        requests: list[dict],
    ) -> Self:
        if requests:
            self.service.presentations().batchUpdate(
                presentationId=self.id,
                body={
                    "requests": requests,
                },
            ).execute()

        return self

    @staticmethod
    def service_from_creds(
        creds: Credentials,
    ) -> SlidesService:
        slides_service: SlidesService = build(
            serviceName="slides",
            version="v1",
            credentials=creds,
        )

        return slides_service

    @classmethod
    def fresh_from_creds(
        cls,
        presentation_name: str,
        creds: Credentials,
        template: Optional[str] = None,
    ) -> Self:
        drive = Drive.from_creds(creds=creds)
        slides_service = Slides.service_from_creds(creds=creds)

        return cls(
            presentation=Slides.get(
                presentation_name=presentation_name,
                drive=drive,
                slides_service=slides_service,
                template=template,
            ),
            slides_service=slides_service,
        )

    @classmethod
    def retrieve_from_id(
        cls,
        presentation_id: str,
        slides_service: SlidesService,
    ) -> Self:
        presentation: SlidesInternal = (
            slides_service.presentations()
            .get(
                presentationId=presentation_id,
            )
            .execute()
        )

        return cls(
            presentation=presentation,
            slides_service=slides_service,
        )

    @classmethod
    def retrieve_from_name(
        cls,
        presentation_name: str,
        drive: Drive,
        slides_service: SlidesService,
    ) -> Self:
        presentation_id: str = drive.find_file_id(
            file_name=presentation_name,
        )

        return cls.retrieve_from_id(
            presentation_id=presentation_id,
            slides_service=slides_service,
        )

    @classmethod
    def create_new(
        cls,
        presentation_name: str,
        slides_service: SlidesService,
    ) -> Self:
        presentation_internal: SlidesInternal = (
            slides_service.presentations()
            .create(body={"title": presentation_name})
            .execute()
        )

        presentation = cls(
            presentation=presentation_internal,
            slides_service=slides_service,
        )

        requests = [
            {
                "deleteObject": {"objectId": element["objectId"]},
            }
            for element in presentation.slide(slide_number=1).get("pageElements", [])
            if element.get("placeholder", None)
        ]

        presentation.update(requests=requests)

        return presentation

    @classmethod
    def create_from_template(
        cls,
        presentation_name: str,
        template_name: str,
        drive: Drive,
        slides_service: SlidesService,
    ) -> Self:
        template_id: str = drive.find_file_id(
            file_name=template_name,
        )

        presentation: SlidesInternal = (
            drive.files()
            .copy(
                fileId=template_id,
                body={
                    "name": presentation_name,
                },
            )
            .execute()
        )

        return cls(
            presentation=presentation,
            slides_service=slides_service,
        )

    @classmethod
    def get(
        cls,
        presentation_name: str,
        drive: Drive,
        slides_service: SlidesService,
        template: Optional[str] = None,
    ) -> Self:
        try:
            return cls.retrieve_from_name(
                presentation_name=presentation_name,
                drive=drive,
                slides_service=slides_service,
            )

        except FileNotFoundError:
            if template is None:
                return cls.create_new(
                    presentation_name=presentation_name,
                    slides_service=slides_service,
                )
            else:
                return cls.create_from_template(
                    presentation_name=presentation_name,
                    template_name=template,
                    drive=drive,
                    slides_service=slides_service,
                )

    def reset(
        self,
        drive: Drive,
    ) -> Self:
        presentation_name = self.title

        drive.delete_file_by_id(
            file_id=self.id,
        )

        new_presentation = self.create_new(
            presentation_name=presentation_name,
            slides_service=self.service,
        )

        self.internal = new_presentation.internal
        self.id = new_presentation.id

        return self

    # TODO: New slide: Inputs include optional insertion position and optional slide id else `uuid uuid.uuid4().hex`

    def copy_slide(
        self,
        slide_number: Optional[int] = None,
        to_position: Optional[int] = None,
    ) -> Self:
        if to_position is not None and slide_number is None:
            raise ValueError(
                "If 'to_position' is specified, 'slide_number' must also be specified."
            )

        if slide_number is None:
            source_index = len(self.slides) - 1
        else:
            source_index = slide_number - 1  # Convert to zero-based index

        if source_index < 0 or source_index >= len(self.slides):
            raise IndexError(
                f"Slide number {source_index + 1} is out of range. Presentation has {len(self.slides)} slides."
            )

        if to_position is None:
            target_index = len(self.slides)
        else:
            target_index = to_position - 1

        if target_index < 0 or target_index > len(self.slides):
            raise IndexError(
                f"Target position {target_index + 1} is out of range. Presentation has {len(self.slides)} slides."
            )

        slide_id = self.slides[source_index]["objectId"]

        requests = [
            {"duplicateObject": {"objectId": slide_id, "insertionIndex": target_index}},
        ]

        self.update(requests=requests)

        return self

    def delete_slide(
        self,
        slide_number: int,
    ) -> Self:
        if len(self.slides) == 1:
            raise ValueError("Cannot delete the only slide in the presentation.")

        if slide_number < 1 or slide_number > len(self.slides):
            raise IndexError(
                f"Slide number {slide_number} is out of range. Presentation has {len(self.slides)} slides."
            )

        slide_id = self.slides[slide_number - 1]["objectId"]
        if slide_id is None:
            raise ValueError(f"Slide number {slide_number} has no ID.")

        requests = [
            {
                "deleteObject": {
                    "objectId": slide_id,
                },
            },
        ]

        self.update(requests=requests)

        return self

    def move_slide(
        self,
        slide_number: int,
        to_position: int,
    ) -> Self:
        if slide_number == to_position:
            raise ValueError("Slide number and target position cannot be the same.")

        self.copy_slide(
            slide_number=slide_number,
            to_position=to_position,
        )
        self.delete_slide(
            slide_number=slide_number,
        )
        return self

    def insert_text(
        self,
        text: str,
        slide_number: Optional[int] = None,
        height: Optional[float] = None,
        width: Optional[float] = None,
        x_shift: Optional[float] = None,
        y_shift: Optional[float] = None,
        element_id: str = uuid.uuid4().hex,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        strikethrough: bool = False,
        font_size: Optional[int] = None,
        font_family: Optional[str] = None,
        colour: Optional[Colour | str] = None,
        background_colour: Optional[Colour | str] = None,
        link: Optional[str] = None,
        **kwargs,
    ) -> Self:
        if height is None:
            height = self.height * 0.9
        if width is None:
            width = self.width * 0.9
        if x_shift is None:
            x_shift = self.width * 0.05
        if y_shift is None:
            y_shift = self.height * 0.05

        theme_color = ""
        parsed_colour = Colour(0, 0, 0)
        theme_background_color = ""
        parsed_background_colour = Colour(0, 0, 0)

        if colour is not None and not isinstance(colour, Colour):
            if colour.startswith("theme-"):
                theme_color = colour[len("theme-") :]
            else:
                parsed_colour = Colour.parse(colour=colour)
        if background_colour is not None and not isinstance(background_colour, Colour):
            if background_colour.startswith("theme-"):
                theme_background_color = background_colour[len("theme-") :]
            else:
                parsed_background_colour = Colour.parse(colour=background_colour)

        if slide_number is None:
            slide_number = len(self.slides)
        elif slide_number < 1 or slide_number > len(self.slides):
            raise IndexError(
                f"Slide number {slide_number} is out of range. Presentation has {len(self.slides)} slides."
            )

        requests: list[dict[str, Any]] = [
            {
                "createShape": {
                    "objectId": element_id,
                    "shapeType": "TEXT_BOX",
                    "elementProperties": {
                        "pageObjectId": self.slide_id(slide_number=slide_number),
                        "size": {
                            "height": {
                                "magnitude": height,
                                "unit": "PT",
                            },
                            "width": {
                                "magnitude": width,
                                "unit": "PT",
                            },
                        },
                        "transform": {
                            "scaleX": 1,
                            "scaleY": 1,
                            "translateX": x_shift,
                            "translateY": y_shift,
                            "unit": "PT",
                        },
                    },
                }
            },
            {
                "insertText": {
                    "objectId": element_id,
                    "insertionIndex": 0,
                    "text": text,
                }
            },
            {
                "updateTextStyle": {
                    "objectId": element_id,
                    "style": {
                        **(
                            {"fontSize": {"magnitude": font_size, "unit": "PT"}}
                            if font_size is not None
                            else {}
                        ),
                        "bold": bold,
                        "italic": italic,
                        "underline": underline,
                        "strikethrough": strikethrough,
                        **(
                            {
                                "foregroundColor": (
                                    {}
                                    if colour is None
                                    else (
                                        {
                                            "opaqueColor": {
                                                "rgbColor": {
                                                    "red": parsed_colour.r / 255,
                                                    "green": parsed_colour.g / 255,
                                                    "blue": parsed_colour.b / 255,
                                                }
                                            }
                                        }
                                        if not (
                                            isinstance(colour, str)
                                            and colour.startswith("theme-")
                                        )
                                        else {"themeColor": theme_color}
                                    )
                                )
                            }
                            if colour
                            else {}
                        ),
                        **(
                            {
                                "backgroundColor": (
                                    {}
                                    if colour is None
                                    else {
                                        "opaqueColor": {
                                            "rgbColor": {
                                                "red": parsed_background_colour.r / 255,
                                                "green": parsed_background_colour.g
                                                / 255,
                                                "blue": parsed_background_colour.b
                                                / 255,
                                            }
                                        }
                                    }
                                    if not (
                                        isinstance(background_colour, str)
                                        and background_colour.startswith("theme-")
                                    )
                                    else {"themeColor": theme_background_color}
                                )
                            }
                            if background_colour
                            else {}
                        ),
                        **({"fontFamily": font_family} if font_family else {}),
                        **({"link": {"url": link}} if link is not None else {}),
                        **kwargs,
                    },
                    "textRange": {"type": "ALL"},
                    "fields": "*",
                }
            },
        ]

        return self.update(requests=requests)

    def insert_image(
        self,
        image_path: Path | str,
        slide_number: Optional[int] = None,
        height: Optional[float] = None,
        width: Optional[float] = None,
        x_shift: Optional[float] = None,
        y_shift: Optional[float] = None,
        element_id: str = uuid.uuid4().hex,
        drive: Optional[Drive] = None,
        force_upload: bool = False,
    ) -> Self:
        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        if height is None:
            height = self.height * 0.9
        if width is None:
            width = self.width * 0.9
        if x_shift is None:
            x_shift = self.width * 0.05
        if y_shift is None:
            y_shift = self.height * 0.05

        if slide_number is None:
            slide_number = len(self.slides)
        elif slide_number < 1 or slide_number > len(self.slides):
            raise IndexError(
                f"Slide number {slide_number} is out of range. Presentation has {len(self.slides)} slides."
            )

        mimetype = mimetypes.guess_type(url=image_path)[0]
        if not mimetype:
            raise ValueError(f"Could not determine mime type for {image_path}")

        image_data = b64encode(image_path.read_bytes()).decode()
        data_url = f"data:{mimetype};base64,{image_data}"

        if len(data_url) <= 2000:  # Direct insertion if under 2KB
            image_url = data_url
        else:
            if drive is None:
                raise ValueError("Drive instance required for large images")

            try:
                uploaded_file_id = drive.get(
                    file_path=image_path,
                    force_upload=force_upload,
                )

                file_data = (
                    drive.files()
                    .get(
                        fileId=uploaded_file_id,
                        fields="thumbnailLink",
                        supportsAllDrives=True,
                    )
                    .execute()
                )

                if "thumbnailLink" not in file_data:
                    raise ValueError("Could not generate thumbnail for image")

                image_url = file_data["thumbnailLink"]

            except Exception as err:
                raise ValueError(f"Failed to upload image to Drive: {err}") from err

        requests = [
            {
                "createImage": {
                    "objectId": element_id,
                    "url": image_url,
                    "elementProperties": {
                        "pageObjectId": self.slide_id(slide_number=slide_number),
                        "size": {
                            "height": {"magnitude": height, "unit": "PT"},
                            "width": {"magnitude": width, "unit": "PT"},
                        },
                        "transform": {
                            "scaleX": 1,
                            "scaleY": 1,
                            "translateX": x_shift,
                            "translateY": y_shift,
                            "unit": "PT",
                        },
                    },
                }
            }
        ]

        return self.update(requests=requests)


class Sheet(object):
    def __init__(
        self,
        sheet: SheetInternal,
        parent: Sheets,
        sheets_service: SheetsService,
    ) -> None:
        self.service: SheetsService = sheets_service
        self.internal: SheetInternal = sheet
        self.id: str = self.internal.get("properties", {})["sheetId"]
        self.parent = parent

    @property
    def title(
        self,
    ) -> str:
        return self.internal.get("properties", {}).get("title")

    @property
    def index(
        self,
    ) -> int:
        return self.internal.get("properties", {}).get("index")

    @property
    def rows(
        self,
    ) -> int:
        return (
            self.internal.get("properties", {})
            .get("gridProperties", {})
            .get("rowCount")
        )

    @property
    def columns(
        self,
    ) -> int:
        return (
            self.internal.get("properties", {})
            .get("gridProperties", {})
            .get("columnCount")
        )

    def to_arrays(
        self,
        range: Optional[str] = None,
    ) -> list:
        data = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=self.parent.id,
                range=f"{self.title}!A1:{column_to_excel(column=self.columns)}{self.rows}"
                if range is None
                else f"{self.title}!{range}",
            )
            .execute()
        )

        values = data.get("values", [])

        return values

    def to_pandas(
        self,
        range: Optional[str] = None,
    ) -> DataFrame:
        return DataFrame(data=self.to_arrays(range=range))

    def to_polars(
        self,
        range: Optional[str] = None,
    ) -> pl.DataFrame:
        raise NotImplementedError("Polars not implemented yet")

    @property
    def df(
        self,
    ) -> DataFrame:
        return self.to_pandas(
            range=None,
        )

    def __repr__(
        self,
    ) -> str:
        return repr(self.df)

    def _repr_html_(
        self,
    ) -> str:
        return self.df.utils.styler.set_caption(self.title)._repr_html_()  # type: ignore

    def _repr_latex_(
        self,
    ) -> str:
        return self.df.utils.styler.set_caption(self.title)._repr_latex_()  # type: ignore

    # def _repr_mimebundle_(
    #     self,
    #     include=None,
    #     exclude=None,
    # ) -> str:
    #     return self.df._repr_mimebundle_(  # type: ignore
    #         include=include,
    #         exclude=exclude,
    #     )

    def update_values(
        self,
        range: str,
        values: list[list[Any]],
        as_user: bool = True,
    ) -> Self:
        self.parent = self.parent.update_values(
            range=range,
            values=values,
            as_user=as_user,
        )

        self.internal = self.parent.sheet(sheet_number=self.index + 1).internal

        return self

    def insert(
        self,
        range: Optional[str],
        values: list[list[Any]],
        as_user: bool = True,
    ) -> Self:
        return self.update_values(
            range=f"{self.title}!{'A1' if range is None else range}",
            values=values,
            as_user=as_user,
        )

    def insert_df(
        self,
        range: Optional[str],
        df: DataFrame,
        as_user: bool = True,
        index_name: str = "Index",
    ) -> Self:
        df_with_index = df.reset_index(
            names=index_name,
        )

        return self.update_values(
            range=f"{self.title}!{'A1' if range is None else range}",
            values=[df_with_index.columns.to_list()]
            + df_with_index.to_numpy().tolist(),  # type: ignore
            as_user=as_user,
        )

    # TODO: Insert values, Insert formula


class Sheets(object):
    def __init__(
        self,
        sheets: SheetsInternal,
        sheets_service: SheetsService,
    ) -> None:
        self.service: SheetsService = sheets_service
        self.internal: SheetsInternal = sheets
        self.id: str = self.internal["spreadsheetId"]

    @property
    def link(
        self,
    ) -> str:
        return f"https://docs.google.com/presentation/d/{self.id}/edit"

    def sheet(
        self,
        sheet_number: int,
    ) -> Sheet:
        if sheet_number < 1 or sheet_number > len(self.internal["sheets"]):
            raise IndexError(
                f"Sheet number {sheet_number} is out of range. Spreadsheet has {len(self.internal['sheets'])} sheets."
            )

        sheet_internal = self.internal["sheets"][sheet_number - 1]

        return Sheet(
            sheet=sheet_internal,
            parent=self,
            sheets_service=self.service,
        )

    def sheet_from_name(
        self,
        sheet_name: str,
    ) -> Sheet:
        sheet_number = next(
            (
                idx + 1
                for idx, sheet in enumerate(self.internal["sheets"])
                if sheet.get("properties", {}).get("title", "") == sheet_name
            ),
            None,
        )

        if sheet_number is None:
            raise ValueError(f"Sheet with title '{sheet_name}' not found.")

        return self.sheet(
            sheet_number=sheet_number,
        )

    @property
    def sheets(
        self,
    ) -> list[Sheet]:
        return [
            self.sheet(sheet_number=sheet_idx + 1)
            for sheet_idx in range(len(self.internal["sheets"]))
        ]

    @property
    def title(
        self,
    ) -> str:
        return self.internal.get("properties", {}).get("title")

    def open(
        self,
    ) -> None:
        webbrowser.open(url=self.link)

    def __repr__(
        self,
    ) -> str:
        return self.sheet(sheet_number=1).__repr__()

    def _repr_html_(
        self,
    ) -> str:
        return self.sheet(sheet_number=1)._repr_html_()

    def _repr_latex_(
        self,
    ) -> str:
        return self.sheet(sheet_number=1)._repr_latex_()

    # def _repr_mimebundle_(
    #     self,
    #     include=None,
    #     exclude=None,
    # ):
    #     return self.sheet(sheet_number=1)._repr_mimebundle_()

    def refresh(
        self,
    ) -> Self:
        self.internal = self.service.spreadsheets().get(spreadsheetId=self.id).execute()

        return self

    def update(
        self,
        requests: list[dict],
    ) -> Self:
        if requests:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.id,
                body={
                    "requests": requests,
                },
            ).execute()

        self.refresh()

        return self

    def update_values(
        self,
        range: str,
        values: list[list[Any]],
        as_user: bool = True,
    ) -> Self:
        self.service.spreadsheets().values().update(
            spreadsheetId=self.id,
            range=range,
            valueInputOption="RAW" if not as_user else "USER_ENTERED",
            body={
                "values": values,
            },
        ).execute()

        self.refresh()

        return self

    @staticmethod
    def service_from_creds(
        creds: Credentials,
    ) -> SheetsService:
        sheets_service: SheetsService = build(
            serviceName="sheets",
            version="v4",
            credentials=creds,
        )

        return sheets_service

    @classmethod
    def fresh_from_creds(
        cls,
        sheets_name: str,
        creds: Credentials,
        template: Optional[str] = None,
    ) -> Self:
        drive = Drive.from_creds(creds=creds)
        sheets_service = Sheets.service_from_creds(creds=creds)

        return cls(
            sheets=Sheets.get(
                sheets_name=sheets_name,
                drive=drive,
                sheets_service=sheets_service,
                template=template,
            ),
            sheets_service=sheets_service,
        )

    @classmethod
    def retrieve_from_id(
        cls,
        sheets_id: str,
        sheets_service: SheetsService,
    ) -> Self:
        sheets: SheetsInternal = (
            sheets_service.spreadsheets()
            .get(
                spreadsheetId=sheets_id,
            )
            .execute()
        )

        return cls(
            sheets=sheets,
            sheets_service=sheets_service,
        )

    @classmethod
    def retrieve_from_name(
        cls,
        sheets_name: str,
        drive: Drive,
        sheets_service: SheetsService,
    ) -> Self:
        sheets_id: str = drive.find_file_id(
            file_name=sheets_name,
        )

        return cls.retrieve_from_id(
            sheets_id=sheets_id,
            sheets_service=sheets_service,
        )

    @classmethod
    def create_new(
        cls,
        sheets_name: str,
        sheets_service: SheetsService,
    ) -> Self:
        sheets_internal: SheetsInternal = (
            sheets_service.spreadsheets()
            .create(
                body={
                    "properties": {"title": sheets_name},
                },
            )
            .execute()
        )

        presentation = cls(
            sheets=sheets_internal,
            sheets_service=sheets_service,
        )

        return presentation

    @classmethod
    def create_from_template(
        cls,
        sheets_name: str,
        template_name: str,
        drive: Drive,
        sheets_service: SheetsService,
    ) -> Self:
        template_id: str = drive.find_file_id(
            file_name=template_name,
        )

        sheets: SheetsInternal = (
            drive.files()
            .copy(
                fileId=template_id,
                body={
                    "name": sheets_name,
                },
            )
            .execute()
        )

        return cls(
            sheets=sheets,
            sheets_service=sheets_service,
        )

    @classmethod
    def get(
        cls,
        sheets_name: str,
        drive: Drive,
        sheets_service: SheetsService,
        template: Optional[str] = None,
    ) -> Self:
        try:
            return cls.retrieve_from_name(
                sheets_name=sheets_name,
                drive=drive,
                sheets_service=sheets_service,
            )

        except FileNotFoundError:
            if template is None:
                return cls.create_new(
                    sheets_name=sheets_name,
                    sheets_service=sheets_service,
                )
            else:
                return cls.create_from_template(
                    sheets_name=sheets_name,
                    template_name=template,
                    drive=drive,
                    sheets_service=sheets_service,
                )

    def reset(
        self,
        drive: Drive,
    ) -> Self:
        sheets_name = self.title

        drive.delete_file_by_id(
            file_id=self.id,
        )

        new_sheets = self.create_new(
            sheets_name=sheets_name,
            sheets_service=self.service,
        )

        self.internal = new_sheets.internal
        self.id = new_sheets.id

        return self

    def rename_sheet(
        self,
        sheet: Sheet,
        new_title: str,
    ) -> Self:
        if new_title in [sheet.title for sheet in self.sheets]:
            raise ValueError(f"Sheet title {new_title} is already used")

        return self.update(
            requests=[
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sheet.id,
                            "title": new_title,
                        },
                        "fields": "title",
                    }
                }
            ]
        )

    def move_sheet(
        self,
        sheet: Sheet,
        to_position: Optional[int] = None,
    ) -> Self:
        target_index = (len(self.sheets) if to_position is None else to_position) - 1
        if target_index < 0 or target_index >= len(self.sheets):
            raise IndexError(
                f"Target position {target_index + 1} is out of range. Spreadsheet has {len(self.sheets)} sheets."
            )

        return self.update(
            requests=[
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sheet.id,
                            "index": target_index,
                        },
                        "fields": "index",
                    }
                }
            ]
        )

    def copy_sheet(
        self,
        sheet: Optional[Sheet] = None,
        new_title: Optional[str] = None,
        to_position: Optional[int] = None,
    ) -> Self:
        if to_position is not None and sheet is None:
            raise ValueError(
                "If 'to_position' is specified, 'sheet' must also be specified."
            )

        sheet_number = len(self.sheets) if sheet is None else sheet.index + 1

        if sheet_number < 1 or sheet_number > len(self.sheets):
            raise IndexError(
                f"Sheet number {sheet_number} is out of range. Spreadsheet has {len(self.sheets)} sheets."
            )

        target_index = len(self.sheets) if to_position is None else (to_position - 1)
        if target_index < 0 or target_index > len(self.sheets):
            raise IndexError(
                f"Target position {target_index + 1} is out of range. Spreadsheet has {len(self.sheets)} sheets."
            )

        sheet_id = self.sheet(sheet_number=sheet_number).id

        if new_title is not None and new_title in [
            sheet.title for sheet in self.sheets
        ]:
            raise ValueError(f"Sheet title {new_title} is already used")

        new_sheet_id = (
            self.service.spreadsheets()
            .sheets()
            .copyTo(
                spreadsheetId=self.id,
                sheetId=sheet_id,
                body=dict(destinationSpreadsheetId=self.id),
            )
            .execute()["sheetId"]
        )

        requests = []
        if to_position is not None:
            requests.append(
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": new_sheet_id,
                            "index": target_index,
                        },
                        "fields": "index",
                    }
                }
            )

        if new_title is not None:
            requests.append(
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": new_sheet_id,
                            "title": new_title,
                        },
                        "fields": "title",
                    }
                }
            )

        return self.update(requests=requests)

    def delete_sheet(
        self,
        sheet: Sheet,
    ) -> Self:
        requests = [
            {
                "deleteSheet": {
                    "sheetId": sheet.id,
                }
            }
        ]

        return self.update(requests=requests)

    def insert_sheet(
        self,
        new_title: Optional[str] = None,
        to_position: Optional[int] = None,
    ) -> Self:
        target_index = len(self.sheets) if to_position is None else (to_position - 1)
        if target_index < 0 or target_index > len(self.sheets):
            raise IndexError(
                f"Target position {target_index + 1} is out of range. Spreadsheet has {len(self.sheets)} sheets."
            )

        if new_title is not None and new_title in [
            sheet.title for sheet in self.sheets
        ]:
            raise ValueError(f"Sheet title {new_title} is already used")

        sheet_properties: dict[str, str | int] = {}
        if to_position is not None:
            sheet_properties["index"] = target_index

        if new_title is not None:
            sheet_properties["title"] = new_title

        return self.update(
            requests=[
                {
                    "addSheet": {
                        "properties": sheet_properties,
                    }
                }
            ]
        )

    def add_sheet_from_dataframe(
        self,
        df: DataFrame,
        new_title: Optional[str] = None,
        to_position: Optional[int] = None,
        as_user=False,
        **kwargs,
    ) -> Self:
        self.insert_sheet(
            new_title=new_title,
            to_position=to_position,
        )

        sheet = self.sheet(
            sheet_number=len(self.sheets) if to_position is None else to_position
        ).insert_df(
            range=None,
            df=df,
            as_user=as_user,
            **kwargs,
        )

        self.internal = sheet.parent.internal

        return self
