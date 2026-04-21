"""Google Sheets spreadsheet wrapper.

Provides object-oriented wrappers around the Google Sheets v4 REST API,
exposing spreadsheets and individual sheets as Python objects that can be
read from and written to as pandas/polars DataFrames. The :class:`Sheets`
class manages spreadsheet-level operations (creation, retrieval, sheet
CRUD), while :class:`Sheet` represents a single tab within a spreadsheet
and supports range-based reads and writes. Drive integration is used to
look up spreadsheets by file name and to copy from template files.
"""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING, Any, Self

from mayutils.core.extras import may_require_extras
from mayutils.interfaces.cloud.google import Drive
from mayutils.objects.dataframes import column_to_excel

with may_require_extras():
    from googleapiclient.discovery import build  # pyright: ignore[reportUnknownVariableType]
    from pandas import DataFrame

if TYPE_CHECKING:
    import polars as pl
    from google.oauth2.credentials import Credentials
    from googleapiclient._apis.sheets.v4.resources import SheetsResource  # pyright: ignore[reportMissingModuleSource]
    from googleapiclient._apis.sheets.v4.schemas import (  # pyright: ignore[reportMissingModuleSource]
        Request as SheetsRequest,
    )
    from googleapiclient._apis.sheets.v4.schemas import (  # pyright: ignore[reportMissingModuleSource]
        Sheet as SheetSchema,
    )
    from googleapiclient._apis.sheets.v4.schemas import (  # pyright: ignore[reportMissingModuleSource]
        SheetProperties,
        Spreadsheet,
    )


