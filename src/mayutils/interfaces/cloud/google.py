"""
Provide a Google Drive service wrapper built on the v3 REST API.

This module exposes a thin, ergonomic layer over ``googleapiclient``'s
generated Drive resource. The :class:`Drive` class bundles common
file-management tasks (listing, finding, deleting, uploading and
refreshing) so that downstream callers only need an authenticated
``Credentials`` object to manipulate files in both user drives and
shared drives. All helpers consistently opt in to shared-drive support
and resumable uploads, and they normalise Drive's verbose list
responses into the small handful of return shapes the rest of
``mayutils`` expects.

See Also
--------
googleapiclient.discovery.Resource : Generated Drive v3 discovery resource.
google.oauth2.credentials.Credentials : OAuth2 credential carrier used to
    authenticate every Drive request issued by :class:`Drive`.
mayutils.interfaces.cloud : Sibling package housing cloud interface
    wrappers that share this authentication pattern.

Examples
--------
>>> from google.oauth2.credentials import Credentials
>>> from mayutils.interfaces.cloud.google import Drive
>>> creds = Credentials(token="ya29.a0Af...")  # doctest: +SKIP
>>> drive = Drive.from_creds(creds)  # doctest: +SKIP
>>> drive.find_file_id("quarterly_report.pdf")  # doctest: +SKIP
'1a2b3c4d5e6f'
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from googleapiclient.discovery import build  # pyright: ignore[reportUnknownVariableType]
    from googleapiclient.http import MediaFileUpload

if TYPE_CHECKING:
    from google.oauth2.credentials import Credentials
    from googleapiclient._apis.drive.v3.resources import DriveResource  # pyright: ignore[reportMissingModuleSource]
    from googleapiclient._apis.drive.v3.schemas import File  # pyright: ignore[reportMissingModuleSource]


class Drive:
    """
    Wrap the Google Drive v3 API with a high-level, ergonomic client.

    The class stores an authenticated ``DriveResource`` and exposes
    convenience methods for searching, uploading, updating and deleting
    files. All methods default to configurations that work across both
    personal and shared drives, translating Drive's lower-level
    discovery responses into Pythonic return shapes. Raising behaviour
    is aligned with standard Python exceptions such as
    :class:`FileNotFoundError` and :class:`ValueError` rather than the
    verbose Google API errors, which keeps calling code readable.

    Parameters
    ----------
    drive_service
        An authenticated Drive v3 resource (typically produced by
        ``googleapiclient.discovery.build``) that will be used as the
        transport for every operation on this instance.

    Attributes
    ----------
    service
        The underlying ``googleapiclient`` Drive v3 resource used by
        every helper method to talk to the API.

    See Also
    --------
    googleapiclient.discovery.Resource : The discovery resource base
        class underpinning :attr:`service`.
    google.oauth2.credentials.Credentials : Credential object consumed
        by :meth:`from_creds` to authorise API calls.
    mayutils.interfaces.cloud : Sibling cloud interface helpers.

    Notes
    -----
    Construct instances via :meth:`from_creds` to avoid hand-building
    the service, or pass in a pre-built resource when integrating with
    an existing client stack.

    Examples
    --------
    >>> from google.oauth2.credentials import Credentials
    >>> from mayutils.interfaces.cloud.google import Drive
    >>> creds = Credentials(token="ya29.a0Af...")  # doctest: +SKIP
    >>> drive = Drive.from_creds(creds)  # doctest: +SKIP
    >>> file_id = drive.find_file_id("quarterly_report.pdf")  # doctest: +SKIP
    >>> drive.upload("/tmp/report.pdf", folder_id="0APnK...")  # doctest: +SKIP
    """

    def __init__(
        self,
        drive_service: DriveResource,
        /,
    ) -> None:
        """
        Store an authenticated Drive v3 resource for later use.

        The constructor merely binds the provided discovery resource to
        the instance so subsequent helpers can dispatch API calls
        against a single, reusable transport. No network activity is
        performed here; authentication, token refresh, and scope checks
        are expected to have happened upstream when the resource was
        built.

        Parameters
        ----------
        drive_service
            An authenticated Drive v3 resource (typically produced by
            ``googleapiclient.discovery.build``) that will be used as
            the transport for every operation on this instance.

        See Also
        --------
        googleapiclient.discovery.build : Factory used to produce the
            ``DriveResource`` passed in here.
        Drive.from_creds : Alternative constructor that wires up the
            resource from an OAuth2 credential object.
        google.oauth2.credentials.Credentials : Credential object
            typically used to authorise the underlying service.

        Examples
        --------
        >>> from googleapiclient.discovery import build
        >>> from mayutils.interfaces.cloud.google import Drive
        >>> service = build("drive", "v3", credentials=creds)  # doctest: +SKIP
        >>> drive = Drive(service)  # doctest: +SKIP
        >>> isinstance(drive, Drive)  # doctest: +SKIP
        True
        """
        self.service = drive_service

    def files(
        self,
    ) -> DriveResource.FilesResource:
        """
        Return the ``files`` sub-resource of the underlying Drive service.

        The method is a thin alias for ``self.service.files()``. It is
        kept as its own entry point so that every helper shares a single
        access path and any future cross-cutting logic (for example
        request logging or retry wrapping) can be applied to the files
        endpoint in exactly one place. No caching is performed; each
        call returns a fresh ``FilesResource`` object from the bound
        service.

        Returns
        -------
            The ``files`` collection on the bound Drive service, ready
            for ``list``, ``get``, ``create``, ``update`` and ``delete``
            calls.

        See Also
        --------
        googleapiclient.discovery.Resource : Base class for the
            sub-resources returned here.
        google.oauth2.credentials.Credentials : Credential type that
            authorised the underlying service.
        Drive.query_files : Higher-level helper that consumes this
            sub-resource to issue search queries.

        Examples
        --------
        >>> from mayutils.interfaces.cloud.google import Drive
        >>> drive = Drive.from_creds(creds)  # doctest: +SKIP
        >>> files_resource = drive.files()  # doctest: +SKIP
        >>> response = files_resource.list(pageSize=5).execute()  # doctest: +SKIP
        """
        return self.service.files()

    @classmethod
    def from_creds(
        cls,
        creds: Credentials,
        /,
    ) -> Self:
        """
        Construct a :class:`Drive` from an authenticated credential set.

        The factory builds the ``drive`` v3 discovery client under the
        hood, removing the need for callers to import
        ``googleapiclient`` themselves. The resulting instance shares
        the lifetime of the passed-in credentials, so token refresh
        handling remains the responsibility of the caller. Scopes
        sufficient for the intended operations must be present on the
        credentials before construction.

        Parameters
        ----------
        creds
            OAuth2 credentials that will authorise every Drive request.
            These should already be refreshed and carry scopes
            sufficient for the operations the caller intends (typically
            ``https://www.googleapis.com/auth/drive``).

        Returns
        -------
            A fully initialised :class:`Drive` bound to a freshly built
            Drive v3 service.

        See Also
        --------
        googleapiclient.discovery.build : Underlying factory used to
            produce the Drive v3 service resource.
        google.oauth2.credentials.Credentials : Credential object type
            accepted here.
        Drive.__init__ : Lower-level constructor used when the
            ``DriveResource`` already exists.

        Examples
        --------
        >>> from google.oauth2.credentials import Credentials
        >>> from mayutils.interfaces.cloud.google import Drive
        >>> creds = Credentials(token="ya29.a0Af...")  # doctest: +SKIP
        >>> drive = Drive.from_creds(creds)  # doctest: +SKIP
        >>> isinstance(drive, Drive)  # doctest: +SKIP
        True
        """
        drive_service = build(
            serviceName="drive",
            version="v3",
            credentials=creds,
        )

        return cls(drive_service)

    def query_files(
        self,
        query: str,
        /,
        *,
        spaces: str = "drive",
        supports_all_drives: bool = True,
        include_items_from_all_drives: bool = True,
        **kwargs: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """
        Execute a Drive ``files.list`` query and return the raw response.

        The method forwards the supplied query string (Drive's ``q``
        parameter) together with sensible shared-drive defaults to
        ``files().list`` and returns the decoded JSON body untouched.
        Defaulting ``supports_all_drives`` and
        ``include_items_from_all_drives`` to ``True`` ensures shared
        drive items are visible without additional caller plumbing.
        Pagination is not handled here; callers that expect large
        result sets should inspect ``nextPageToken`` and re-invoke with
        a ``pageToken`` keyword.

        Parameters
        ----------
        query
            Drive query string (the ``q`` parameter) filtering which
            files are returned; follows Drive's search syntax, e.g.
            ``"name = 'foo' and trashed = false"``.
        spaces
            Comma-separated Drive spaces to search. ``'drive'`` scopes
            the search to the user's Drive; other valid values include
            ``'appDataFolder'``.
        supports_all_drives
            When ``True``, the caller acknowledges support for shared
            drives, which is required to see or act on files that live
            inside shared drives.
        include_items_from_all_drives
            When ``True``, shared-drive items are returned alongside
            personal Drive items. Only meaningful when
            ``supports_all_drives`` is also ``True``.
        **kwargs
            Additional keyword arguments forwarded verbatim to
            ``files().list``; typical extras include ``fields``,
            ``pageSize`` or ``orderBy``.

        Returns
        -------
            The decoded JSON body returned by Drive, usually a mapping
            containing ``files`` (a list of file resources) and
            pagination metadata such as ``nextPageToken``.

        See Also
        --------
        googleapiclient.discovery.Resource : Base class providing the
            ``files().list`` method dispatched here.
        google.oauth2.credentials.Credentials : Credential type that
            authorised the underlying service.
        Drive.find_file : Higher-level helper that wraps this query for
            the common name-lookup case.

        Examples
        --------
        >>> from mayutils.interfaces.cloud.google import Drive
        >>> drive = Drive.from_creds(creds)  # doctest: +SKIP
        >>> result = drive.query_files(  # doctest: +SKIP
        ...     "name = 'report.pdf' and trashed = false",
        ...     fields="files(id, name)",
        ... )
        >>> result["files"]  # doctest: +SKIP
        [{'id': '1a2b', 'name': 'report.pdf'}]
        """
        return (
            self.files()  # pyright: ignore[reportReturnType]  # ty:ignore[invalid-return-type]
            .list(
                q=query,
                spaces=spaces,
                supportsAllDrives=supports_all_drives,
                includeItemsFromAllDrives=include_items_from_all_drives,
                **kwargs,
            )
            .execute()
        )

    def find_file(
        self,
        file_name: str,
        /,
        *,
        folder_id: str | None = None,
    ) -> File | None:
        """
        Look up the first non-trashed Drive file with the given name.

        The helper composes a Drive search query that combines an
        exact name match with a ``trashed = false`` filter and
        optionally a parent-folder constraint. Only the ``id`` and
        ``name`` fields are requested to keep the payload lean. The
        first matching entry is returned so callers that expect unique
        names receive a direct answer; callers with ambiguous names
        should scope the lookup via ``folder_id``.

        Parameters
        ----------
        file_name
            Exact display name to match. Drive's ``name`` field is
            used, so the search is case-sensitive and does not
            interpret wildcards.
        folder_id
            If provided, restricts the search to files whose parent is
            this Drive folder ID, which is useful to disambiguate
            common file names. When ``None``, all folders the user can
            see are searched.

        Returns
        -------
            The first Drive ``File`` resource matching the query,
            limited to the ``id`` and ``name`` fields, or ``None``
            when no such file exists.

        See Also
        --------
        googleapiclient.discovery.Resource : Source of the ``files().list``
            method invoked internally.
        google.oauth2.credentials.Credentials : Credentials used to
            authorise the lookup.
        Drive.find_file_id : Companion helper that returns just the ID
            and raises when missing.

        Examples
        --------
        >>> from mayutils.interfaces.cloud.google import Drive
        >>> drive = Drive.from_creds(creds)  # doctest: +SKIP
        >>> drive.find_file("report.pdf")  # doctest: +SKIP
        {'id': '1a2b', 'name': 'report.pdf'}
        >>> drive.find_file("report.pdf", folder_id="0APnK...")  # doctest: +SKIP
        {'id': '1a2b', 'name': 'report.pdf'}
        >>> drive.find_file("missing.pdf") is None  # doctest: +SKIP
        True
        """
        query = f"name = '{file_name}' and trashed = false"
        if folder_id is not None:
            query += f" and '{folder_id}' in parents"

        results = self.query_files(
            query,
            fields="files(id, name)",
        )

        return (results.get("files", []) or [None])[0]

    def find_file_id(
        self,
        file_name: str,
        /,
        **kwargs: Any,  # noqa: ANN401
    ) -> str:
        """
        Resolve a Drive file name to its unique Drive file ID.

        The method composes :meth:`find_file` and then extracts the
        opaque Drive ``id`` so downstream helpers can target the file
        directly. Any scoping keyword (for example ``folder_id``) is
        forwarded verbatim so callers can disambiguate common names.
        Two specific failure paths raise: missing files and payloads
        that lack an ``id`` field.

        Parameters
        ----------
        file_name
            Exact display name to resolve. The first matching
            non-trashed file is used; callers who need disambiguation
            should pass a ``folder_id`` via ``**kwargs``.
        **kwargs
            Extra keyword arguments forwarded to :meth:`find_file`,
            most notably ``folder_id`` to scope the lookup.

        Returns
        -------
            The Drive file ID (the stable opaque identifier used by
            the Drive API).

        Raises
        ------
        FileNotFoundError
            If no non-trashed file with ``file_name`` exists in the
            searched scope.
        ValueError
            If Drive returns a matching file but its payload lacks an
            ``id`` field (an unexpected API state).

        See Also
        --------
        googleapiclient.discovery.Resource : Source of the underlying
            ``files().list`` call.
        google.oauth2.credentials.Credentials : Credentials authorising
            the lookup.
        Drive.find_file : Lower-level helper that returns the full file
            resource rather than just the ID.

        Examples
        --------
        >>> from mayutils.interfaces.cloud.google import Drive
        >>> drive = Drive.from_creds(creds)  # doctest: +SKIP
        >>> drive.find_file_id("report.pdf")  # doctest: +SKIP
        '1a2b3c'
        >>> drive.find_file_id("report.pdf", folder_id="0APnK...")  # doctest: +SKIP
        '9z8y7x'
        """
        file: File | None = self.find_file(
            file_name,
            **kwargs,
        )
        if not file:
            msg = f"File '{file_name}' not found."
            raise FileNotFoundError(msg)

        file_id: str | None = file.get("id", None)
        if not file_id:
            msg = f"File '{file_name}' has no ID."
            raise ValueError(msg)

        return file_id

    def delete_file_by_id(
        self,
        file_id: str,
        /,
    ) -> None:
        """
        Permanently delete a Drive file by its unique ID.

        The method invokes ``files().delete`` with the supplied ID,
        which removes the file immediately and bypasses the Drive
        trash. Because no ``supportsAllDrives`` flag is forwarded, the
        helper targets items in the user's own Drive; callers needing
        shared-drive deletion should use :meth:`delete_file_by_name`
        or call the underlying service directly. Success is inferred
        from the absence of a raised exception.

        Parameters
        ----------
        file_id
            Drive file ID of the resource to remove. The delete is
            immediate and bypasses the trash, so the file is
            unrecoverable via normal user flows.

        See Also
        --------
        googleapiclient.discovery.Resource : Source of the
            ``files().delete`` method dispatched here.
        google.oauth2.credentials.Credentials : Credentials authorising
            the destructive call.
        Drive.delete_file_by_name : Name-based deletion helper that
            resolves to an ID before delegating here.

        Examples
        --------
        >>> from mayutils.interfaces.cloud.google import Drive
        >>> drive = Drive.from_creds(creds)  # doctest: +SKIP
        >>> drive.delete_file_by_id("1a2b3c")  # doctest: +SKIP
        """
        self.files().delete(fileId=file_id).execute()  # pyright: ignore[reportUnknownMemberType]

    def delete_file_by_name(
        self,
        file_name: str,
        /,
        *,
        supports_all_drives: bool = True,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """
        Permanently delete a Drive file located via its display name.

        The helper resolves ``file_name`` to a Drive file ID via
        :meth:`find_file_id` and then issues ``files().delete`` with
        ``supportsAllDrives`` enabled by default, which allows
        removing items on shared drives as well as personal Drive.
        Scoping keywords such as ``folder_id`` are forwarded to the
        lookup stage to reduce the risk of deleting the wrong file
        when names collide.

        Parameters
        ----------
        file_name
            Display name of the file to delete. Resolved to an ID via
            :meth:`find_file_id`; scoping the search (for example by
            ``folder_id`` in ``**kwargs``) is recommended when the
            name may collide with other files.
        supports_all_drives
            When ``True``, allows deleting items that live on shared
            drives as well as the user's own Drive.
        **kwargs
            Extra keyword arguments forwarded to :meth:`find_file_id`
            for scoping the lookup (for example ``folder_id``).

        See Also
        --------
        googleapiclient.discovery.Resource : Source of the underlying
            ``files().delete`` method.
        google.oauth2.credentials.Credentials : Credentials authorising
            the destructive call.
        Drive.delete_file_by_id : Lower-level helper used once the ID
            has been resolved.

        Examples
        --------
        >>> from mayutils.interfaces.cloud.google import Drive
        >>> drive = Drive.from_creds(creds)  # doctest: +SKIP
        >>> drive.delete_file_by_name("report.pdf")  # doctest: +SKIP
        >>> drive.delete_file_by_name(  # doctest: +SKIP
        ...     "report.pdf",
        ...     folder_id="0APnK...",
        ... )
        """
        self.files().delete(
            fileId=self.find_file_id(
                file_name,
                **kwargs,
            ),
            supportsAllDrives=supports_all_drives,
        ).execute()  # pyright: ignore[reportUnknownMemberType]

    def _create_media(
        self,
        file_path: Path,
        /,
        *,
        folder_id: str | None = None,
    ) -> tuple[MediaFileUpload, File]:
        """
        Build the ``MediaFileUpload`` and metadata payload for an upload.

        The helper validates that the local file exists, infers a
        MIME type from the filename, and constructs a resumable
        ``MediaFileUpload`` together with the ``File`` metadata body
        expected by Drive's ``create``/``update`` endpoints. Resumable
        mode is enabled unconditionally so large uploads survive
        transient network errors via chunked retries. When
        ``folder_id`` is provided it is injected into the metadata so
        new files are created directly inside the target folder.

        Parameters
        ----------
        file_path
            Local filesystem location of the file to send. The file
            must exist; its ``name`` is used as the Drive display name
            and its extension drives MIME-type inference.
        folder_id
            Drive ID of the destination folder. When provided, the
            resulting metadata sets this folder as the file's parent;
            when ``None``, the file is placed in the authenticated
            user's root Drive.

        Returns
        -------
            A two-tuple where the first element is a resumable
            ``MediaFileUpload`` pointing at ``file_path`` with the
            detected MIME type, and the second is the Drive ``File``
            metadata dict (``name``, ``mimeType`` and optional
            ``parents``) ready to be sent as the request body.

        Raises
        ------
        FileNotFoundError
            If ``file_path`` does not exist on disk.
        ValueError
            If ``mimetypes`` cannot infer a content type from the
            file's extension.

        See Also
        --------
        googleapiclient.http.MediaFileUpload : Resumable-upload wrapper
            produced here.
        google.oauth2.credentials.Credentials : Credentials authorising
            the eventual Drive call.
        Drive._upload : Consumer of the returned media and metadata
            pair for fresh uploads.

        Examples
        --------
        >>> from pathlib import Path
        >>> from mayutils.interfaces.cloud.google import Drive
        >>> drive = Drive.from_creds(creds)  # doctest: +SKIP
        >>> media, meta = drive._create_media(  # doctest: +SKIP
        ...     Path("/tmp/report.pdf"),
        ...     folder_id="0APnK...",
        ... )
        >>> meta["mimeType"]  # doctest: +SKIP
        'application/pdf'
        """
        if not file_path.exists():
            msg = f"File not found: {file_path}"
            raise FileNotFoundError(msg)

        mimetype = mimetypes.guess_type(url=file_path)[0]
        if not mimetype:
            msg = f"Could not determine mime type for {file_path}"
            raise ValueError(msg)

        file_metadata: File = {
            "name": file_path.name,
            "mimeType": mimetype,
        }
        if folder_id is not None:
            file_metadata["parents"] = [folder_id]

        media = MediaFileUpload(
            filename=str(file_path),
            mimetype=mimetype,
            resumable=True,
        )

        return media, file_metadata

    def _upload(
        self,
        file_path: Path,
        /,
        *,
        folder_id: str | None = None,
    ) -> str:
        """
        Create a new Drive file from a local path via resumable upload.

        The helper prepares the media payload with :meth:`_create_media`
        and then issues ``files().create`` with
        ``supportsAllDrives=True`` so the call works identically in
        personal and shared drives. Only the ``id`` field is returned
        by Drive to keep the response small; the method then validates
        that the ID is present before handing it back. The resumable
        upload transparently retries failed chunks until the upload
        completes or an unrecoverable error surfaces.

        Parameters
        ----------
        file_path
            Local file to upload. Its basename becomes the Drive
            display name and its extension is used for MIME-type
            detection.
        folder_id
            Drive folder ID to create the file inside. When ``None``,
            the file is created at the root of the user's Drive.

        Returns
        -------
            The Drive file ID assigned to the newly created resource.

        Raises
        ------
        ValueError
            If the MIME type cannot be inferred, or if Drive's
            response does not include an ``id`` for the created file.

        See Also
        --------
        googleapiclient.discovery.Resource : Source of the
            ``files().create`` endpoint invoked here.
        google.oauth2.credentials.Credentials : Credentials authorising
            the upload.
        Drive.upload : Public wrapper that delegates to this helper
            when no existing file is present.

        Examples
        --------
        >>> from pathlib import Path
        >>> from mayutils.interfaces.cloud.google import Drive
        >>> drive = Drive.from_creds(creds)  # doctest: +SKIP
        >>> drive._upload(Path("/tmp/report.pdf"), folder_id="0APnK...")  # doctest: +SKIP
        '1a2b3c4d'
        """
        media, file_metadata = self._create_media(
            file_path,
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
            msg = f"Failed to upload file: {file_path}"
            raise ValueError(msg)

        return uploaded_file_id

    def _update(
        self,
        file_path: Path,
        /,
        file_id: str,
        *,
        folder_id: str | None = None,
    ) -> str:
        """
        Replace an existing Drive file's contents with a local file.

        The helper prepares the same media payload as :meth:`_upload`
        but discards the metadata body because Drive's ``update``
        endpoint rejects parent changes bundled with media content.
        Only the binary contents are replaced; the file's name,
        parents, and sharing settings remain intact, which keeps
        existing links and permissions stable. Resumable mode is
        inherited from :meth:`_create_media`, so large update payloads
        survive transient network errors.

        Parameters
        ----------
        file_path
            Local file whose bytes will overwrite the Drive file's
            current contents. Its MIME type is inferred and applied
            to the upload.
        file_id
            Drive file ID of the resource to update in place.
        folder_id
            Accepted for symmetry with :meth:`_upload` and used only
            when constructing the media payload. Drive's update call
            itself does not move the file, so this value has no
            effect on the file's parents.

        Returns
        -------
            The Drive file ID of the updated resource, echoed back for
            convenience (always equal to ``file_id`` on success).

        Raises
        ------
        ValueError
            If the MIME type cannot be inferred, or if Drive's
            response does not include an ``id`` for the updated file.

        See Also
        --------
        googleapiclient.discovery.Resource : Source of the
            ``files().update`` endpoint invoked here.
        google.oauth2.credentials.Credentials : Credentials authorising
            the update.
        Drive.upload : Public wrapper that delegates to this helper
            when an existing file is found.

        Examples
        --------
        >>> from pathlib import Path
        >>> from mayutils.interfaces.cloud.google import Drive
        >>> drive = Drive.from_creds(creds)  # doctest: +SKIP
        >>> drive._update(  # doctest: +SKIP
        ...     Path("/tmp/report.pdf"),
        ...     file_id="1a2b3c4d",
        ... )
        '1a2b3c4d'
        """
        media, _file_metadata = self._create_media(
            file_path,
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
            msg = f"Failed to upload file: {file_path}"
            raise ValueError(msg)

        return updated_file_id

    def upload(
        self,
        file_path: Path | str,
        /,
        *,
        folder_id: str | None = None,
    ) -> str:
        """
        Upload a local file to Drive, overwriting any same-named file.

        The method resolves an existing Drive file by display name
        (the basename of ``file_path``); if found, its contents are
        replaced in-place via :meth:`_update`, otherwise a fresh file
        is created with :meth:`_upload`. This pattern preserves the
        Drive file ID across refreshes, which is important for
        callers that share links or cache IDs downstream. String
        inputs are coerced to :class:`pathlib.Path` to centralise
        path and extension handling.

        Parameters
        ----------
        file_path
            Local filesystem location of the file to upload. String
            inputs are coerced to :class:`pathlib.Path` for consistent
            name/extension handling.
        folder_id
            Drive folder ID used when creating a new file. Ignored
            when an existing file is updated, because Drive's update
            call leaves the file's parents untouched.

        Returns
        -------
            The Drive file ID of the resulting (created or updated)
            resource.

        See Also
        --------
        googleapiclient.discovery.Resource : Source of the underlying
            ``files().create``/``files().update`` endpoints.
        google.oauth2.credentials.Credentials : Credentials authorising
            the upload.
        Drive.get : Higher-level helper that skips uploading when an
            existing Drive copy is already present.

        Examples
        --------
        >>> from mayutils.interfaces.cloud.google import Drive
        >>> drive = Drive.from_creds(creds)  # doctest: +SKIP
        >>> drive.upload("/tmp/report.pdf", folder_id="0APnK...")  # doctest: +SKIP
        '1a2b3c4d'
        """
        file_path = Path(file_path)

        try:
            file_id = self.find_file_id(file_path.name)
        except (FileNotFoundError, ValueError):
            file_id = None

        if file_id is not None:
            return self._update(
                file_path,
                file_id=file_id,
                folder_id=folder_id,
            )
        return self._upload(
            file_path,
            folder_id=folder_id,
        )

    def get(
        self,
        file_path: Path | str,
        /,
        *,
        force_upload: bool = False,
    ) -> str:
        """
        Return a Drive file ID for ``file_path``, uploading only if needed.

        The method looks up the Drive file whose name equals the full
        string form of ``file_path`` (matching the lookup convention
        used by the rest of ``mayutils``). If the lookup succeeds and
        ``force_upload`` is ``False``, the existing ID is returned
        unchanged and no bytes cross the network. If the lookup fails,
        or if ``force_upload`` requests a fresh copy, the file is
        (re-)uploaded via :meth:`upload` after the old Drive copy (if
        any) has been deleted to avoid stale ID collisions.

        Parameters
        ----------
        file_path
            Local file to use as the source of truth. String inputs
            are coerced to :class:`pathlib.Path`.
        force_upload
            When ``True``, the existing Drive copy (if any) is deleted
            and a brand-new file is uploaded, producing a fresh Drive
            file ID. When ``False``, an existing matching file is
            reused without being modified.

        Returns
        -------
            The Drive file ID that now corresponds to ``file_path``.

        See Also
        --------
        googleapiclient.discovery.Resource : Source of the underlying
            ``files().list``/``files().create`` endpoints.
        google.oauth2.credentials.Credentials : Credentials authorising
            the underlying Drive calls.
        Drive.upload : Helper used when an upload is required.

        Examples
        --------
        Reuse an existing Drive copy if it exists:

        >>> from mayutils.interfaces.cloud.google import Drive
        >>> drive = Drive.from_creds(creds)  # doctest: +SKIP
        >>> drive.get("/tmp/report.pdf")  # doctest: +SKIP
        '1a2b3c4d'

        Force a fresh upload even when a copy is already present:

        >>> drive.get("/tmp/report.pdf", force_upload=True)  # doctest: +SKIP
        '9z8y7x6w'
        """
        file_path = Path(file_path)

        try:
            file_id = self.find_file_id(str(file_path))
            if force_upload:
                self.delete_file_by_id(file_id)
                file_id = self.upload(file_path)

        except FileNotFoundError:
            file_id = self.upload(file_path)

        return file_id
