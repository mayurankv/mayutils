"""Google Slides presentation wrapper.

Provides the :class:`Slides` helper which wraps the raw Google Slides REST
response dictionary together with a live ``googleapiclient`` service, exposing
ergonomic CRUD operations over slides (create, duplicate, delete, move) and
convenience insertion helpers for styled text boxes and images. The wrapper
maintains the decoded presentation payload locally and re-issues
``batchUpdate`` requests through the shared service, and composes with
:class:`mayutils.interfaces.cloud.google.Drive` to locate templates, upload
large image assets that exceed the inline data URL size limit, and resolve
presentations by name rather than ID.
"""

from __future__ import annotations

import mimetypes
import uuid
import webbrowser
from base64 import b64encode
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self, cast

from mayutils.core.extras import may_require_extras
from mayutils.interfaces.cloud.google import Drive
from mayutils.objects.colours import Colour

with may_require_extras():
    from googleapiclient.discovery import build  # pyright: ignore[reportUnknownVariableType]

if TYPE_CHECKING:
    from google.oauth2.credentials import Credentials
    from googleapiclient._apis.slides.v1.resources import SlidesResource  # pyright: ignore[reportMissingModuleSource]
    from googleapiclient._apis.slides.v1.schemas import Page, Presentation  # pyright: ignore[reportMissingModuleSource]
    from googleapiclient._apis.slides.v1.schemas import Request as SlidesRequest  # pyright: ignore[reportMissingModuleSource]

EMU_UNITS_PER_POINT = 12700