class Sheet:
    """Single sheet within a Google Sheets spreadsheet.

    Wraps the Google Sheets API representation of a single tab and offers
    helpers for reading its contents as a pandas DataFrame and for
    writing values (including whole DataFrames) back to specific ranges.
    Each instance keeps a reference to its parent :class:`Sheets` so that
    writes can refresh the cached spreadsheet metadata after execution.

    Parameters
    ----------
    sheet : SheetSchema
        Raw ``sheets[i]`` entry returned by the Sheets API, containing
        the ``properties`` block (``sheetId``, ``title``, ``index``,
        ``gridProperties``).
    parent : Sheets
        Owning spreadsheet wrapper; used to issue batch updates and to
        re-fetch sheet metadata after writes.
    sheets_service : SheetsResource
        Authenticated Google Sheets API service client used to issue
        read/write requests against the spreadsheet.
    """

    def __init__(
        self,
        sheet: SheetSchema,
        /,
        *,
        parent: Sheets,
        sheets_service: SheetsResource,
    ) -> None:
        self.service: SheetsResource = sheets_service
        self.internal: SheetSchema = sheet
        self.id: int = self._properties["sheetId"]  # pyright: ignore[reportTypedDictNotRequiredAccess]
        self.parent = parent

    @property
    def _properties(
        self,
    ) -> SheetProperties:
        """Fetch the ``properties`` block from the raw sheet payload."""
        return self.internal["properties"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def title(
        self,
    ) -> str:
        """Title of the sheet tab as shown in the Google Sheets UI.

        Returns
        -------
        str
            Human-readable tab title taken from the sheet's
            ``properties.title`` field.
        """
        return self._properties["title"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def index(
        self,
    ) -> int:
        """Zero-based position of the sheet within its parent spreadsheet.

        Returns
        -------
        int
            Display order index; ``0`` is the leftmost tab.
        """
        return self._properties["index"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def rows(
        self,
    ) -> int:
        """Total number of rows in the sheet grid.

        Returns
        -------
        int
            Row count reported by ``properties.gridProperties.rowCount``,
            including blank trailing rows allocated by the grid.
        """
        return self._properties["gridProperties"]["rowCount"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def columns(
        self,
    ) -> int:
        """Total number of columns in the sheet grid.

        Returns
        -------
        int
            Column count reported by
            ``properties.gridProperties.columnCount``, including blank
            trailing columns allocated by the grid.
        """
        return self._properties["gridProperties"]["columnCount"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    def to_arrays(
        self,
        *,
        sheet_range: str | None = None,
    ) -> list[list[Any]]:
        """Fetch the raw cell values from the sheet as a 2D list.

        Parameters
        ----------
        range : str or None, default None
            A1-style range *without* the sheet prefix (for example
            ``"B2:D10"``). When ``None``, the full grid from ``A1`` to the
            bottom-right cell (computed from :attr:`rows` and
            :attr:`columns`) is requested.

        Returns
        -------
        list
            List of rows, where each row is a list of cell values as
            returned by the Sheets API. Trailing empty cells/rows may be
            truncated by the API.
        """
        data = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=self.parent.id,  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                range=f"{self.title}!A1:{column_to_excel(self.columns)}{self.rows}"
                if sheet_range is None
                else f"{self.title}!{sheet_range}",
            )
            .execute()
        )

        return data.get("values", [])

    def to_pandas(
        self,
        *,
        sheet_range: str | None = None,
    ) -> DataFrame:
        """Return the sheet contents as a pandas DataFrame.

        Parameters
        ----------
        range : str or None, default None
            A1-style range *without* the sheet prefix to restrict the
            read. When ``None``, the full grid is returned.

        Returns
        -------
        DataFrame
            Pandas DataFrame constructed from the 2D list of raw cell
            values. No header inference is performed — the first row is
            kept as data.
        """
        return DataFrame(data=self.to_arrays(sheet_range=sheet_range))

    def to_polars(
        self,
        *,
        sheet_range: str | None = None,
    ) -> pl.DataFrame:
        """Return the sheet contents as a polars DataFrame.

        Parameters
        ----------
        range : str or None, default None
            A1-style range *without* the sheet prefix to restrict the
            read. When ``None``, the full grid is returned.

        Returns
        -------
        pl.DataFrame
            Polars DataFrame of the sheet's raw cell values.

        Raises
        ------
        NotImplementedError
            Always — polars support has not been implemented yet.
        """
        msg = "Polars not implemented yet"
        raise NotImplementedError(msg)

    @property
    def df(
        self,
    ) -> DataFrame:
        """Full sheet as a pandas DataFrame.

        Returns
        -------
        DataFrame
            Equivalent to calling :meth:`to_pandas` with ``range=None``;
            provided for convenient attribute-style access.
        """
        return self.to_pandas(sheet_range=None)

    def __repr__(
        self,
    ) -> str:
        """Unambiguous string representation delegating to the DataFrame.

        Returns
        -------
        str
            The ``repr`` of the full sheet rendered as a pandas DataFrame.
        """
        return repr(self.df)

    def _repr_html_(
        self,
    ) -> str:
        return self.df.utils.styler.set_caption(self.title)._repr_html_()

    def _repr_latex_(
        self,
    ) -> str:
        return self.df.utils.styler.set_caption(self.title)._repr_latex_()

    def _repr_mimebundle_(
        self,
        include: None = None,  # noqa: ARG002
        exclude: None = None,  # noqa: ARG002
    ) -> dict[str, str]:
        return {
            "text/html": self.df._repr_html_(),  # pyright: ignore[reportCallIssue]  # ty:ignore[call-non-callable]
            "text/plain": repr(self.df),
        }

    def update_values(
        self,
        values: list[list[Any]],
        /,
        *,
        sheet_range: str,
        as_user: bool = True,
    ) -> Self:
        """Write ``values`` to ``range`` and refresh the local metadata.

        Parameters
        ----------
        range : str
            Fully qualified A1-style range *including* the sheet prefix
            (for example ``"Sheet1!A1:C3"``).
        values : list of list of Any
            Row-major 2D list of values to write. Inner lists correspond
            to spreadsheet rows.
        as_user : bool, default True
            When ``True``, values are parsed the way a human typing into
            the UI would enter them (``USER_ENTERED`` — formulas are
            evaluated, dates/numbers are auto-typed). When ``False``, the
            values are written verbatim (``RAW``).

        Returns
        -------
        Self
            The same :class:`Sheet` instance with its cached
            ``internal`` payload refreshed to reflect the remote state.
        """
        self.parent = self.parent.update_values(
            values,
            sheet_range=sheet_range,
            as_user=as_user,
        )

        self.internal = self.parent.sheet(self.index + 1).internal

        return self

    def insert(
        self,
        values: list[list[Any]],
        /,
        *,
        sheet_range: str | None,
        as_user: bool = True,
    ) -> Self:
        """Write ``values`` into this sheet, defaulting the anchor to ``A1``.

        Parameters
        ----------
        range : str or None
            A1-style range *without* the sheet prefix indicating the
            top-left anchor of the write (for example ``"B2"``). When
            ``None``, ``A1`` is used.
        values : list of list of Any
            Row-major 2D list of values to write.
        as_user : bool, default True
            If ``True``, values are interpreted as ``USER_ENTERED``
            (formulas evaluated); otherwise they are written ``RAW``.

        Returns
        -------
        Self
            The same :class:`Sheet` instance with refreshed metadata.
        """
        return self.update_values(
            values,
            sheet_range=f"{self.title}!{'A1' if sheet_range is None else sheet_range}",
            as_user=as_user,
        )

    def insert_df(
        self,
        df: DataFrame,
        /,
        *,
        sheet_range: str | None,
        as_user: bool = True,
        index_name: str = "Index",
    ) -> Self:
        """Write a pandas DataFrame (with its index) into the sheet.

        The DataFrame's index is promoted to a regular column named
        ``index_name`` before writing, and the column names are inserted
        as the header row.

        Parameters
        ----------
        range : str or None
            A1-style range *without* the sheet prefix indicating the
            top-left anchor of the write. When ``None``, ``A1`` is used.
        df : DataFrame
            Pandas DataFrame to materialise into the sheet. Its index is
            reset with ``names=index_name`` prior to writing.
        as_user : bool, default True
            If ``True``, values are interpreted as ``USER_ENTERED``;
            otherwise they are written ``RAW``.
        index_name : str, default 'Index'
            Column name assigned to the DataFrame's index when promoting
            it to a column.

        Returns
        -------
        Self
            The same :class:`Sheet` instance with refreshed metadata.
        """
        df_with_index = df.reset_index(names=index_name)

        return self.update_values(
            [df_with_index.columns.to_list(), *df_with_index.to_numpy().tolist()],
            sheet_range=f"{self.title}!{'A1' if sheet_range is None else sheet_range}",
            as_user=as_user,
        )

    # TODO(@mayurankv): Insert values, Insert formula  # noqa: TD003


class Sheets:
    """Google Sheets spreadsheet wrapper.

    Represents an entire spreadsheet (a Drive file) and exposes methods
    for managing its tabs (create, copy, move, rename, delete), reading
    and writing data, and round-tripping DataFrames. Instances are
    constructed via the ``fresh_from_creds``, ``retrieve_from_id``,
    ``retrieve_from_name``, ``create_new`` or ``create_from_template``
    classmethods rather than directly.

    Parameters
    ----------
    sheets : Spreadsheet
        Raw spreadsheet payload returned by the Sheets API, containing
        at minimum the ``spreadsheetId``, ``properties`` and ``sheets``
        keys.
    sheets_service : SheetsResource
        Authenticated Google Sheets API service client used for all
        read/write/batch operations against the spreadsheet.
    """

    def __init__(
        self,
        sheets: Spreadsheet,
        /,
        *,
        sheets_service: SheetsResource,
    ) -> None:
        self.service: SheetsResource = sheets_service
        self.internal: Spreadsheet = sheets
        self.id: str = self.internal["spreadsheetId"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def _internal_sheets(
        self,
    ) -> list[SheetSchema]:
        """Return the raw ``sheets`` list from the spreadsheet payload."""
        return self.internal["sheets"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def link(
        self,
    ) -> str:
        """Shareable browser URL for the spreadsheet.

        Returns
        -------
        str
            ``https://docs.google.com/spreadsheets/d/<id>/edit`` URL
            constructed from the spreadsheet ID.
        """
        return f"https://docs.google.com/spreadsheets/d/{self.id}/edit"

    def sheet(
        self,
        sheet_number: int,
        /,
    ) -> Sheet:
        """Return the :class:`Sheet` at a 1-indexed position.

        Parameters
        ----------
        sheet_number : int
            1-indexed tab position (1 = leftmost tab).

        Returns
        -------
        Sheet
            Wrapper around the sheet entry at the requested position.

        Raises
        ------
        IndexError
            If ``sheet_number`` is less than 1 or greater than the number
            of sheets in the spreadsheet.
        """
        if sheet_number < 1 or sheet_number > len(self._internal_sheets):
            msg = f"Sheet number {sheet_number} is out of range. Spreadsheet has {len(self._internal_sheets)} sheets."
            raise IndexError(msg)

        sheet_internal = self._internal_sheets[sheet_number - 1]

        return Sheet(
            sheet_internal,
            parent=self,
            sheets_service=self.service,
        )

    def sheet_from_name(
        self,
        sheet_name: str,
        /,
    ) -> Sheet:
        """Return the :class:`Sheet` whose tab title matches ``sheet_name``.

        Parameters
        ----------
        sheet_name : str
            Exact tab title to look up (case-sensitive).

        Returns
        -------
        Sheet
            Wrapper around the first sheet whose ``properties.title``
            equals ``sheet_name``.

        Raises
        ------
        ValueError
            If no sheet in the spreadsheet has the given title.
        """
        sheet_number = next(
            (idx + 1 for idx, sheet in enumerate(self._internal_sheets) if sheet.get("properties", {}).get("title", "") == sheet_name),
            None,
        )

        if sheet_number is None:
            msg = f"Sheet with title '{sheet_name}' not found."
            raise ValueError(msg)

        return self.sheet(sheet_number)

    @property
    def sheets(
        self,
    ) -> list[Sheet]:
        """All sheets in the spreadsheet in display order.

        Returns
        -------
        list of Sheet
            :class:`Sheet` wrappers for every tab, ordered left-to-right
            as they appear in the UI.
        """
        return [self.sheet(sheet_idx + 1) for sheet_idx in range(len(self._internal_sheets))]

    @property
    def title(
        self,
    ) -> str:
        """Title of the spreadsheet file as stored in Drive.

        Returns
        -------
        str
            Spreadsheet-level title from ``properties.title``.
        """
        return self.internal["properties"]["title"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    def open(
        self,
    ) -> None:
        """Open the spreadsheet in the system default web browser.

        Notes
        -----
        Uses :func:`webbrowser.open` on :attr:`link`; no authentication
        handshake is performed.
        """
        webbrowser.open(url=self.link)

    def __repr__(
        self,
    ) -> str:
        """Represent using the first sheet using ``repr``.

        Returns
        -------
        str
            ``repr`` of the first tab rendered as a DataFrame, used as a
            concise preview of the spreadsheet.
        """
        return self.sheet(1).__repr__()

    def _repr_html_(
        self,
    ) -> str:
        return self.sheet(1)._repr_html_()  # pyright: ignore[reportPrivateUsage]

    def _repr_latex_(
        self,
    ) -> str:
        return self.sheet(1)._repr_latex_()  # pyright: ignore[reportPrivateUsage]

    def _repr_mimebundle_(
        self,
        include: None = None,
        exclude: None = None,
    ) -> dict[str, str]:
        return self.sheet(1)._repr_mimebundle_(  # pyright: ignore[reportPrivateUsage]
            include=include,
            exclude=exclude,
        )

    def refresh(
        self,
    ) -> Self:
        """Re-fetch the remote spreadsheet metadata into ``self.internal``.

        Returns
        -------
        Self
            The same instance, after its cached ``internal`` payload has
            been replaced with a freshly fetched copy from the Sheets
            API. Used after any mutating operation to keep local state
            consistent.
        """
        self.internal = self.service.spreadsheets().get(spreadsheetId=self.id).execute()

        return self

    def update(
        self,
        requests: list[SheetsRequest],
        /,
    ) -> Self:
        """Apply a batch of Sheets API request dicts.

        Parameters
        ----------
        requests : list of SheetsRequest
            Sequence of raw request bodies in the ``batchUpdate`` format
            (each entry is one of ``addSheet``, ``updateSheetProperties``,
            ``deleteSheet``, etc.). If empty, the API call is skipped.

        Returns
        -------
        Self
            The same instance, with :meth:`refresh` already invoked so
            that subsequent reads see the post-update state.
        """
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
        values: list[list[Any]],
        /,
        *,
        sheet_range: str,
        as_user: bool = True,
    ) -> Self:
        """Write ``values`` to ``range`` on the spreadsheet.

        Parameters
        ----------
        range : str
            Fully qualified A1-style range *including* the sheet prefix
            (for example ``"Sheet1!A1:C3"``).
        values : list of list of Any
            Row-major 2D list of values to write.
        as_user : bool, default True
            When ``True``, uses ``valueInputOption=USER_ENTERED`` so
            strings like ``"1/1/2024"`` or ``"=A1+1"`` are parsed as
            dates/formulas. When ``False``, uses ``RAW`` so values are
            stored verbatim.

        Returns
        -------
        Self
            The same instance, refreshed so that ``self.internal``
            reflects the updated spreadsheet state.
        """
        self.service.spreadsheets().values().update(
            spreadsheetId=self.id,
            range=sheet_range,
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
        /,
    ) -> SheetsResource:
        """Build a Google Sheets v4 API service client.

        Parameters
        ----------
        creds : Credentials
            OAuth 2.0 credentials authorised for at least the
            ``spreadsheets`` scope.

        Returns
        -------
        SheetsResource
            Authenticated ``sheets v4`` API client produced by
            :func:`googleapiclient.discovery.build`.
        """
        sheets_service: SheetsResource = build(  # pyright: ignore[reportUnknownVariableType]
            serviceName="sheets",
            version="v4",
            credentials=creds,
        )

        return sheets_service  # pyright: ignore[reportUnknownVariableType]

    @classmethod
    def fresh_from_creds(
        cls,
        sheets_name: str,
        /,
        *,
        creds: Credentials,
        template: str | None = None,
    ) -> Self:
        """Get an existing spreadsheet by name or create one if missing.

        Looks the file up on Drive by name; if found, retrieves it,
        otherwise creates a blank spreadsheet (or copies ``template`` if
        provided).

        Parameters
        ----------
        sheets_name : str
            Desired Drive filename of the spreadsheet to retrieve or
            create.
        creds : Credentials
            OAuth 2.0 credentials authorised for Drive and Sheets.
        template : str or None, default None
            Drive filename of a template spreadsheet to clone when no
            spreadsheet named ``sheets_name`` yet exists. When ``None``,
            a blank spreadsheet is created.

        Returns
        -------
        Self
            :class:`Sheets` wrapping either the pre-existing file or the
            newly created/copied one.
        """
        return cls.get(
            sheets_name,
            drive=Drive.from_creds(creds),
            sheets_service=cls.service_from_creds(creds),
            template=template,
        )

    @classmethod
    def retrieve_from_id(
        cls,
        sheets_id: str,
        /,
        *,
        sheets_service: SheetsResource,
    ) -> Self:
        """Fetch an existing spreadsheet by Drive file ID.

        Parameters
        ----------
        sheets_id : str
            Drive file ID of the target spreadsheet (the opaque string
            between ``/d/`` and ``/edit`` in the browser URL).
        sheets_service : SheetsResource
            Authenticated Sheets API service client.

        Returns
        -------
        Self
            :class:`Sheets` wrapping the retrieved spreadsheet metadata.
        """
        sheets: Spreadsheet = (
            sheets_service.spreadsheets()
            .get(
                spreadsheetId=sheets_id,
            )
            .execute()
        )

        return cls(
            sheets,
            sheets_service=sheets_service,
        )

    @classmethod
    def retrieve_from_name(
        cls,
        sheets_name: str,
        /,
        *,
        drive: Drive,
        sheets_service: SheetsResource,
    ) -> Self:
        """Fetch an existing spreadsheet by its Drive filename.

        Parameters
        ----------
        sheets_name : str
            Drive filename of the target spreadsheet.
        drive : Drive
            Drive wrapper used to resolve the filename to a file ID.
        sheets_service : SheetsResource
            Authenticated Sheets API service client.

        Returns
        -------
        Self
            :class:`Sheets` wrapping the retrieved spreadsheet metadata.

        Raises
        ------
        FileNotFoundError
            Propagated from :meth:`Drive.find_file_id` when no Drive file
            with the given name exists.
        """
        sheets_id: str = drive.find_file_id(sheets_name)

        return cls.retrieve_from_id(
            sheets_id,
            sheets_service=sheets_service,
        )

    @classmethod
    def create_new(
        cls,
        sheets_name: str,
        /,
        *,
        sheets_service: SheetsResource,
    ) -> Self:
        """Create a new blank spreadsheet with the given title.

        Parameters
        ----------
        sheets_name : str
            Title to assign to the newly created spreadsheet. Also acts
            as the Drive filename.
        sheets_service : SheetsResource
            Authenticated Sheets API service client.

        Returns
        -------
        Self
            :class:`Sheets` wrapping the freshly created, empty
            spreadsheet (one default ``Sheet1`` tab).
        """
        sheets_internal: Spreadsheet = (
            sheets_service.spreadsheets()
            .create(
                body={
                    "properties": {"title": sheets_name},
                },
            )
            .execute()
        )

        return cls(
            sheets_internal,
            sheets_service=sheets_service,
        )

    @classmethod
    def create_from_template(
        cls,
        sheets_name: str,
        /,
        *,
        template_name: str,
        drive: Drive,
        sheets_service: SheetsResource,
    ) -> Self:
        """Create a spreadsheet by copying a template file.

        Resolves ``template_name`` to a Drive file ID and calls Drive's
        ``files.copy`` with the new filename.

        Parameters
        ----------
        sheets_name : str
            Title of the newly created copy.
        template_name : str
            Drive filename of the source template spreadsheet.
        drive : Drive
            Drive wrapper used to resolve the template name and perform
            the copy.
        sheets_service : SheetsResource
            Authenticated Sheets API service client attached to the
            returned :class:`Sheets` instance.

        Returns
        -------
        Self
            :class:`Sheets` wrapping the copied spreadsheet.
        """
        template_id: str = drive.find_file_id(template_name)

        copied_file = (
            drive.files()
            .copy(
                fileId=template_id,
                body={
                    "name": sheets_name,
                },
            )
            .execute()
        )

        return cls.retrieve_from_id(
            copied_file["id"],  # pyright: ignore[reportTypedDictNotRequiredAccess]
            sheets_service=sheets_service,
        )

    @classmethod
    def get(
        cls,
        sheets_name: str,
        /,
        *,
        drive: Drive,
        sheets_service: SheetsResource,
        template: str | None = None,
    ) -> Self:
        """Retrieve a spreadsheet by name, creating it if it does not exist.

        Parameters
        ----------
        sheets_name : str
            Drive filename to look up and, if absent, to create.
        drive : Drive
            Drive wrapper used for name resolution and template copying.
        sheets_service : SheetsResource
            Authenticated Sheets API service client.
        template : str or None, default None
            Drive filename of a template spreadsheet to clone if
            ``sheets_name`` does not exist. When ``None``, a blank
            spreadsheet is created instead.

        Returns
        -------
        Self
            :class:`Sheets` wrapping the resolved (or newly created)
            spreadsheet.
        """
        try:
            return cls.retrieve_from_name(
                sheets_name,
                drive=drive,
                sheets_service=sheets_service,
            )

        except FileNotFoundError:
            if template is None:
                return cls.create_new(
                    sheets_name,
                    sheets_service=sheets_service,
                )
            return cls.create_from_template(
                sheets_name,
                template_name=template,
                drive=drive,
                sheets_service=sheets_service,
            )

    def reset(
        self,
        drive: Drive,
        /,
    ) -> Self:
        """Delete and recreate the spreadsheet to clear all content.

        The existing Drive file is deleted and a new blank spreadsheet
        with the same title is created in its place. The instance's
        ``internal`` and ``id`` attributes are updated in-place.

        Parameters
        ----------
        drive : Drive
            Drive wrapper used to delete the underlying file.

        Returns
        -------
        Self
            The same instance, now pointing at the fresh, empty
            spreadsheet.
        """
        sheets_name = self.title

        drive.delete_file_by_id(self.id)

        new_sheets = self.create_new(
            sheets_name,
            sheets_service=self.service,
        )

        self.internal = new_sheets.internal
        self.id = new_sheets.id

        return self

    def rename_sheet(
        self,
        sheet: Sheet,
        /,
        *,
        new_title: str,
    ) -> Self:
        """Rename a tab within the spreadsheet.

        Parameters
        ----------
        sheet : Sheet
            Tab whose title should be changed.
        new_title : str
            New tab title. Must not collide with any existing tab title
            in the same spreadsheet.

        Returns
        -------
        Self
            The same instance, refreshed after the rename.

        Raises
        ------
        ValueError
            If another tab in the spreadsheet already uses
            ``new_title``.
        """
        if new_title in [sheet.title for sheet in self.sheets]:
            msg = f"Sheet title {new_title} is already used"
            raise ValueError(msg)

        return self.update(
            [
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
        /,
        *,
        to_position: int | None = None,
    ) -> Self:
        """Move a tab to a new position in the tab bar.

        Parameters
        ----------
        sheet : Sheet
            Tab to reposition.
        to_position : int or None, default None
            1-indexed destination position. When ``None``, the tab is
            moved to the rightmost slot.

        Returns
        -------
        Self
            The same instance, refreshed after the move.

        Raises
        ------
        IndexError
            If the computed zero-based target index falls outside
            ``[0, number_of_sheets)``.
        """
        target_index = (len(self.sheets) if to_position is None else to_position) - 1
        if target_index < 0 or target_index >= len(self.sheets):
            msg = f"Target position {target_index + 1} is out of range. Spreadsheet has {len(self.sheets)} sheets."
            raise IndexError(msg)

        return self.update(
            [
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
        *,
        sheet: Sheet | None = None,
        new_title: str | None = None,
        to_position: int | None = None,
    ) -> Self:
        """Duplicate a tab within the spreadsheet.

        The source tab is copied into the same spreadsheet; the copy can
        optionally be renamed and/or repositioned in a single batch
        update.

        Parameters
        ----------
        sheet : Sheet or None, default None
            Tab to duplicate. When ``None``, defaults to the last tab,
            but note that ``to_position`` then must also be ``None``.
        new_title : str or None, default None
            Title to apply to the new copy. When ``None``, the Sheets
            API assigns a default ``"Copy of ..."`` name. Must not
            collide with existing tab titles.
        to_position : int or None, default None
            1-indexed destination position for the copy. When ``None``,
            the copy is placed in its default position (end of the tab
            list). Requires ``sheet`` to be provided.

        Returns
        -------
        Self
            The same instance, refreshed after the copy/rename/move.

        Raises
        ------
        ValueError
            If ``to_position`` is provided while ``sheet`` is ``None``,
            or if ``new_title`` collides with an existing tab title.
        IndexError
            If the resolved source or target positions fall outside the
            valid range for the current spreadsheet.
        """
        if to_position is not None and sheet is None:
            msg = "If 'to_position' is specified, 'sheet' must also be specified."
            raise ValueError(msg)

        sheet_number = len(self.sheets) if sheet is None else sheet.index + 1

        if sheet_number < 1 or sheet_number > len(self.sheets):
            msg = f"Sheet number {sheet_number} is out of range. Spreadsheet has {len(self.sheets)} sheets."
            raise IndexError(msg)

        target_index = len(self.sheets) if to_position is None else (to_position - 1)
        if target_index < 0 or target_index > len(self.sheets):
            msg = f"Target position {target_index + 1} is out of range. Spreadsheet has {len(self.sheets)} sheets."
            raise IndexError(msg)

        sheet_id = self.sheet(sheet_number).id

        if new_title is not None and new_title in [sheet.title for sheet in self.sheets]:
            msg = f"Sheet title {new_title} is already used"
            raise ValueError(msg)

        new_sheet_id: int = (  # pyright: ignore[reportUnknownVariableType]
            self.service.spreadsheets()
            .sheets()
            .copyTo(  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
                spreadsheetId=self.id,
                sheetId=sheet_id,
                body={"destinationSpreadsheetId": self.id},
            )
            .execute()["sheetId"]
        )

        requests: list[SheetsRequest] = []
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

        return self.update(requests)

    def delete_sheet(
        self,
        sheet: Sheet,
        /,
    ) -> Self:
        """Remove a tab from the spreadsheet.

        Parameters
        ----------
        sheet : Sheet
            Tab to delete. The spreadsheet must retain at least one tab
            afterwards — the Sheets API will reject requests that
            remove the only remaining sheet.

        Returns
        -------
        Self
            The same instance, refreshed after the deletion.
        """
        requests: list[SheetsRequest] = [
            {
                "deleteSheet": {
                    "sheetId": sheet.id,
                }
            }
        ]

        return self.update(requests)

    def insert_sheet(
        self,
        *,
        new_title: str | None = None,
        to_position: int | None = None,
    ) -> Self:
        """Add a new blank tab to the spreadsheet.

        Parameters
        ----------
        new_title : str or None, default None
            Title for the new tab. When ``None``, Google assigns the
            default ``SheetN`` name. Must not collide with existing tab
            titles.
        to_position : int or None, default None
            1-indexed position at which to insert the tab. When ``None``,
            the tab is appended at the end.

        Returns
        -------
        Self
            The same instance, refreshed so ``self.sheets`` includes the
            new tab.

        Raises
        ------
        IndexError
            If ``to_position`` resolves to a zero-based index outside
            ``[0, number_of_sheets]``.
        ValueError
            If ``new_title`` is already used by another tab.
        """
        target_index = len(self.sheets) if to_position is None else (to_position - 1)
        if target_index < 0 or target_index > len(self.sheets):
            msg = f"Target position {target_index + 1} is out of range. Spreadsheet has {len(self.sheets)} sheets."
            raise IndexError(msg)

        if new_title is not None and new_title in [sheet.title for sheet in self.sheets]:
            msg = f"Sheet title {new_title} is already used"
            raise ValueError(msg)

        sheet_properties: SheetProperties = {}
        if to_position is not None:
            sheet_properties["index"] = target_index

        if new_title is not None:
            sheet_properties["title"] = new_title

        requests: list[SheetsRequest] = [
            {
                "addSheet": {
                    "properties": sheet_properties,
                }
            }
        ]

        return self.update(requests)

    def add_sheet_from_dataframe(
        self,
        df: DataFrame,
        /,
        *,
        new_title: str | None = None,
        to_position: int | None = None,
        as_user: bool = False,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        """Create a new tab and populate it from a pandas DataFrame.

        Wraps :meth:`insert_sheet` followed by
        :meth:`Sheet.insert_df` anchored at ``A1`` on the newly inserted
        tab.

        Parameters
        ----------
        df : DataFrame
            Pandas DataFrame whose contents (header + index + values)
            should populate the new tab.
        new_title : str or None, default None
            Title for the new tab. When ``None``, Google assigns a
            default name.
        to_position : int or None, default None
            1-indexed position at which to insert the new tab. When
            ``None``, the tab is appended at the end.
        as_user : bool, default False
            Passed through to :meth:`Sheet.insert_df`. When ``True``,
            values are parsed as ``USER_ENTERED``; otherwise written
            ``RAW``.
        **kwargs
            Additional keyword arguments forwarded to
            :meth:`Sheet.insert_df` (for example ``index_name``).

        Returns
        -------
        Self
            The same instance, refreshed so ``self.internal`` mirrors
            the post-insert state.
        """
        self.insert_sheet(
            new_title=new_title,
            to_position=to_position,
        )

        sheet = self.sheet(len(self.sheets) if to_position is None else to_position).insert_df(
            df,
            sheet_range=None,
            as_user=as_user,
            **kwargs,
        )

        self.internal = sheet.parent.internal  # pyright: ignore[reportUnknownMemberType]

        return self
