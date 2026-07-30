"""
Wrap the Google Slides REST API as an ergonomic Python object.

Provide the :class:`Slides` helper which pairs a decoded Google Slides REST
response dictionary with a live ``googleapiclient`` service, exposing CRUD
operations over slides (create, duplicate, delete, move) and convenience
insertion helpers for styled text boxes and images. The wrapper maintains the
decoded presentation payload locally and re-issues ``batchUpdate`` requests
through the shared service, and composes with
:class:`mayutils.interfaces.cloud.google.Drive` to locate templates, upload
large image assets that exceed the inline data URL size limit, and resolve
presentations by name rather than ID.

See Also
--------
mayutils.interfaces.cloud.google.Drive : Drive wrapper used for file lookup and uploads.
mayutils.objects.colours.Colour : Colour parsing helper used by text insertion.
googleapiclient.discovery.build : Underlying service factory for Slides v1.

Examples
--------
>>> from unittest.mock import MagicMock, patch
>>> from mayutils.interfaces.filetypes.slides import Slides
>>> with patch("mayutils.interfaces.filetypes.slides.Drive"):
...     with patch("googleapiclient.discovery.build") as mock_build:
...         mock_service = MagicMock()
...         mock_build.return_value = mock_service
...         mock_service.presentations().get().execute.return_value = {
...             "presentationId": "pid",
...             "title": "Quarterly Review",
...             "slides": [{"objectId": "g1"}],
...             "pageSize": {
...                 "width": {"magnitude": 9144000},
...                 "height": {"magnitude": 5143500},
...             },
...         }
...         deck = Slides.fresh_from_creds("Quarterly Review", creds=MagicMock())
>>> isinstance(deck, Slides)
True
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

if TYPE_CHECKING:
    from google.oauth2.credentials import Credentials
    from googleapiclient._apis.slides.v1.resources import SlidesResource  # pyright: ignore[reportMissingModuleSource]
    from googleapiclient._apis.slides.v1.schemas import Page, Presentation  # pyright: ignore[reportMissingModuleSource]
    from googleapiclient._apis.slides.v1.schemas import Request as SlidesRequest  # pyright: ignore[reportMissingModuleSource]

EMU_UNITS_PER_POINT = 12700


class Slides:
    """
    Wrap a Google Slides presentation with ergonomic CRUD helpers.

    Couple a decoded Slides REST payload (``Presentation``) with a live
    ``googleapiclient`` service so that CRUD operations on slides and common
    content insertions (text, images) can be issued without hand-building
    ``batchUpdate`` bodies. Instances cache the presentation payload locally
    and are refreshed implicitly as mutating methods are called. The wrapper
    translates between the EMU units stored on the API payload and the points
    consumed by the public helpers so callers never need to juggle units.

    Parameters
    ----------
    presentation
        Decoded Google Slides REST response describing an existing
        presentation. Provides the Drive file ID, title, page size and the
        ordered list of slides.
    slides_service
        Authenticated ``googleapiclient`` Slides v1 service client used to
        issue ``batchUpdate`` and ``get`` calls against the Slides API.

    Attributes
    ----------
    id
        Drive file ID of the wrapped presentation.
    service
        The underlying Slides v1 service client.
    internal
        The most recently observed REST payload for the presentation.

    See Also
    --------
    mayutils.interfaces.cloud.google.Drive : Drive wrapper used for name-based lookups.
    Slides.get : Factory that resolves or creates a deck by name.
    Slides.retrieve_from_id : Factory that fetches a deck by Drive file ID.

    Examples
    --------
    >>> from unittest.mock import MagicMock
    >>> service = MagicMock()
    >>> service.presentations().get().execute.return_value = {
    ...     "presentationId": "pid",
    ...     "title": "Quarterly Review",
    ...     "slides": [{"objectId": "g1"}],
    ...     "pageSize": {
    ...         "width": {"magnitude": 9144000},
    ...         "height": {"magnitude": 5143500},
    ...     },
    ... }
    >>> deck = Slides.retrieve_from_id("1AbC", slides_service=service)
    >>> isinstance(deck, Slides)
    True
    """

    def __init__(
        self,
        presentation: Presentation,
        /,
        *,
        slides_service: SlidesResource,
    ) -> None:
        """
        Initialise the wrapper from an API payload and service client.

        Capture the supplied ``Presentation`` dict as the local state snapshot
        and persist the authenticated service client for later mutations. The
        Drive file ID is read eagerly from the payload so that subsequent
        ``batchUpdate`` calls can be addressed even if the payload is later
        refreshed.

        Parameters
        ----------
        presentation
            Decoded Slides REST response providing at minimum a
            ``presentationId`` and list of slides; used as the initial
            snapshot of presentation state.
        slides_service
            Authenticated Slides v1 service client used for all subsequent
            API interactions.

        See Also
        --------
        Slides.retrieve_from_id : Fetch a presentation and construct a wrapper.
        Slides.create_new : Create a fresh deck and wrap the response.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> payload = {
        ...     "presentationId": "pid",
        ...     "title": "Quarterly Review",
        ...     "slides": [{"objectId": "g1"}],
        ...     "pageSize": {
        ...         "width": {"magnitude": 9144000},
        ...         "height": {"magnitude": 5143500},
        ...     },
        ... }
        >>> deck = Slides(payload, slides_service=MagicMock())
        >>> deck.title
        'Quarterly Review'
        """
        self.id: str = presentation["presentationId"]  # pyright: ignore[reportTypedDictNotRequiredAccess]
        self.service: SlidesResource = slides_service
        self.internal: Presentation = presentation

    @property
    def _internal_slides(
        self,
    ) -> list[Page]:
        """
        Return the raw ``slides`` list from the presentation payload.

        Expose the underlying ``slides`` array of the decoded REST payload
        without copying so that private helpers can index into it directly.
        Callers should not mutate the returned list — it is the live state
        cache used by the wrapper.

        Returns
        -------
            Ordered list of ``Page`` dicts straight from the Slides REST
            payload.

        See Also
        --------
        Slides.slides : Public list-of-pages accessor used by callers.
        Slides.slide : Retrieve a single page by 1-based position.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> deck = Slides(
        ...     {
        ...         "presentationId": "pid",
        ...         "title": "t",
        ...         "slides": [{"objectId": "g1"}],
        ...         "pageSize": {
        ...             "width": {"magnitude": 9144000},
        ...             "height": {"magnitude": 5143500},
        ...         },
        ...     },
        ...     slides_service=MagicMock(),
        ... )
        >>> deck._internal_slides[0]["objectId"]
        'g1'
        """
        return self.internal["slides"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def height(
        self,
    ) -> float:
        """
        Report the slide height in typographic points.

        The underlying Slides API reports dimensions in English Metric Units
        (EMU); the value is converted to points (1 pt = 12 700 EMU) to match
        the units accepted by insertion helpers such as :meth:`insert_text`
        and :meth:`insert_image`. The value is read from the cached payload
        and therefore reflects the last known state of the deck.

        Returns
        -------
            Slide height in points.

        See Also
        --------
        Slides.width : Sibling accessor returning the slide width in points.
        Slides.insert_text : Consumer of point-based height defaults.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> deck = Slides(
        ...     {
        ...         "presentationId": "pid",
        ...         "title": "t",
        ...         "slides": [{"objectId": "g1"}],
        ...         "pageSize": {
        ...             "width": {"magnitude": 9144000},
        ...             "height": {"magnitude": 5143500},
        ...         },
        ...     },
        ...     slides_service=MagicMock(),
        ... )
        >>> deck.height
        405.0
        """
        return self.internal["pageSize"]["height"]["magnitude"] / EMU_UNITS_PER_POINT  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def width(
        self,
    ) -> float:
        """
        Report the slide width in typographic points.

        Convert the EMU value reported by the Slides API to points, enabling
        direct use as ``width``/``x_shift`` arguments to the insertion
        helpers. The reading is derived from the locally cached payload so it
        reflects whatever size the last ``get`` returned.

        Returns
        -------
            Slide width in points.

        See Also
        --------
        Slides.height : Sibling accessor returning the slide height in points.
        Slides.insert_image : Consumer of point-based width defaults.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> deck = Slides(
        ...     {
        ...         "presentationId": "pid",
        ...         "title": "t",
        ...         "slides": [{"objectId": "g1"}],
        ...         "pageSize": {
        ...             "width": {"magnitude": 9144000},
        ...             "height": {"magnitude": 5143500},
        ...         },
        ...     },
        ...     slides_service=MagicMock(),
        ... )
        >>> deck.width
        720.0
        """
        return self.internal["pageSize"]["width"]["magnitude"] / EMU_UNITS_PER_POINT  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def link(
        self,
    ) -> str:
        """
        Build the web editor URL for the presentation.

        Concatenate the standard Google Slides editor prefix with the Drive
        file ID captured at construction so that the resulting URL opens the
        presentation in the web editor. The URL is stable for the lifetime of
        the Drive file and updates to :attr:`id` (e.g. after :meth:`reset`)
        are reflected automatically.

        Returns
        -------
            Fully qualified ``docs.google.com`` URL that opens the
            presentation in the Google Slides web editor.

        See Also
        --------
        Slides.open : Open the URL in the system default web browser.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> deck = Slides(
        ...     {
        ...         "presentationId": "1AbC",
        ...         "title": "t",
        ...         "slides": [{"objectId": "g1"}],
        ...         "pageSize": {
        ...             "width": {"magnitude": 9144000},
        ...             "height": {"magnitude": 5143500},
        ...         },
        ...     },
        ...     slides_service=MagicMock(),
        ... )
        >>> deck.link
        'https://docs.google.com/presentation/d/1AbC/edit'
        """
        return f"https://docs.google.com/presentation/d/{self.id}/edit"

    def slide(
        self,
        slide_number: int,
        /,
    ) -> Page:
        """
        Return the raw payload for a single slide by 1-indexed position.

        Translate the 1-based ``slide_number`` argument into the 0-based
        position used internally and return the corresponding ``Page`` dict.
        The raw payload is returned so callers can introspect or patch it if
        needed without another round-trip to the API.

        Parameters
        ----------
        slide_number
            1-based position of the slide within the presentation. ``1``
            refers to the first slide in reading order.

        Returns
        -------
            The Slides REST payload fragment describing the requested page,
            including ``objectId`` and ``pageElements``.

        Raises
        ------
        IndexError
            If ``slide_number`` is less than ``1`` or exceeds the number of
            slides currently held in :attr:`internal`.

        See Also
        --------
        Slides.slide_id : Convenience accessor for the ``objectId`` field.
        Slides.slides : Full list of slide payloads.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> deck = Slides(
        ...     {
        ...         "presentationId": "pid",
        ...         "title": "t",
        ...         "slides": [{"objectId": "g1"}],
        ...         "pageSize": {
        ...             "width": {"magnitude": 9144000},
        ...             "height": {"magnitude": 5143500},
        ...         },
        ...     },
        ...     slides_service=MagicMock(),
        ... )
        >>> first = deck.slide(1)
        >>> first["objectId"]
        'g1'
        """
        if slide_number < 1 or slide_number > len(self._internal_slides):
            msg = f"Slide number {slide_number} is out of range. Presentation has {len(self._internal_slides)} slides."
            raise IndexError(msg)

        return self._internal_slides[slide_number - 1]

    @property
    def slides(
        self,
    ) -> list[Page]:
        """
        Return every slide payload in presentation order.

        Iterate the cached payload and delegate to :meth:`slide` so the
        public accessor enforces the same bounds semantics as direct lookups.
        The returned list is newly allocated on each access, so callers may
        mutate it without affecting the wrapper's internal state.

        Returns
        -------
            Ordered list of per-slide REST payloads mirroring the order
            users see in the web editor.

        See Also
        --------
        Slides.slide : Access a single slide by 1-based position.
        Slides._internal_slides : Live cached list backing this accessor.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> deck = Slides(
        ...     {
        ...         "presentationId": "pid",
        ...         "title": "t",
        ...         "slides": [
        ...             {"objectId": "g1"},
        ...             {"objectId": "g2"},
        ...             {"objectId": "g3"},
        ...             {"objectId": "g4"},
        ...         ],
        ...         "pageSize": {
        ...             "width": {"magnitude": 9144000},
        ...             "height": {"magnitude": 5143500},
        ...         },
        ...     },
        ...     slides_service=MagicMock(),
        ... )
        >>> len(deck.slides)
        4
        """
        return [self.slide(slide_idx + 1) for slide_idx in range(len(self._internal_slides))]

    def slide_id(
        self,
        slide_number: int,
        /,
    ) -> str:
        """
        Return the Google-assigned ``objectId`` for a slide.

        Look up the raw ``Page`` payload via :meth:`slide` and return the
        opaque identifier Google uses to address the page in subsequent
        ``batchUpdate`` calls. This is the canonical input for the
        ``pageObjectId`` field in most Slides API request objects.

        Parameters
        ----------
        slide_number
            1-based position of the slide whose identifier is required.

        Returns
        -------
            Opaque Slides ``objectId`` string suitable as
            ``pageObjectId`` when building ``batchUpdate`` requests.

        See Also
        --------
        Slides.slide : Fetch the full payload for the slide.

        Notes
        -----
        Bubbles up :class:`IndexError` from :meth:`slide` when
        ``slide_number`` falls outside the current slide range.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> deck = Slides(
        ...     {
        ...         "presentationId": "pid",
        ...         "title": "t",
        ...         "slides": [{"objectId": "g1"}],
        ...         "pageSize": {
        ...             "width": {"magnitude": 9144000},
        ...             "height": {"magnitude": 5143500},
        ...         },
        ...     },
        ...     slides_service=MagicMock(),
        ... )
        >>> deck.slide_id(1)
        'g1'
        """
        return self.slide(slide_number)["objectId"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def title(
        self,
    ) -> str:
        """
        Report the presentation title as stored on Drive.

        Return the ``title`` field of the cached Slides REST payload which
        mirrors the Drive file name. The value reflects the last observed
        state of the deck — renames performed outside this wrapper are not
        surfaced until the next ``get`` refresh.

        Returns
        -------
            Drive file title taken from the ``title`` field of the Slides
            REST payload.

        See Also
        --------
        Slides.link : Web editor URL derived from the file ID.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> deck = Slides(
        ...     {
        ...         "presentationId": "pid",
        ...         "title": "Quarterly Review",
        ...         "slides": [{"objectId": "g1"}],
        ...         "pageSize": {
        ...             "width": {"magnitude": 9144000},
        ...             "height": {"magnitude": 5143500},
        ...         },
        ...     },
        ...     slides_service=MagicMock(),
        ... )
        >>> deck.title
        'Quarterly Review'
        """
        return self.internal["title"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    def open(
        self,
    ) -> None:
        """
        Open the presentation in the system default web browser.

        Delegate to :func:`webbrowser.open` against :attr:`link`; the call is
        fire-and-forget and returns even if no browser is available. Used
        interactively to inspect mutations after running a workflow.

        See Also
        --------
        Slides.link : URL that is handed to :mod:`webbrowser`.
        webbrowser.open : Underlying standard-library entry point.

        Examples
        --------
        >>> from unittest.mock import MagicMock, patch
        >>> deck = Slides(
        ...     {
        ...         "presentationId": "pid",
        ...         "title": "t",
        ...         "slides": [{"objectId": "g1"}],
        ...         "pageSize": {
        ...             "width": {"magnitude": 9144000},
        ...             "height": {"magnitude": 5143500},
        ...         },
        ...     },
        ...     slides_service=MagicMock(),
        ... )
        >>> with patch("webbrowser.open") as mock_open:
        ...     deck.open()
        >>> mock_open.called
        True
        """
        webbrowser.open(url=self.link)

    def get_thumbnail_url(
        self,
        slide_number: int,
    ) -> str:
        """
        Fetch a rendered thumbnail URL for a single slide.

        Resolve the requested slide to its ``objectId`` and call the Slides
        ``pages.getThumbnail`` endpoint to produce a short-lived, signed
        image URL. The URL is served from Google's thumbnail infrastructure
        and typically expires after several minutes.

        Parameters
        ----------
        slide_number
            1-based position of the slide to render.

        Returns
        -------
            Short-lived, authenticated ``contentUrl`` returned by the Slides
            ``pages.getThumbnail`` endpoint, suitable for embedding in
            ``<img>`` tags or IPython display widgets.

        See Also
        --------
        Slides.display : Render a slide inline in an IPython frontend.
        Slides._repr_mimebundle_ : Uses the thumbnail for rich Jupyter display.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> service = MagicMock()
        >>> service.presentations().pages().getThumbnail().execute.return_value = {
        ...     "contentUrl": "https://example.com/thumb.png",
        ... }
        >>> deck = Slides(
        ...     {
        ...         "presentationId": "pid",
        ...         "title": "t",
        ...         "slides": [{"objectId": "g1"}],
        ...         "pageSize": {
        ...             "width": {"magnitude": 9144000},
        ...             "height": {"magnitude": 5143500},
        ...         },
        ...     },
        ...     slides_service=service,
        ... )
        >>> url = deck.get_thumbnail_url(1)
        >>> url.startswith("https://")
        True
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
        """
        Render a slide (or the full deck) inline in an IPython frontend.

        Fetch a thumbnail URL via :meth:`get_thumbnail_url` and hand it to
        :class:`IPython.core.display.Image` for rendering. When ``slide_number``
        is ``None`` the method recursively renders every slide in order.
        If IPython is not importable the function silently returns, so it is
        safe to invoke from non-notebook contexts.

        Parameters
        ----------
        slide_number
            1-based slide index to render. When ``None`` every slide in the
            deck is rendered sequentially via recursive calls.
        **kwargs
            Additional keyword arguments forwarded to
            :class:`IPython.core.display.Image` (e.g. ``width``, ``height``)
            for per-slide display customisation.

        See Also
        --------
        Slides.get_thumbnail_url : Source of the rendered image URL.
        IPython.core.display.Image : Widget used for inline rendering.

        Examples
        --------
        >>> from unittest.mock import MagicMock, patch
        >>> service = MagicMock()
        >>> service.presentations().pages().getThumbnail().execute.return_value = {
        ...     "contentUrl": "https://example.com/thumb.png",
        ... }
        >>> deck = Slides(
        ...     {
        ...         "presentationId": "pid",
        ...         "title": "t",
        ...         "slides": [{"objectId": "g1"}],
        ...         "pageSize": {
        ...             "width": {"magnitude": 9144000},
        ...             "height": {"magnitude": 5143500},
        ...         },
        ...     },
        ...     slides_service=service,
        ... )
        >>> with patch("IPython.display.display") as mock_display:
        ...     deck.display(slide_number=1, width=480)
        >>> mock_display.called
        True
        """
        if slide_number is not None:
            url = self.get_thumbnail_url(slide_number=slide_number)

            try:
                from IPython.core.display import Image
                from IPython.display import display  # pyright: ignore[reportUnknownVariableType]

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
        """
        Provide a MIME bundle rendering for Jupyter rich display.

        Implement the Jupyter rich-display protocol so that evaluating a
        :class:`Slides` instance as the final expression in a cell previews
        the first slide. The returned mapping contains a single ``text/html``
        entry wrapping the thumbnail URL in an ``<img>`` tag sized to the
        container width.

        Parameters
        ----------
        include
            MIME types the frontend has requested; accepted for interface
            compatibility but not consulted.
        exclude
            MIME types the frontend wishes to exclude; accepted for
            interface compatibility but not consulted.

        Returns
        -------
            Mapping from MIME type to payload. Currently emits a single
            ``text/html`` entry showing the first slide's thumbnail at
            responsive width.

        See Also
        --------
        Slides.display : Explicit inline rendering helper.
        Slides.get_thumbnail_url : Source of the embedded thumbnail URL.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> service = MagicMock()
        >>> service.presentations().pages().getThumbnail().execute.return_value = {
        ...     "contentUrl": "https://example.com/thumb.png",
        ... }
        >>> deck = Slides(
        ...     {
        ...         "presentationId": "pid",
        ...         "title": "t",
        ...         "slides": [{"objectId": "g1"}],
        ...         "pageSize": {
        ...             "width": {"magnitude": 9144000},
        ...             "height": {"magnitude": 5143500},
        ...         },
        ...     },
        ...     slides_service=service,
        ... )
        >>> bundle = deck._repr_mimebundle_()
        >>> "text/html" in bundle
        True
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
        """
        Submit raw ``batchUpdate`` requests and return self for chaining.

        Forward the supplied list of Slides request objects to
        ``presentations.batchUpdate`` in a single API call when the list is
        non-empty. Atomicity and ordering guarantees follow Google's
        documented semantics for that endpoint; an empty list is a no-op
        that still returns ``self`` to preserve fluent chaining.

        Parameters
        ----------
        requests
            Sequence of Slides ``batchUpdate`` request objects (for example
            ``{"createShape": {...}}``). An empty list is a no-op.

        Returns
        -------
            The same wrapper instance, enabling fluent chaining of
            mutation calls.

        See Also
        --------
        Slides.insert_text : Builds and submits ``createShape`` requests.
        Slides.insert_image : Builds and submits ``createImage`` requests.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> service = MagicMock()
        >>> deck = Slides(
        ...     {
        ...         "presentationId": "pid",
        ...         "title": "t",
        ...         "slides": [{"objectId": "g1"}],
        ...         "pageSize": {
        ...             "width": {"magnitude": 9144000},
        ...             "height": {"magnitude": 5143500},
        ...         },
        ...     },
        ...     slides_service=service,
        ... )
        >>> result = deck.update([{"deleteObject": {"objectId": "g123"}}])
        >>> result is deck
        True
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
        """
        Build a Slides v1 service client from OAuth credentials.

        Wrap the ``googleapiclient.discovery.build`` helper with the
        Slides-specific service name and version so callers can obtain a
        ready-to-use service client from an authorised credentials object
        without duplicating the boilerplate. The returned object is suitable
        for direct use as ``slides_service`` in the other factories.

        Parameters
        ----------
        creds
            Authorised ``google.oauth2.credentials.Credentials`` object
            carrying the scopes necessary for Slides read/write access.

        Returns
        -------
            A ready-to-use ``googleapiclient`` discovery service pinned to
            the Slides v1 API.

        See Also
        --------
        Slides.fresh_from_creds : Higher-level helper that also builds the Drive client.
        googleapiclient.discovery.build : Underlying service factory.

        Examples
        --------
        >>> from unittest.mock import MagicMock, patch
        >>> with patch("googleapiclient.discovery.build") as mock_build:
        ...     mock_build.return_value = MagicMock()
        ...     service = Slides.service_from_creds(MagicMock())
        >>> mock_build.called
        True
        """
        with may_require_extras():
            from googleapiclient.discovery import build  # pyright: ignore[reportUnknownVariableType]

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
        """
        Resolve (or create) a presentation by name using raw credentials.

        Construct both the Drive wrapper and the Slides service client from a
        single set of OAuth credentials and delegate to :meth:`get` to either
        resolve an existing deck by name or provision a new one. When a
        template name is supplied and no matching deck exists, the template
        is duplicated instead of a blank file being created.

        Parameters
        ----------
        presentation_name
            Drive file name to look up. If no such file exists a new
            presentation is created with this title.
        creds
            OAuth credentials used to build both the Drive client (for
            name resolution) and the Slides service client.
        template
            Optional Drive file name of a template presentation. When
            provided and no existing presentation matches
            ``presentation_name``, the template is copied rather than a
            blank deck being created.

        Returns
        -------
            Wrapper bound to the resolved or freshly created presentation.

        See Also
        --------
        Slides.get : Underlying resolve-or-create routine.
        Slides.service_from_creds : Builds the Slides service used here.
        mayutils.interfaces.cloud.google.Drive.from_creds : Builds the Drive client.

        Examples
        --------
        >>> from unittest.mock import MagicMock, patch
        >>> with patch("mayutils.interfaces.filetypes.slides.Drive"):
        ...     with patch("googleapiclient.discovery.build") as mock_build:
        ...         mock_service = MagicMock()
        ...         mock_build.return_value = mock_service
        ...         mock_service.presentations().get().execute.return_value = {
        ...             "presentationId": "pid",
        ...             "title": "Quarterly Review",
        ...             "slides": [{"objectId": "g1"}],
        ...             "pageSize": {
        ...                 "width": {"magnitude": 9144000},
        ...                 "height": {"magnitude": 5143500},
        ...             },
        ...         }
        ...         deck = Slides.fresh_from_creds("Quarterly Review", creds=MagicMock())
        >>> isinstance(deck, Slides)
        True
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
        """
        Retrieve an existing presentation by Drive file ID.

        Issue a ``presentations.get`` against the supplied service client to
        pull the full REST payload for the requested file and wrap it in a
        new :class:`Slides` instance. This is the lowest-level factory and
        is the building block used by :meth:`retrieve_from_name` and
        :meth:`create_from_template`.

        Parameters
        ----------
        presentation_id
            Opaque Drive file ID of the presentation to fetch.
        slides_service
            Authenticated Slides v1 service client used to perform the
            ``presentations.get`` call.

        Returns
        -------
            Wrapper around the fetched presentation payload.

        See Also
        --------
        Slides.retrieve_from_name : Resolve a deck from its Drive file name.
        Slides.get : Resolve-or-create helper built on this method.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> service = MagicMock()
        >>> service.presentations().get().execute.return_value = {
        ...     "presentationId": "pid",
        ...     "title": "t",
        ...     "slides": [{"objectId": "g1"}],
        ...     "pageSize": {
        ...         "width": {"magnitude": 9144000},
        ...         "height": {"magnitude": 5143500},
        ...     },
        ... }
        >>> deck = Slides.retrieve_from_id("1AbC", slides_service=service)
        >>> isinstance(deck, Slides)
        True
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
        """
        Retrieve an existing presentation by Drive file name.

        Delegate to :meth:`Drive.find_file_id` to resolve the requested name
        to a Drive file ID, then pass that ID to :meth:`retrieve_from_id` to
        load the REST payload. The helper is intended for workflows where
        callers prefer human-readable names over opaque IDs.

        Parameters
        ----------
        presentation_name
            Exact Drive file name to resolve. The lookup is delegated to
            :meth:`mayutils.interfaces.cloud.google.Drive.find_file_id`.
        drive
            Drive wrapper used to resolve the name to a file ID.
        slides_service
            Slides v1 service client used once the ID is known.

        Returns
        -------
            Wrapper around the resolved presentation.

        See Also
        --------
        Slides.retrieve_from_id : Lower-level ID-based factory.
        Slides.get : Resolve-or-create helper that swallows ``FileNotFoundError``.

        Notes
        -----
        Bubbles up :class:`FileNotFoundError` from
        :meth:`Drive.find_file_id` when no file with the given name
        exists on Drive.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> drive = MagicMock()
        >>> drive.find_file_id.return_value = "pid"
        >>> service = MagicMock()
        >>> service.presentations().get().execute.return_value = {
        ...     "presentationId": "pid",
        ...     "title": "Quarterly Review",
        ...     "slides": [{"objectId": "g1"}],
        ...     "pageSize": {
        ...         "width": {"magnitude": 9144000},
        ...         "height": {"magnitude": 5143500},
        ...     },
        ... }
        >>> deck = Slides.retrieve_from_name(
        ...     "Quarterly Review",
        ...     drive=drive,
        ...     slides_service=service,
        ... )
        >>> isinstance(deck, Slides)
        True
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
        """
        Create a new, empty presentation with the given title.

        Issue a ``presentations.create`` against the Slides service and then
        remove the default title/subtitle placeholders that the API injects
        into the first slide. The resulting deck has a single, empty page
        ready for callers to populate with :meth:`insert_text` or
        :meth:`insert_image`.

        Parameters
        ----------
        presentation_name
            Title assigned to the newly created Drive file.
        slides_service
            Slides v1 service client used to issue the create call and
            the subsequent placeholder cleanup batch update.

        Returns
        -------
            Wrapper bound to the new presentation.

        See Also
        --------
        Slides.create_from_template : Copy a template instead of creating blank.
        Slides.get : Resolve-or-create helper that calls this on cache-miss.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> service = MagicMock()
        >>> service.presentations().create().execute.return_value = {
        ...     "presentationId": "pid",
        ...     "title": "Quarterly Review",
        ...     "slides": [{"objectId": "g1", "pageElements": []}],
        ...     "pageSize": {
        ...         "width": {"magnitude": 9144000},
        ...         "height": {"magnitude": 5143500},
        ...     },
        ... }
        >>> deck = Slides.create_new("Quarterly Review", slides_service=service)
        >>> isinstance(deck, Slides)
        True
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
        """
        Copy a template presentation to a new file with the given name.

        Resolve the template by name via :meth:`Drive.find_file_id`, invoke
        ``files.copy`` on the Drive service, and wrap the resulting file
        with :meth:`retrieve_from_id`. The copy preserves every slide,
        theme, and layout from the template, providing a fast starting
        point for bespoke decks.

        Parameters
        ----------
        presentation_name
            Title to assign to the newly copied file.
        template_name
            Drive file name of the template to duplicate. Must already exist
            and be readable by the authenticated user.
        drive
            Drive wrapper used to locate the template by name and execute
            the ``files.copy`` call.
        slides_service
            Slides v1 service client stored on the resulting wrapper for
            subsequent mutations.

        Returns
        -------
            Wrapper bound to the newly created copy of the template.

        See Also
        --------
        Slides.create_new : Create a blank deck instead of copying a template.
        mayutils.interfaces.cloud.google.Drive.find_file_id : Template name resolution.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> drive = MagicMock()
        >>> drive.find_file_id.return_value = "tpl"
        >>> drive.files().copy().execute.return_value = {"id": "pid"}
        >>> service = MagicMock()
        >>> service.presentations().get().execute.return_value = {
        ...     "presentationId": "pid",
        ...     "title": "Quarterly Review",
        ...     "slides": [{"objectId": "g1"}],
        ...     "pageSize": {
        ...         "width": {"magnitude": 9144000},
        ...         "height": {"magnitude": 5143500},
        ...     },
        ... }
        >>> deck = Slides.create_from_template(
        ...     "Quarterly Review",
        ...     template_name="Quarterly Template",
        ...     drive=drive,
        ...     slides_service=service,
        ... )
        >>> isinstance(deck, Slides)
        True
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
        """
        Fetch a presentation by name, creating it on demand if missing.

        Attempt :meth:`retrieve_from_name` first. If the lookup fails with
        :class:`FileNotFoundError` and ``template`` is ``None`` a blank
        presentation is created via :meth:`create_new`; otherwise the named
        template is copied via :meth:`create_from_template`. This is the
        preferred entry point for idempotent workflows that want to
        refresh an existing deck or bootstrap a new one on first run.

        Parameters
        ----------
        presentation_name
            Drive file name that identifies (or will identify) the target
            presentation.
        drive
            Drive wrapper used to resolve names and perform copy operations.
        slides_service
            Slides v1 service client used for creation and subsequent
            mutations.
        template
            Optional Drive name of a template presentation to copy when the
            target does not yet exist.

        Returns
        -------
            Wrapper around the retrieved or newly provisioned presentation.

        See Also
        --------
        Slides.retrieve_from_name : Name-based lookup attempted first.
        Slides.create_new : Fallback when no template is supplied.
        Slides.create_from_template : Fallback when a template is supplied.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> drive = MagicMock()
        >>> drive.find_file_id.return_value = "pid"
        >>> service = MagicMock()
        >>> service.presentations().get().execute.return_value = {
        ...     "presentationId": "pid",
        ...     "title": "Quarterly Review",
        ...     "slides": [{"objectId": "g1"}],
        ...     "pageSize": {
        ...         "width": {"magnitude": 9144000},
        ...         "height": {"magnitude": 5143500},
        ...     },
        ... }
        >>> deck = Slides.get(
        ...     "Quarterly Review",
        ...     drive=drive,
        ...     slides_service=service,
        ...     template="Quarterly Template",
        ... )
        >>> isinstance(deck, Slides)
        True
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
        """
        Delete the presentation and recreate it empty under the same name.

        Use the supplied Drive wrapper to remove the existing file by ID and
        then call :meth:`create_new` with the original title to provision a
        fresh, empty deck. The wrapper's :attr:`id` and :attr:`internal`
        state are updated in place so callers can continue using the same
        instance. Any previously shared links stop working because a brand
        new Drive file ID is allocated.

        Parameters
        ----------
        drive
            Drive wrapper used to delete the existing file by ID before a
            new one is provisioned.

        Returns
        -------
            The same wrapper instance, now pointing at the freshly created
            presentation (``id`` and ``internal`` are updated in place).

        See Also
        --------
        Slides.create_new : Used to provision the replacement deck.
        mayutils.interfaces.cloud.google.Drive.delete_file_by_id : Used to remove the old file.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> service = MagicMock()
        >>> service.presentations().create().execute.return_value = {
        ...     "presentationId": "new_pid",
        ...     "title": "t",
        ...     "slides": [{"objectId": "g1", "pageElements": []}],
        ...     "pageSize": {
        ...         "width": {"magnitude": 9144000},
        ...         "height": {"magnitude": 5143500},
        ...     },
        ... }
        >>> deck = Slides(
        ...     {
        ...         "presentationId": "old_pid",
        ...         "title": "t",
        ...         "slides": [{"objectId": "g0"}],
        ...         "pageSize": {
        ...             "width": {"magnitude": 9144000},
        ...             "height": {"magnitude": 5143500},
        ...         },
        ...     },
        ...     slides_service=service,
        ... )
        >>> drive = MagicMock()
        >>> _ = deck.reset(drive)
        >>> deck.id
        'new_pid'
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
        """
        Duplicate an existing slide, optionally inserting at a position.

        Resolve both the source index (defaulting to the last slide) and the
        target index (defaulting to the end of the deck) in 0-based space,
        then emit a single ``duplicateObject`` request. The duplicate is
        ordered by ``insertionIndex`` so callers can drop copies anywhere in
        the deck with a predictable layout.

        Parameters
        ----------
        slide_number
            1-based position of the slide to duplicate. When ``None`` the
            last slide is duplicated.
        to_position
            1-based position at which the copy is inserted. When ``None``
            the copy is appended at the end. Must be ``None`` if
            ``slide_number`` is ``None``.

        Returns
        -------
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

        See Also
        --------
        Slides.move_slide : Copy-then-delete helper built on top of this method.
        Slides.delete_slide : Complementary removal operation.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> deck = Slides(
        ...     {
        ...         "presentationId": "pid",
        ...         "title": "t",
        ...         "slides": [
        ...             {"objectId": "g1"},
        ...             {"objectId": "g2"},
        ...             {"objectId": "g3"},
        ...         ],
        ...         "pageSize": {
        ...             "width": {"magnitude": 9144000},
        ...             "height": {"magnitude": 5143500},
        ...         },
        ...     },
        ...     slides_service=MagicMock(),
        ... )
        >>> result = deck.copy_slide(slide_number=1, to_position=3)
        >>> result is deck
        True
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
        """
        Delete the slide at the given 1-based position.

        Guard against attempting to delete the only remaining slide (the
        Slides API rejects the request) and then emit a ``deleteObject``
        targeting the requested page. The presentation payload is refreshed
        implicitly on the next mutation.

        Parameters
        ----------
        slide_number
            1-based position of the slide to remove.

        Returns
        -------
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

        See Also
        --------
        Slides.copy_slide : Complementary duplication operation.
        Slides.move_slide : Copy-then-delete helper built on top of this method.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> deck = Slides(
        ...     {
        ...         "presentationId": "pid",
        ...         "title": "t",
        ...         "slides": [
        ...             {"objectId": "g1"},
        ...             {"objectId": "g2"},
        ...         ],
        ...         "pageSize": {
        ...             "width": {"magnitude": 9144000},
        ...             "height": {"magnitude": 5143500},
        ...         },
        ...     },
        ...     slides_service=MagicMock(),
        ... )
        >>> result = deck.delete_slide(2)
        >>> result is deck
        True
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
        """
        Move a slide to a new 1-based position.

        Implement the move as a copy-then-delete: the source slide is first
        duplicated into ``to_position`` and the original is then removed.
        This sidesteps the Slides API's lack of a dedicated move request and
        keeps the final deck ordering consistent with the requested target
        position.

        Parameters
        ----------
        slide_number
            1-based position of the slide to move.
        to_position
            1-based target position for the slide.

        Returns
        -------
            The same wrapper instance after the move has been applied.

        Raises
        ------
        ValueError
            If ``slide_number`` equals ``to_position`` (no-op).

        See Also
        --------
        Slides.copy_slide : Duplication step of the move.
        Slides.delete_slide : Removal step of the move.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> deck = Slides(
        ...     {
        ...         "presentationId": "pid",
        ...         "title": "t",
        ...         "slides": [
        ...             {"objectId": "g1"},
        ...             {"objectId": "g2"},
        ...             {"objectId": "g3"},
        ...         ],
        ...         "pageSize": {
        ...             "width": {"magnitude": 9144000},
        ...             "height": {"magnitude": 5143500},
        ...         },
        ...     },
        ...     slides_service=MagicMock(),
        ... )
        >>> result = deck.move_slide(1, to_position=3)
        >>> result is deck
        True
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
        """
        Insert a styled text box onto a slide.

        Create a ``TEXT_BOX`` shape, insert the supplied text and apply a
        single text style covering every character, issuing all of this as
        one ``batchUpdate``. Geometry arguments default to a centred 90%
        frame, and colour inputs accept either :class:`Colour` instances,
        hex/named strings, or ``"theme-<NAME>"`` references to the deck's
        theme palette.

        Parameters
        ----------
        text
            String content to place inside the new text box.
        slide_number
            1-based slide index the text box is added to. When ``None`` the
            last slide is targeted.
        height
            Text box height in points. Defaults to 90% of the slide height.
        width
            Text box width in points. Defaults to 90% of the slide width.
        x_shift
            Horizontal offset from the slide's top-left corner in points.
            Defaults to 5% of the slide width.
        y_shift
            Vertical offset from the slide's top-left corner in points.
            Defaults to 5% of the slide height.
        element_id
            Client-assigned Slides ``objectId`` for the new shape. Must be
            unique within the presentation; defaults to a fresh UUID4 hex
            string evaluated when the module is imported, so callers should
            usually pass an explicit value if inserting multiple text boxes.
        bold
            Whether the text is rendered bold.
        italic
            Whether the text is rendered italic.
        underline
            Whether the text is underlined.
        strikethrough
            Whether the text is struck through.
        font_size
            Font size in points. ``None`` leaves the Slides default.
        font_family
            Font family name recognised by Google Slides (e.g. ``"Arial"``).
        colour
            Foreground text colour. Accepts a :class:`Colour` instance, any
            string supported by :meth:`Colour.parse`, or a string prefixed
            ``"theme-"`` (e.g. ``"theme-ACCENT1"``) to reference a theme
            colour.
        background_colour
            Text background fill colour. Same input conventions as
            ``colour``.
        link
            Optional URL to turn the entire text run into a hyperlink.
        **kwargs
            Additional entries merged verbatim into the ``updateTextStyle``
            ``style`` dict, allowing advanced styles not otherwise exposed.

        Returns
        -------
            The same wrapper instance after the batch update has been
            submitted.

        Raises
        ------
        IndexError
            If ``slide_number`` is outside the current slide range.

        See Also
        --------
        Slides.insert_image : Sibling helper for image insertion.
        mayutils.objects.colours.Colour : Colour input parser.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> deck = Slides(
        ...     {
        ...         "presentationId": "pid",
        ...         "title": "t",
        ...         "slides": [{"objectId": "g1"}],
        ...         "pageSize": {
        ...             "width": {"magnitude": 9144000},
        ...             "height": {"magnitude": 5143500},
        ...         },
        ...     },
        ...     slides_service=MagicMock(),
        ... )
        >>> result = deck.insert_text(
        ...     "Quarterly Summary",
        ...     bold=True,
        ...     font_size=24,
        ...     colour="theme-ACCENT1",
        ... )
        >>> result is deck
        True
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
        r"""
        Insert an image onto a slide, uploading to Drive when necessary.

        Small images (encoded data URL ``<= 2000`` characters) are embedded
        directly. Larger images must be uploaded to Drive first so the API
        can fetch them by URL; the method resolves a thumbnail URL from
        Drive metadata in that case. Frame geometry defaults mirror the
        centred 90% layout used by :meth:`insert_text`.

        Parameters
        ----------
        image_path
            Filesystem path to a readable image file. Strings are coerced
            to :class:`pathlib.Path`.
        slide_number
            1-based slide index the image is placed on. Defaults to the
            last slide.
        height
            Image frame height in points. Defaults to 90% of the slide
            height.
        width
            Image frame width in points. Defaults to 90% of the slide
            width.
        x_shift
            Horizontal offset of the frame from the slide's top-left in
            points. Defaults to 5% of the slide width.
        y_shift
            Vertical offset of the frame from the slide's top-left in
            points. Defaults to 5% of the slide height.
        element_id
            Client-assigned Slides ``objectId`` for the new image. Must be
            unique within the presentation; defaults to a UUID4 hex
            evaluated at import time — pass an explicit value when
            inserting multiple images in the same session.
        drive
            Drive wrapper used to upload oversized images. Required when
            the encoded data URL exceeds the 2 KB inline limit.
        force_upload
            When ``True``, force a re-upload through
            :meth:`Drive.get` even if the file is already present on Drive.

        Returns
        -------
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

        See Also
        --------
        Slides.insert_text : Sibling helper for text insertion.
        mayutils.interfaces.cloud.google.Drive.get : Uploader used for large files.

        Examples
        --------
        >>> import tempfile
        >>> from pathlib import Path
        >>> from unittest.mock import MagicMock
        >>> tmp = Path(tempfile.mkdtemp()) / "chart.png"
        >>> _ = tmp.write_bytes(b"\\x89PNG\\r\\n\\x1a\\n" + b"0" * 16)
        >>> deck = Slides(
        ...     {
        ...         "presentationId": "pid",
        ...         "title": "t",
        ...         "slides": [
        ...             {"objectId": "g1"},
        ...             {"objectId": "g2"},
        ...         ],
        ...         "pageSize": {
        ...             "width": {"magnitude": 9144000},
        ...             "height": {"magnitude": 5143500},
        ...         },
        ...     },
        ...     slides_service=MagicMock(),
        ... )
        >>> result = deck.insert_image(
        ...     tmp,
        ...     slide_number=2,
        ... )
        >>> result is deck
        True
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
            """
            Upload the outer image and return a Drive thumbnail URL.

            Delegate to :meth:`Drive.get` to ensure the asset exists on
            Drive (respecting the outer ``force_upload`` flag captured via
            closure), then fetch the ``thumbnailLink`` metadata field so
            the Slides ``createImage`` request can reference the asset by
            URL. The thumbnail link is short-lived but suffices for the
            single ``batchUpdate`` call that follows.

            Parameters
            ----------
            drive
                Drive wrapper used to upload the image (if missing) and
                fetch its metadata. The closure-captured ``image_path``
                and ``force_upload`` variables determine upload behaviour.

            Returns
            -------
                The ``thumbnailLink`` field from the uploaded Drive file,
                suitable as the ``url`` of a ``createImage`` request.

            Raises
            ------
            ValueError
                If Drive does not return a ``thumbnailLink`` for the
                uploaded file (e.g. thumbnail generation still pending).

            See Also
            --------
            mayutils.interfaces.cloud.google.Drive.get : Upload-or-reuse helper.

            Examples
            --------
            >>> from unittest.mock import MagicMock
            >>> drive = MagicMock()
            >>> drive.get.return_value = "uploaded_id"
            >>> drive.files().get().execute.return_value = {
            ...     "thumbnailLink": "https://example.com/thumb.png",
            ... }
            >>> # get_file_thumbnail is an inner closure exercised by insert_image
            """
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
