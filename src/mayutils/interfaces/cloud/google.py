"""Google Drive service wrapper built on the v3 REST API.

Provides a thin, ergonomic layer over ``googleapiclient``'s generated Drive
resource. The :class:`Drive` class bundles common file-management tasks
(listing, finding, deleting, uploading and refreshing) so that downstream
callers only need an authenticated ``Credentials`` object to manipulate files
in both user drives and shared drives. All helpers consistently opt in to
shared-drive support and resumable uploads, and they normalise Drive's
verbose list responses into the small handful of return shapes the rest of
``mayutils`` expects.
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
    """High-level client over the Google Drive v3 API.

    Wraps an authenticated ``DriveResource`` and exposes convenience methods
    for searching, uploading, updating and deleting files. All methods
    default to configurations that work across both personal and shared
    drives, and raising behaviour is aligned with standard Python
    exceptions (``FileNotFoundError``, ``ValueError``) rather than the
    lower-level Google API errors.

    Attributes
    ----------
    service : DriveResource
        The underlying ``googleapiclient`` Drive v3 resource used by every
        helper method to talk to the API.

    Notes
    -----
    Construct instances via :meth:`from_creds` to avoid hand-building the
    service, or pass in a pre-built resource when integrating with an
    existing client stack.
    """

    def __init__(
        self,
        drive_service: DriveResource,
        /,
    ) -> None:
        """Store an authenticated Drive v3 resource for later use.

        Parameters
        ----------
        drive_service : DriveResource
            An authenticated Drive v3 resource (typically produced by
            ``googleapiclient.discovery.build``) that will be used as the
            transport for every operation on this instance.
        """
        self.service = drive_service

    def files(
        self,
    ) -> DriveResource.FilesResource:
        """Return the ``files`` sub-resource of the underlying Drive service.

        This is a thin alias for ``self.service.files()`` kept so that
        every helper can share a single entry point and future-proof any
        cross-cutting logic (for example request logging or retry
        wrapping) applied to the files endpoint.

        Returns
        -------
        DriveResource.FilesResource
            The ``files`` collection on the bound Drive service, ready for
            ``list``, ``get``, ``create``, ``update`` and ``delete`` calls.
        """
        return self.service.files()

    @classmethod
    def from_creds(
        cls,
        creds: Credentials,
        /,
    ) -> Self:
        """Construct a :class:`Drive` from an authenticated credential set.

        Builds the ``drive`` v3 discovery client under the hood, removing
        the need for callers to import ``googleapiclient`` themselves.

        Parameters
        ----------
        creds : Credentials
            OAuth2 credentials that will authorise every Drive request.
            These should already be refreshed and carry scopes sufficient
            for the operations the caller intends (typically
            ``https://www.googleapis.com/auth/drive``).

        Returns
        -------
        Self
            A fully initialised :class:`Drive` bound to a freshly built
            Drive v3 service.

        Examples
        --------
        >>> drive = Drive.from_creds(creds=oauth_credentials)
        >>> drive.find_file_id(file_name="report.pdf")
        '1a2b3c...'
        """
        drive_service: DriveResource = build(  # pyright: ignore[reportUnknownVariableType]
            serviceName="drive",
            version="v3",
            credentials=creds,
        )

        return cls(
            drive_service,  # pyright: ignore[reportUnknownArgumentType]
        )

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
        """Execute a Drive ``files.list`` query and return the raw response.

        Parameters
        ----------
        query : str
            Drive query string (the ``q`` parameter) filtering which files
            are returned; follows Drive's search syntax, e.g.
            ``"name = 'foo' and trashed = false"``.
        spaces : str, default 'drive'
            Comma-separated Drive spaces to search. ``'drive'`` scopes
            the search to the user's Drive; other valid values include
            ``'appDataFolder'``.
        supportsAllDrives : bool, default True
            When ``True``, the caller acknowledges support for shared
            drives, which is required to see or act on files that live
            inside shared drives.
        includeItemsFromAllDrives : bool, default True
            When ``True``, shared-drive items are returned alongside
            personal Drive items. Only meaningful when
            ``supportsAllDrives`` is also ``True``.
        **kwargs
            Additional keyword arguments forwarded verbatim to
            ``files().list``; typical extras include ``fields``,
            ``pageSize`` or ``orderBy``.

        Returns
        -------
        Any
            The decoded JSON body returned by Drive, usually a mapping
            containing ``files`` (a list of file resources) and
            pagination metadata such as ``nextPageToken``.
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
        """Look up the first non-trashed Drive file with the given name.

        Parameters
        ----------
        file_name : str
            Exact display name to match. Drive's ``name`` field is used,
            so the search is case-sensitive and does not interpret
            wildcards.
        folder_id : str | None, optional
            If provided, restricts the search to files whose parent is
            this Drive folder ID, which is useful to disambiguate common
            file names. When ``None``, all folders the user can see are
            searched.

        Returns
        -------
        File | None
            The first Drive ``File`` resource matching the query, limited
            to the ``id`` and ``name`` fields, or ``None`` when no such
            file exists.
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
        """Resolve a Drive file name to its unique Drive file ID.

        Parameters
        ----------
        file_name : str
            Exact display name to resolve. The first matching
            non-trashed file is used; callers who need disambiguation
            should pass a ``folder_id`` via ``**kwargs``.
        **kwargs
            Extra keyword arguments forwarded to :meth:`find_file`, most
            notably ``folder_id`` to scope the lookup.

        Returns
        -------
        str
            The Drive file ID (the stable opaque identifier used by the
            Drive API).

        Raises
        ------
        FileNotFoundError
            If no non-trashed file with ``file_name`` exists in the
            searched scope.
        ValueError
            If Drive returns a matching file but its payload lacks an
            ``id`` field (an unexpected API state).
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
        """Permanently delete a Drive file by its unique ID.

        Parameters
        ----------
        file_id : str
            Drive file ID of the resource to remove. The delete is
            immediate and bypasses the trash, so the file is
            unrecoverable via normal user flows.

        Returns
        -------
        None
            Nothing is returned; success is indicated by the absence of
            a raised exception from the underlying API call.
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
        """Permanently delete a Drive file located via its display name.

        Parameters
        ----------
        file_name : str
            Display name of the file to delete. Resolved to an ID via
            :meth:`find_file_id`; scoping the search (for example by
            ``folder_id`` in ``**kwargs``) is recommended when the name
            may collide with other files.
        supportsAllDrives : bool, default True
            When ``True``, allows deleting items that live on shared
            drives as well as the user's own Drive.
        **kwargs
            Extra keyword arguments forwarded to :meth:`find_file_id`
            for scoping the lookup (for example ``folder_id``).

        Returns
        -------
        None
            Nothing is returned; a successful call means the file has
            been removed.

        Raises
        ------
        FileNotFoundError
            If ``file_name`` does not resolve to any Drive file.
        ValueError
            If the located file lacks an ID in Drive's response.
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
        """Build the ``MediaFileUpload`` and metadata payload for an upload.

        Parameters
        ----------
        file_path : Path
            Local filesystem location of the file to send. The file must
            exist; its ``name`` is used as the Drive display name and
            its extension drives MIME-type inference.
        folder_id : str | None, optional
            Drive ID of the destination folder. When provided, the
            resulting metadata sets this folder as the file's parent;
            when ``None``, the file is placed in the authenticated
            user's root Drive.

        Returns
        -------
        tuple of (MediaFileUpload, File)
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
        """Create a new Drive file from a local path via resumable upload.

        Parameters
        ----------
        file_path : Path
            Local file to upload. Its basename becomes the Drive display
            name and its extension is used for MIME-type detection.
        folder_id : str | None, optional
            Drive folder ID to create the file inside. When ``None``,
            the file is created at the root of the user's Drive.

        Returns
        -------
        str
            The Drive file ID assigned to the newly created resource.

        Raises
        ------
        FileNotFoundError
            If ``file_path`` does not exist locally.
        ValueError
            If the MIME type cannot be inferred, or if Drive's response
            does not include an ``id`` for the created file.
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
        """Replace an existing Drive file's contents with a local file.

        The metadata object returned by :meth:`_create_media` is
        discarded: Drive's ``update`` endpoint rejects parent changes
        bundled with media content, so only the media body is sent and
        the existing file's name and location are preserved.

        Parameters
        ----------
        file_path : Path
            Local file whose bytes will overwrite the Drive file's
            current contents. Its MIME type is inferred and applied to
            the upload.
        file_id : str
            Drive file ID of the resource to update in place.
        folder_id : str | None, optional
            Accepted for symmetry with :meth:`_upload` and used only
            when constructing the media payload. Drive's update call
            itself does not move the file, so this value has no effect
            on the file's parents.

        Returns
        -------
        str
            The Drive file ID of the updated resource, echoed back for
            convenience (always equal to ``file_id`` on success).

        Raises
        ------
        FileNotFoundError
            If ``file_path`` does not exist locally.
        ValueError
            If the MIME type cannot be inferred, or if Drive's response
            does not include an ``id`` for the updated file.
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
        """Upload a local file to Drive, overwriting any same-named file.

        Resolves an existing Drive file by display name (the basename of
        ``file_path``); if found, its contents are replaced in-place via
        :meth:`_update`, otherwise a fresh file is created with
        :meth:`_upload`. This preserves the Drive file ID across
        refreshes, which is important for callers that share links or
        cache IDs.

        Parameters
        ----------
        file_path : Path | str
            Local filesystem location of the file to upload. String
            inputs are coerced to :class:`pathlib.Path` for consistent
            name/extension handling.
        folder_id : str | None, optional
            Drive folder ID used when creating a new file. Ignored when
            an existing file is updated, because Drive's update call
            leaves the file's parents untouched.

        Returns
        -------
        str
            The Drive file ID of the resulting (created or updated)
            resource.

        Raises
        ------
        FileNotFoundError
            If ``file_path`` does not exist locally.
        ValueError
            If the MIME type cannot be inferred, or if Drive's response
            omits the file ID for the created or updated resource.
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
        """Return a Drive file ID for ``file_path``, uploading only if needed.

        Looks up the Drive file whose name equals the string form of
        ``file_path`` (note: this is the full path string, not just
        the basename, matching the lookup convention used by the rest
        of ``mayutils``). If the lookup succeeds and ``force_upload``
        is ``False``, the existing ID is returned unchanged. If the
        lookup fails, or if ``force_upload`` requests a fresh copy, the
        file is (re-)uploaded via :meth:`upload`.

        Parameters
        ----------
        file_path : Path | str
            Local file to use as the source of truth. String inputs are
            coerced to :class:`pathlib.Path`.
        force_upload : bool, default False
            When ``True``, the existing Drive copy (if any) is deleted
            and a brand-new file is uploaded, producing a fresh Drive
            file ID. When ``False``, an existing matching file is
            reused without being modified.

        Returns
        -------
        str
            The Drive file ID that now corresponds to ``file_path``.

        Raises
        ------
        ValueError
            If an upload was required and Drive's response omits the
            file ID, or if MIME-type inference fails.
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
