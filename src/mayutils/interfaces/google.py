from typing import Optional, Self, Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import webbrowser

DriveService = Any
SlidesService = Any
PresentationInternal = Any
File = Any


class Drive(object):
    def __init__(
        self,
        drive_service: DriveService,
    ) -> None:
        self.service = drive_service

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

    def find_file(
        self,
        file_name: str,
    ) -> File | None:
        query = f"name = '{file_name}' and mimeType = 'application/vnd.google-apps.presentation' and trashed = false"

        results = (
            self.service.files()
            .list(
                q=query,
                spaces="drive",
                fields="files(id, name)",
            )
            .execute()
        )

        files = results.get("files", [])
        file = files[0] if files else None

        return file


class Presentation(object):
    def __init__(
        self,
        presentation: PresentationInternal,
        slides_service: SlidesService,
    ) -> None:
        self.id: str = presentation["presentationId"]
        self.service: SlidesService = slides_service
        self.slides: PresentationInternal = presentation

    @property
    def link(
        self,
    ) -> str:
        return f"https://docs.google.com/presentation/d/{self.id}/edit"

    def open(
        self,
    ) -> None:
        webbrowser.open(self.link)

    def get_thumbnail_url(
        self,
        slide_number: int,
    ) -> str:
        slide_id = self.slides["slides"][slide_number - 1]["objectId"]
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
            for slide_idx in range(len(self.slides["slides"])):
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
    ) -> None:
        self.service.presentations().batchUpdate(
            presentationId=self.id,
            body={
                "requests": requests,
            },
        ).execute()

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
    def retrieve_from_id(
        cls,
        presentation_id: str,
        slides_service: SlidesService,
    ) -> Self:
        presentation: PresentationInternal = (
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
        file: File | None = drive.find_file(
            file_name=presentation_name,
        )
        if not file:
            raise FileNotFoundError(f"Presentation '{presentation_name}' not found.")

        presentation_id: str | None = file.get("id", None)
        if not presentation_id:
            raise ValueError(f"Presentation '{presentation_name}' has no ID.")

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
        presentation: PresentationInternal = (
            slides_service.presentations()
            .create(body={"title": presentation_name})
            .execute()
        )

        return cls(
            presentation=presentation,
            slides_service=slides_service,
        )

    @classmethod
    def create_from_template(
        cls,
        presentation_name: str,
        template_name: str,
        drive: Drive,
        slides_service: SlidesService,
    ) -> Self:
        file: File | None = drive.find_file(
            file_name=template_name,
        )
        if not file:
            raise FileNotFoundError(f"Template '{template_name}' not found.")

        template_id: str | None = file.get("id", None)
        if not template_id:
            raise ValueError(f"Template '{template_name}' has no ID.")

        presentation: PresentationInternal = (
            drive.service.files()
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
            source_index = len(self.slides["slides"]) - 1
        else:
            source_index = slide_number - 1  # Convert to zero-based index

        if source_index < 0 or source_index >= len(self.slides["slides"]):
            raise IndexError(
                f"Slide number {source_index + 1} is out of range. Presentation has {len(self.slides['slides'])} slides."
            )

        if to_position is None:
            target_index = len(self.slides["slides"])
        else:
            target_index = to_position - 1

        if target_index < 0 or target_index > len(self.slides["slides"]):
            raise IndexError(
                f"Target position {target_index + 1} is out of range. Presentation has {len(self.slides['slides'])} slides."
            )

        slide_id = self.slides["slides"][source_index]["objectId"]

        requests = [
            {"duplicateObject": {"objectId": slide_id, "insertionIndex": target_index}},
        ]

        self.update(requests=requests)

        return self

    def delete_slide(
        self,
        slide_number: int,
    ) -> Self:
        if len(self.slides["slides"]) == 1:
            raise ValueError("Cannot delete the only slide in the presentation.")

        if slide_number < 1 or slide_number > len(self.slides["slides"]):
            raise IndexError(
                f"Slide number {slide_number} is out of range. Presentation has {len(self.slides['slides'])} slides."
            )

        slide_id = self.slides["slides"][slide_number - 1]["objectId"]
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