class Slides:
    """High-level wrapper around a Google Slides presentation.

    Couples a decoded Slides REST payload (``Presentation``) with a live
    ``googleapiclient`` service so that CRUD operations on slides and common
    content insertions (text, images) can be issued without hand-building
    ``batchUpdate`` bodies. Instances cache the presentation payload locally
    and are refreshed implicitly as mutating methods are called.

    Parameters
    ----------
    presentation : Presentation
        Decoded Google Slides REST response describing an existing
        presentation. Provides the Drive file ID, title, page size and the
        ordered list of slides.
    slides_service : SlidesResource
        Authenticated ``googleapiclient`` Slides v1 service client used to
        issue ``batchUpdate`` and ``get`` calls against the Slides API.

    Attributes
    ----------
    id : str
        Drive file ID of the wrapped presentation.
    service : SlidesResource
        The underlying Slides v1 service client.
    internal : Presentation
        The most recently observed REST payload for the presentation.
    """

    def __init__(
        self,
        presentation: Presentation,
        /,
        *,
        slides_service: SlidesResource,
    ) -> None:
        """Initialise the wrapper from an API payload and service client.

        Parameters
        ----------
        presentation : Presentation
            Decoded Slides REST response providing at minimum a
            ``presentationId`` and list of slides; used as the initial
            snapshot of presentation state.
        slides_service : SlidesResource
            Authenticated Slides v1 service client used for all subsequent
            API interactions.
        """
        self.id: str = presentation["presentationId"]  # pyright: ignore[reportTypedDictNotRequiredAccess]
        self.service: SlidesResource = slides_service
        self.internal: Presentation = presentation

    @property
    def _internal_slides(
        self,
    ) -> list[Page]:
        """Return the raw ``slides`` list from the presentation payload."""
        return self.internal["slides"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def height(
        self,
    ) -> float:
        """Height of each slide in typographic points.

        The underlying Slides API reports dimensions in English Metric Units
        (EMU); the value is converted to points (1 pt = 12 700 EMU) to match
        the units accepted by insertion helpers such as :meth:`insert_text`
        and :meth:`insert_image`.

        Returns
        -------
        float
            Slide height in points.
        """
        return self.internal["pageSize"]["height"]["magnitude"] / EMU_UNITS_PER_POINT  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def width(
        self,
    ) -> float:
        """Width of each slide in typographic points.

        Converts the EMU value reported by the Slides API to points, enabling
        direct use as ``width``/``x_shift`` arguments to the insertion
        helpers.

        Returns
        -------
        float
            Slide width in points.
        """
        return self.internal["pageSize"]["width"]["magnitude"] / EMU_UNITS_PER_POINT  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def link(
        self,
    ) -> str:
        """Web editor URL for the presentation.

        Returns
        -------
        str
            Fully qualified ``docs.google.com`` URL that opens the
            presentation in the Google Slides web editor.
        """
        return f"https://docs.google.com/presentation/d/{self.id}/edit"

    def slide(
        self,
        slide_number: int,
        /,
    ) -> Page:
        """Return the raw payload for a single slide by 1-indexed position.

        Parameters
        ----------
        slide_number : int
            1-based position of the slide within the presentation. ``1``
            refers to the first slide in reading order.

        Returns
        -------
        Page
            The Slides REST payload fragment describing the requested page,
            including ``objectId`` and ``pageElements``.

        Raises
        ------
        IndexError
            If ``slide_number`` is less than ``1`` or exceeds the number of
            slides currently held in :attr:`internal`.
        """
        if slide_number < 1 or slide_number > len(self._internal_slides):
            msg = f"Slide number {slide_number} is out of range. Presentation has {len(self._internal_slides)} slides."
            raise IndexError(msg)

        return self._internal_slides[slide_number - 1]

    @property
    def slides(
        self,
    ) -> list[Page]:
        """All slide payloads in presentation order.

        Returns
        -------
        list[Page]
            Ordered list of per-slide REST payloads mirroring the order
            users see in the web editor.
        """
        return [self.slide(slide_idx + 1) for slide_idx in range(len(self._internal_slides))]

    def slide_id(
        self,
        slide_number: int,
        /,
    ) -> str:
        """Return the Google-assigned ``objectId`` for a slide.

        Parameters
        ----------
        slide_number : int
            1-based position of the slide whose identifier is required.

        Returns
        -------
        str
            Opaque Slides ``objectId`` string suitable as
            ``pageObjectId`` when building ``batchUpdate`` requests.

        Raises
        ------
        IndexError
            If ``slide_number`` falls outside the current slide range (see
            :meth:`slide`).
        """
        return self.slide(slide_number)["objectId"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def title(
        self,
    ) -> str:
        """Presentation title as reported by the Slides service.

        Returns
        -------
        str
            Drive file title taken from the ``title`` field of the Slides
            REST payload.
        """
        return self.internal["title"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    def open(
        self,
    ) -> None:
        """Open the presentation in the system default web browser.

        Notes
        -----
        Delegates to :func:`webbrowser.open` against :attr:`link`; the call
        is fire-and-forget and returns even if no browser is available.
        """
        webbrowser.open(url=self.link)

    def get_thumbnail_url(
        self,
        slide_number: int,
    ) -> str:
        """Fetch a rendered thumbnail URL for a single slide.

        Parameters
        ----------
        slide_number : int
            1-based position of the slide to render.

        Returns
        -------
        str
            Short-lived, authenticated ``contentUrl`` returned by the Slides
            ``pages.getThumbnail`` endpoint, suitable for embedding in
            ``<img>`` tags or IPython display widgets.
        """
        slide_id = self.slide_id(slide_number)
        return (
            self.service.presentations()
            .pages()
            .getThumbnail(
                presentationId=self.id,
                pageObjectId=slide_id,
            )
            .execute()["contentUrl"]  # pyright: ignore[reportTypedDictNotRequiredAccess]
        )

    def display(
        self,
        *,
        slide_number: int | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Render a slide (or the full deck) inline in an IPython frontend.

        Parameters
        ----------
        slide_number : int | None, default None
            1-based slide index to render. When ``None`` every slide in the
            deck is rendered sequentially via recursive calls.
        **kwargs
            Additional keyword arguments forwarded to
            :class:`IPython.core.display.Image` (e.g. ``width``, ``height``)
            for per-slide display customisation.

        Notes
        -----
        If IPython is not importable the function silently returns, so it is
        safe to invoke from non-notebook contexts.
        """
        if slide_number is not None:
            url = self.get_thumbnail_url(slide_number=slide_number)

            try:
                from IPython.core.display import Image  # noqa: PLC0415
                from IPython.display import display  # pyright: ignore[reportUnknownVariableType] # noqa: PLC0415

                display(
                    Image(
                        url=url,
                        **kwargs,
                    )
                )
            except ImportError:
                pass

        else:
            for slide_idx in range(len(self.slides)):
                self.display(slide_number=slide_idx + 1)

    def _repr_mimebundle_(
        self,
        include: None = None,  # noqa: ARG002
        exclude: None = None,  # noqa: ARG002
    ) -> dict[str, str]:
        """Provide a MIME bundle rendering for Jupyter rich display.

        Parameters
        ----------
        include : Sequence[str] | None, default None
            MIME types the frontend has requested; accepted for interface
            compatibility but not consulted.
        exclude : Sequence[str] | None, default None
            MIME types the frontend wishes to exclude; accepted for
            interface compatibility but not consulted.

        Returns
        -------
        dict[str, str]
            Mapping from MIME type to payload. Currently emits a single
            ``text/html`` entry showing the first slide's thumbnail at
            responsive width.
        """
        url = self.get_thumbnail_url(slide_number=1)

        return {
            "text/html": f'<img src="{url}" style="max-width: 100%;">',
        }

    def update(
        self,
        requests: list[SlidesRequest],
        /,
    ) -> Self:
        """Submit a list of raw API requests and refresh local state.

        Parameters
        ----------
        requests : list[SlidesRequest]
            Sequence of Slides ``batchUpdate`` request objects (for example
            ``{"createShape": {...}}``). An empty list is a no-op.

        Returns
        -------
        Self
            The same wrapper instance, enabling fluent chaining of
            mutation calls.

        Notes
        -----
        This method issues a single ``batchUpdate`` call; atomicity and
        ordering guarantees follow Google's documented semantics for that
        endpoint.
        """
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
        /,
    ) -> SlidesResource:
        """Build a Slides v1 service client from OAuth credentials.

        Parameters
        ----------
        creds : Credentials
            Authorised ``google.oauth2.credentials.Credentials`` object
            carrying the scopes necessary for Slides read/write access.

        Returns
        -------
        SlidesResource
            A ready-to-use ``googleapiclient`` discovery service pinned to
            the Slides v1 API.
        """
        slides_service: SlidesResource = build(  # pyright: ignore[reportUnknownVariableType]
            serviceName="slides",
            version="v1",
            credentials=creds,
        )

        return slides_service  # pyright: ignore[reportUnknownVariableType]

    @classmethod
    def fresh_from_creds(
        cls,
        presentation_name: str,
        /,
        *,
        creds: Credentials,
        template: str | None = None,
    ) -> Self:
        """Resolve (or create) a presentation by name using raw credentials.

        Parameters
        ----------
        presentation_name : str
            Drive file name to look up. If no such file exists a new
            presentation is created with this title.
        creds : Credentials
            OAuth credentials used to build both the Drive client (for
            name resolution) and the Slides service client.
        template : str | None, default None
            Optional Drive file name of a template presentation. When
            provided and no existing presentation matches
            ``presentation_name``, the template is copied rather than a
            blank deck being created.

        Returns
        -------
        Self
            Wrapper bound to the resolved or freshly created presentation.
        """
        return cls.get(
            presentation_name,
            drive=Drive.from_creds(creds),
            slides_service=cls.service_from_creds(creds),
            template=template,
        )

    @classmethod
    def retrieve_from_id(
        cls,
        presentation_id: str,
        /,
        *,
        slides_service: SlidesResource,
    ) -> Self:
        """Retrieve an existing presentation by Drive file ID.

        Parameters
        ----------
        presentation_id : str
            Opaque Drive file ID of the presentation to fetch.
        slides_service : SlidesResource
            Authenticated Slides v1 service client used to perform the
            ``presentations.get`` call.

        Returns
        -------
        Self
            Wrapper around the fetched presentation payload.
        """
        presentation: Presentation = (
            slides_service.presentations()
            .get(
                presentationId=presentation_id,
            )
            .execute()
        )

        return cls(
            presentation,
            slides_service=slides_service,
        )

    @classmethod
    def retrieve_from_name(
        cls,
        presentation_name: str,
        /,
        *,
        drive: Drive,
        slides_service: SlidesResource,
    ) -> Self:
        """Retrieve an existing presentation by Drive file name.

        Parameters
        ----------
        presentation_name : str
            Exact Drive file name to resolve. The lookup is delegated to
            :meth:`mayutils.interfaces.cloud.google.Drive.find_file_id`.
        drive : Drive
            Drive wrapper used to resolve the name to a file ID.
        slides_service : SlidesResource
            Slides v1 service client used once the ID is known.

        Returns
        -------
        Self
            Wrapper around the resolved presentation.

        Raises
        ------
        FileNotFoundError
            Propagated from :meth:`Drive.find_file_id` when no file with
            the given name exists.
        """
        presentation_id: str = drive.find_file_id(
            presentation_name,
        )

        return cls.retrieve_from_id(
            presentation_id,
            slides_service=slides_service,
        )

    @classmethod
    def create_new(
        cls,
        presentation_name: str,
        /,
        *,
        slides_service: SlidesResource,
    ) -> Self:
        """Create a new, empty presentation with the given title.

        The Slides API seeds a new deck with a default title/subtitle
        placeholder; this method removes those placeholders so the first
        slide starts truly empty.

        Parameters
        ----------
        presentation_name : str
            Title assigned to the newly created Drive file.
        slides_service : SlidesResource
            Slides v1 service client used to issue the create call and
            the subsequent placeholder cleanup batch update.

        Returns
        -------
        Self
            Wrapper bound to the new presentation.
        """
        presentation_internal: Presentation = slides_service.presentations().create(body={"title": presentation_name}).execute()

        presentation = cls(
            presentation_internal,
            slides_service=slides_service,
        )

        requests: list[SlidesRequest] = [
            {
                "deleteObject": {"objectId": element["objectId"]},  # pyright: ignore[reportTypedDictNotRequiredAccess]
            }
            for element in presentation.slide(1).get("pageElements", [])
            if element.get("placeholder", None)
        ]

        presentation.update(requests)

        return presentation

    @classmethod
    def create_from_template(
        cls,
        presentation_name: str,
        /,
        *,
        template_name: str,
        drive: Drive,
        slides_service: SlidesResource,
    ) -> Self:
        """Copy a template presentation to a new file with the given name.

        Parameters
        ----------
        presentation_name : str
            Title to assign to the newly copied file.
        template_name : str
            Drive file name of the template to duplicate. Must already exist
            and be readable by the authenticated user.
        drive : Drive
            Drive wrapper used to locate the template by name and execute
            the ``files.copy`` call.
        slides_service : SlidesResource
            Slides v1 service client stored on the resulting wrapper for
            subsequent mutations.

        Returns
        -------
        Self
            Wrapper bound to the newly created copy of the template.
        """
        template_id: str = drive.find_file_id(
            template_name,
        )

        copied_file = (
            drive.files()
            .copy(
                fileId=template_id,
                body={
                    "name": presentation_name,
                },
            )
            .execute()
        )

        return cls.retrieve_from_id(
            copied_file["id"],  # pyright: ignore[reportTypedDictNotRequiredAccess]
            slides_service=slides_service,
        )

    @classmethod
    def get(
        cls,
        presentation_name: str,
        /,
        *,
        drive: Drive,
        slides_service: SlidesResource,
        template: str | None = None,
    ) -> Self:
        """Fetch a presentation by name, creating it on demand if missing.

        Attempts :meth:`retrieve_from_name` first. If the lookup fails with
        :class:`FileNotFoundError` and ``template`` is ``None`` a blank
        presentation is created via :meth:`create_new`; otherwise the named
        template is copied via :meth:`create_from_template`.

        Parameters
        ----------
        presentation_name : str
            Drive file name that identifies (or will identify) the target
            presentation.
        drive : Drive
            Drive wrapper used to resolve names and perform copy operations.
        slides_service : SlidesResource
            Slides v1 service client used for creation and subsequent
            mutations.
        template : str | None, default None
            Optional Drive name of a template presentation to copy when the
            target does not yet exist.

        Returns
        -------
        Self
            Wrapper around the retrieved or newly provisioned presentation.
        """
        try:
            return cls.retrieve_from_name(
                presentation_name,
                drive=drive,
                slides_service=slides_service,
            )

        except FileNotFoundError:
            if template is None:
                return cls.create_new(
                    presentation_name,
                    slides_service=slides_service,
                )
            return cls.create_from_template(
                presentation_name,
                template_name=template,
                drive=drive,
                slides_service=slides_service,
            )

    def reset(
        self,
        drive: Drive,
        /,
    ) -> Self:
        """Delete the presentation and recreate it empty under the same name.

        Parameters
        ----------
        drive : Drive
            Drive wrapper used to delete the existing file by ID before a
            new one is provisioned.

        Returns
        -------
        Self
            The same wrapper instance, now pointing at the freshly created
            presentation (``id`` and ``internal`` are updated in place).

        Notes
        -----
        The operation is destructive — any pre-existing content is lost and
        the Drive file ID changes, so any previously shared links stop
        working.
        """
        presentation_name = self.title

        drive.delete_file_by_id(self.id)

        new_presentation = self.create_new(
            presentation_name,
            slides_service=self.service,
        )

        self.internal = new_presentation.internal
        self.id = new_presentation.id

        return self

    # TODO(@mayurankv): New slide: Include optional insertion position and optional slide id else `uuid uuid.uuid4().hex`  # noqa: TD003

    def copy_slide(
        self,
        *,
        slide_number: int | None = None,
        to_position: int | None = None,
    ) -> Self:
        """Duplicate an existing slide, optionally inserting at a position.

        Parameters
        ----------
        slide_number : int | None, default None
            1-based position of the slide to duplicate. When ``None`` the
            last slide is duplicated.
        to_position : int | None, default None
            1-based position at which the copy is inserted. When ``None``
            the copy is appended at the end. Must be ``None`` if
            ``slide_number`` is ``None``.

        Returns
        -------
        Self
            The same wrapper instance after the ``duplicateObject`` call
            has been applied.

        Raises
        ------
        ValueError
            If ``to_position`` is provided without an explicit
            ``slide_number``.
        IndexError
            If either the source or target index falls outside the current
            slide range.
        """
        if to_position is not None and slide_number is None:
            msg = "If 'to_position' is specified, 'slide_number' must also be specified."
            raise ValueError(msg)

        source_index = (len(self.slides) if slide_number is None else slide_number) - 1

        if source_index < 0 or source_index >= len(self.slides):
            msg = f"Slide number {source_index + 1} is out of range. Presentation has {len(self.slides)} slides."
            raise IndexError(msg)

        target_index = len(self.slides) if to_position is None else to_position - 1

        if target_index < 0 or target_index > len(self.slides):
            msg = f"Target position {target_index + 1} is out of range. Presentation has {len(self.slides)} slides."
            raise IndexError(msg)

        slide_id = self.slide_id(source_index + 1)

        requests: list[SlidesRequest] = [  # ty:ignore[invalid-assignment]
            {
                "duplicateObject": {
                    "objectId": slide_id,
                    "insertionIndex": target_index,  # pyright: ignore[reportAssignmentType]  # ty:ignore[invalid-key]
                },
            },
        ]

        self.update(requests)

        return self

    def delete_slide(
        self,
        slide_number: int,
        /,
    ) -> Self:
        """Delete the slide at the given 1-based position.

        Parameters
        ----------
        slide_number : int
            1-based position of the slide to remove.

        Returns
        -------
        Self
            The same wrapper instance after the ``deleteObject`` request
            has been issued.

        Raises
        ------
        ValueError
            If the presentation contains only a single slide (the Slides
            API forbids deleting every page) or the slide has no
            ``objectId``.
        IndexError
            If ``slide_number`` is outside the current slide range.
        """
        if len(self.slides) == 1:
            msg = "Cannot delete the only slide in the presentation."
            raise ValueError(msg)

        if slide_number < 1 or slide_number > len(self.slides):
            msg = f"Slide number {slide_number} is out of range. Presentation has {len(self.slides)} slides."
            raise IndexError(msg)

        slide_id = self.slide_id(slide_number)

        requests: list[SlidesRequest] = [
            {
                "deleteObject": {
                    "objectId": slide_id,
                },
            },
        ]

        self.update(requests)

        return self

    def move_slide(
        self,
        slide_number: int,
        /,
        *,
        to_position: int,
    ) -> Self:
        """Move a slide to a new 1-based position.

        Implemented as a copy-then-delete: the source slide is first
        duplicated into ``to_position`` and the original is then removed.

        Parameters
        ----------
        slide_number : int
            1-based position of the slide to move.
        to_position : int
            1-based target position for the slide.

        Returns
        -------
        Self
            The same wrapper instance after the move has been applied.

        Raises
        ------
        ValueError
            If ``slide_number`` equals ``to_position`` (no-op).
        """
        if slide_number == to_position:
            msg = "Slide number and target position cannot be the same."
            raise ValueError(msg)

        self.copy_slide(
            slide_number=slide_number,
            to_position=to_position,
        )
        self.delete_slide(slide_number)

        return self

    def insert_text(  # noqa: C901
        self,
        text: str,
        /,
        *,
        slide_number: int | None = None,
        height: float | None = None,
        width: float | None = None,
        x_shift: float | None = None,
        y_shift: float | None = None,
        element_id: str = uuid.uuid4().hex,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        strikethrough: bool = False,
        font_size: int | None = None,
        font_family: str | None = None,
        colour: Colour | str | None = None,
        background_colour: Colour | str | None = None,
        link: str | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        """Insert a styled text box onto a slide.

        The method creates a ``TEXT_BOX`` shape, inserts the supplied text
        and applies a single text style covering every character, issuing
        all of this as one ``batchUpdate``.

        Parameters
        ----------
        text : str
            String content to place inside the new text box.
        slide_number : int | None, default None
            1-based slide index the text box is added to. When ``None`` the
            last slide is targeted.
        height : float | None, default None
            Text box height in points. Defaults to 90% of the slide height.
        width : float | None, default None
            Text box width in points. Defaults to 90% of the slide width.
        x_shift : float | None, default None
            Horizontal offset from the slide's top-left corner in points.
            Defaults to 5% of the slide width.
        y_shift : float | None, default None
            Vertical offset from the slide's top-left corner in points.
            Defaults to 5% of the slide height.
        element_id : str, default uuid.uuid4().hex
            Client-assigned Slides ``objectId`` for the new shape. Must be
            unique within the presentation; defaults to a fresh UUID4 hex
            string evaluated when the module is imported, so callers should
            usually pass an explicit value if inserting multiple text boxes.
        bold : bool, default False
            Whether the text is rendered bold.
        italic : bool, default False
            Whether the text is rendered italic.
        underline : bool, default False
            Whether the text is underlined.
        strikethrough : bool, default False
            Whether the text is struck through.
        font_size : int | None, default None
            Font size in points. ``None`` leaves the Slides default.
        font_family : str | None, default None
            Font family name recognised by Google Slides (e.g. ``"Arial"``).
        colour : Colour | str | None, default None
            Foreground text colour. Accepts a :class:`Colour` instance, any
            string supported by :meth:`Colour.parse`, or a string prefixed
            ``"theme-"`` (e.g. ``"theme-ACCENT1"``) to reference a theme
            colour.
        background_colour : Colour | str | None, default None
            Text background fill colour. Same input conventions as
            ``colour``.
        link : str | None, default None
            Optional URL to turn the entire text run into a hyperlink.
        **kwargs
            Additional entries merged verbatim into the ``updateTextStyle``
            ``style`` dict, allowing advanced styles not otherwise exposed.

        Returns
        -------
        Self
            The same wrapper instance after the batch update has been
            submitted.

        Raises
        ------
        IndexError
            If ``slide_number`` is outside the current slide range.
        """
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
                parsed_colour = Colour.parse(colour)
        if background_colour is not None and not isinstance(background_colour, Colour):
            if background_colour.startswith("theme-"):
                theme_background_color = background_colour[len("theme-") :]
            else:
                parsed_background_colour = Colour.parse(background_colour)

        if slide_number is None:
            slide_number = len(self.slides)
        elif slide_number < 1 or slide_number > len(self.slides):
            msg = f"Slide number {slide_number} is out of range. Presentation has {len(self.slides)} slides."
            raise IndexError(msg)

        requests: list[SlidesRequest] = cast(
            "list[SlidesRequest]",
            [
                {
                    "createShape": {
                        "objectId": element_id,
                        "shapeType": "TEXT_BOX",
                        "elementProperties": {
                            "pageObjectId": self.slide_id(slide_number),
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
                            **({"fontSize": {"magnitude": font_size, "unit": "PT"}} if font_size is not None else {}),
                            "bold": bold,
                            "italic": italic,
                            "underline": underline,
                            "strikethrough": strikethrough,
                            **(
                                {
                                    "foregroundColor": (
                                        {
                                            "opaqueColor": {
                                                "rgbColor": {
                                                    "red": parsed_colour.r / 255,
                                                    "green": parsed_colour.g / 255,
                                                    "blue": parsed_colour.b / 255,
                                                }
                                            }
                                        }
                                        if not (isinstance(colour, str) and colour.startswith("theme-"))
                                        else {"themeColor": theme_color}
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
                                                    "green": parsed_background_colour.g / 255,
                                                    "blue": parsed_background_colour.b / 255,
                                                }
                                            }
                                        }
                                        if not (isinstance(background_colour, str) and background_colour.startswith("theme-"))
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
            ],
        )

        return self.update(requests)

    def insert_image(  # noqa: C901
        self,
        image_path: Path | str,
        /,
        *,
        slide_number: int | None = None,
        height: float | None = None,
        width: float | None = None,
        x_shift: float | None = None,
        y_shift: float | None = None,
        element_id: str = uuid.uuid4().hex,
        drive: Drive | None = None,
        force_upload: bool = False,
    ) -> Self:
        """Insert an image onto a slide, uploading to Drive when necessary.

        Small images (encoded data URL ``<= 2000`` characters) are embedded
        directly. Larger images must be uploaded to Drive first so the API
        can fetch them by URL; the method resolves a thumbnail URL from
        Drive metadata in that case.

        Parameters
        ----------
        image_path : Path | str
            Filesystem path to a readable image file. Strings are coerced
            to :class:`pathlib.Path`.
        slide_number : int | None, default None
            1-based slide index the image is placed on. Defaults to the
            last slide.
        height : float | None, default None
            Image frame height in points. Defaults to 90% of the slide
            height.
        width : float | None, default None
            Image frame width in points. Defaults to 90% of the slide
            width.
        x_shift : float | None, default None
            Horizontal offset of the frame from the slide's top-left in
            points. Defaults to 5% of the slide width.
        y_shift : float | None, default None
            Vertical offset of the frame from the slide's top-left in
            points. Defaults to 5% of the slide height.
        element_id : str, default uuid.uuid4().hex
            Client-assigned Slides ``objectId`` for the new image. Must be
            unique within the presentation; defaults to a UUID4 hex
            evaluated at import time — pass an explicit value when
            inserting multiple images in the same session.
        drive : Drive | None, default None
            Drive wrapper used to upload oversized images. Required when
            the encoded data URL exceeds the 2 KB inline limit.
        force_upload : bool, default False
            When ``True``, force a re-upload through
            :meth:`Drive.get` even if the file is already present on Drive.

        Returns
        -------
        Self
            The same wrapper instance after the ``createImage`` request has
            been submitted.

        Raises
        ------
        FileNotFoundError
            If ``image_path`` does not exist on disk.
        IndexError
            If ``slide_number`` is outside the current slide range.
        ValueError
            If the MIME type of ``image_path`` cannot be guessed, if a
            large image is passed without a ``drive`` instance, if Drive
            fails to generate a thumbnail for the uploaded asset, or if
            the upload itself fails (the underlying error is chained).
        """
        image_path = Path(image_path)

        if not image_path.exists():
            msg = f"Image file not found: {image_path}"
            raise FileNotFoundError(msg)

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
            msg = f"Slide number {slide_number} is out of range. Presentation has {len(self.slides)} slides."
            raise IndexError(msg)

        mimetype = mimetypes.guess_type(url=image_path)[0]
        if not mimetype:
            msg = f"Could not determine mime type for {image_path}"
            raise ValueError(msg)

        image_data = b64encode(image_path.read_bytes()).decode()
        data_url = f"data:{mimetype};base64,{image_data}"

        def get_file_thumbnail(
            drive: Drive,
            /,
        ) -> str:
            uploaded_file_id = drive.get(
                image_path,
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
                msg = "Could not generate thumbnail for image"
                raise ValueError(msg)

            return file_data["thumbnailLink"]

        if len(data_url) <= 2000:  # noqa: PLR2004 # Direct insertion if under 2KB
            image_url = data_url
        else:
            if drive is None:
                msg = "Drive instance required for large images"
                raise ValueError(msg)

            try:
                image_url = get_file_thumbnail(drive)

            except Exception as err:
                msg = f"Failed to upload image to Drive: {err}"
                raise ValueError(msg) from err

        requests: list[SlidesRequest] = [
            {
                "createImage": {
                    "objectId": element_id,
                    "url": image_url,
                    "elementProperties": {
                        "pageObjectId": self.slide_id(slide_number),
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

        return self.update(requests)
