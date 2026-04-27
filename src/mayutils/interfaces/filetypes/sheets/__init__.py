"""
Provide Google Sheets spreadsheet and sheet wrapper classes.

Expose object-oriented wrappers around the Google Sheets v4 REST API so
spreadsheets and individual tabs can be treated as Python objects that
round-trip to pandas DataFrames. The :class:`Sheets` class manages
spreadsheet-level operations (creation, retrieval, sheet CRUD) while
:class:`Sheet` represents a single tab and supports range-based reads
and writes. Drive integration is used to resolve spreadsheets by file
name and to copy from template files when bootstrapping new sheets.

See Also
--------
mayutils.interfaces.cloud.google.Drive : Drive API wrapper used for file lookup and copy.
mayutils.interfaces.filetypes.xlsx.Xlsx : XLSX helper reused for A1-style column conversion.

Examples
--------
>>> from mayutils.interfaces.filetypes.sheets import Sheets
>>> sheets = Sheets.fresh_from_creds(  # doctest: +SKIP
...     "My Report",
...     creds=creds,
... )
>>> df = sheets.sheet(1).to_pandas()  # doctest: +SKIP
"""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING, Self

from mayutils.core.extras import may_require_extras
from mayutils.interfaces.cloud.google import Drive
from mayutils.interfaces.filetypes.xlsx import Xlsx

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
    """
    Represent a single tab within a Google Sheets spreadsheet.

    Wrap the Google Sheets API representation of one tab and offer
    helpers for reading its contents as a pandas DataFrame and writing
    values (including whole DataFrames) back to specific ranges. Each
    instance keeps a reference to its parent :class:`Sheets` so writes
    can refresh the cached spreadsheet metadata after execution, and
    surfaces convenience properties for the tab's title, index and
    grid dimensions without re-fetching from the remote API.

    Parameters
    ----------
    sheet
        Raw ``sheets[i]`` entry returned by the Sheets API, containing
        the ``properties`` block (``sheetId``, ``title``, ``index``,
        ``gridProperties``).
    parent
        Owning spreadsheet wrapper used to issue batch updates and to
        re-fetch sheet metadata after writes.
    sheets_service
        Authenticated Google Sheets API service client used to issue
        read and write requests against the spreadsheet.

    See Also
    --------
    Sheets : Spreadsheet-level wrapper that owns instances of this class.
    mayutils.interfaces.filetypes.xlsx.Xlsx : Excel helpers reused for column conversion.

    Examples
    --------
    >>> from mayutils.interfaces.filetypes.sheets import Sheet, Sheets
    >>> sheets = Sheets.fresh_from_creds("My Report", creds=creds)  # doctest: +SKIP
    >>> sheet = sheets.sheet(1)  # doctest: +SKIP
    >>> sheet.title  # doctest: +SKIP
    'Sheet1'
    >>> sheet.to_pandas()  # doctest: +SKIP
    """

    def __init__(
        self,
        sheet: SheetSchema,
        /,
        *,
        parent: Sheets,
        sheets_service: SheetsResource,
    ) -> None:
        """
        Initialise the sheet wrapper from a raw API payload.

        Store the supplied sheet payload and service client on the
        instance and eagerly extract the numeric ``sheetId`` so later
        operations can reference it without repeatedly indexing into
        the raw dict. The parent :class:`Sheets` is retained so that
        mutating calls can trigger metadata refreshes on the owner.

        Parameters
        ----------
        sheet
            Raw ``sheets[i]`` entry from the Sheets API payload.
        parent
            Owning spreadsheet wrapper used for batch updates and
            refreshes after writes.
        sheets_service
            Authenticated Google Sheets API service client.

        See Also
        --------
        Sheets.sheet : Factory method that constructs Sheet instances.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheet, Sheets
        >>> service = MagicMock()
        >>> spreadsheet = Sheets(
        ...     {
        ...         "spreadsheetId": "abc",
        ...         "properties": {"title": "My Report"},
        ...         "sheets": [
        ...             {
        ...                 "properties": {
        ...                     "sheetId": 0,
        ...                     "title": "Sheet1",
        ...                     "index": 0,
        ...                     "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...                 }
        ...             }
        ...         ],
        ...     },
        ...     sheets_service=service,
        ... )
        >>> sheet = spreadsheet.sheet(1)
        >>> isinstance(sheet, Sheet)
        True
        """
        self.service: SheetsResource = sheets_service
        self.internal: SheetSchema = sheet
        self.id: int = self._properties["sheetId"]  # pyright: ignore[reportTypedDictNotRequiredAccess]
        self.parent = parent

    @property
    def _properties(
        self,
    ) -> SheetProperties:
        """
        Return the ``properties`` block from the raw sheet payload.

        Expose the nested ``properties`` dict stored on the Sheets API
        response so sibling properties can delegate to it without
        repeating the typed-dict indexing. The returned mapping
        contains ``sheetId``, ``title``, ``index`` and
        ``gridProperties``.

        Returns
        -------
            Mapping extracted from ``self.internal["properties"]``.

        See Also
        --------
        Sheet.title : Reads ``properties.title``.
        Sheet.index : Reads ``properties.index``.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> spreadsheet = Sheets(
        ...     {
        ...         "spreadsheetId": "abc",
        ...         "properties": {"title": "My Report"},
        ...         "sheets": [
        ...             {
        ...                 "properties": {
        ...                     "sheetId": 0,
        ...                     "title": "Sheet1",
        ...                     "index": 0,
        ...                     "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...                 }
        ...             }
        ...         ],
        ...     },
        ...     sheets_service=MagicMock(),
        ... )
        >>> sheet = spreadsheet.sheet(1)
        >>> sheet._properties["title"]
        'Sheet1'
        """
        return self.internal["properties"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def title(
        self,
    ) -> str:
        """
        Return the title of the sheet tab as shown in the UI.

        Read the human-readable tab title from the cached
        ``properties.title`` field. The value reflects the last
        successful metadata fetch, so after renames the caller should
        call :meth:`Sheets.refresh` (or a mutating method that already
        refreshes) before relying on the title.

        Returns
        -------
            Tab title stored on the sheet's ``properties.title`` field.

        See Also
        --------
        Sheets.rename_sheet : Renames a tab and refreshes metadata.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> spreadsheet = Sheets(
        ...     {
        ...         "spreadsheetId": "abc",
        ...         "properties": {"title": "My Report"},
        ...         "sheets": [
        ...             {
        ...                 "properties": {
        ...                     "sheetId": 0,
        ...                     "title": "Sheet1",
        ...                     "index": 0,
        ...                     "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...                 }
        ...             }
        ...         ],
        ...     },
        ...     sheets_service=MagicMock(),
        ... )
        >>> sheet = spreadsheet.sheet(1)
        >>> sheet.title
        'Sheet1'
        """
        return self._properties["title"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def index(
        self,
    ) -> int:
        """
        Return the zero-based position of the tab in its spreadsheet.

        Read ``properties.index`` which corresponds to the display
        order of tabs in the Google Sheets UI where ``0`` is the
        leftmost tab. Note that many API surfaces (and this wrapper's
        :meth:`Sheets.sheet`) use 1-indexed positions instead, so
        consumers should add one when converting.

        Returns
        -------
            Zero-based display index; ``0`` is the leftmost tab.

        See Also
        --------
        Sheets.move_sheet : Mutates the index by reordering tabs.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> spreadsheet = Sheets(
        ...     {
        ...         "spreadsheetId": "abc",
        ...         "properties": {"title": "My Report"},
        ...         "sheets": [
        ...             {
        ...                 "properties": {
        ...                     "sheetId": 0,
        ...                     "title": "Sheet1",
        ...                     "index": 0,
        ...                     "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...                 }
        ...             }
        ...         ],
        ...     },
        ...     sheets_service=MagicMock(),
        ... )
        >>> sheet = spreadsheet.sheet(1)
        >>> sheet.index
        0
        """
        return self._properties["index"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def rows(
        self,
    ) -> int:
        """
        Return the total number of rows allocated in the grid.

        Read ``properties.gridProperties.rowCount``, which includes
        blank trailing rows allocated by the grid and not just rows
        containing values. This is primarily useful when constructing
        default read ranges that span the full grid.

        Returns
        -------
            Row count reported by ``properties.gridProperties.rowCount``.

        See Also
        --------
        Sheet.columns : Sibling property returning column count.
        Sheet.to_arrays : Uses this value to build the default range.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> spreadsheet = Sheets(
        ...     {
        ...         "spreadsheetId": "abc",
        ...         "properties": {"title": "My Report"},
        ...         "sheets": [
        ...             {
        ...                 "properties": {
        ...                     "sheetId": 0,
        ...                     "title": "Sheet1",
        ...                     "index": 0,
        ...                     "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...                 }
        ...             }
        ...         ],
        ...     },
        ...     sheets_service=MagicMock(),
        ... )
        >>> sheet = spreadsheet.sheet(1)
        >>> sheet.rows
        1000
        """
        return self._properties["gridProperties"]["rowCount"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def columns(
        self,
    ) -> int:
        """
        Return the total number of columns allocated in the grid.

        Read ``properties.gridProperties.columnCount``, including blank
        trailing columns allocated by the grid, not merely those with
        values. Combined with :attr:`rows` this yields the bounds of
        the default A1 read range.

        Returns
        -------
            Column count reported by
            ``properties.gridProperties.columnCount``.

        See Also
        --------
        Sheet.rows : Sibling property returning row count.
        Sheet.to_arrays : Uses this value to build the default range.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> spreadsheet = Sheets(
        ...     {
        ...         "spreadsheetId": "abc",
        ...         "properties": {"title": "My Report"},
        ...         "sheets": [
        ...             {
        ...                 "properties": {
        ...                     "sheetId": 0,
        ...                     "title": "Sheet1",
        ...                     "index": 0,
        ...                     "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...                 }
        ...             }
        ...         ],
        ...     },
        ...     sheets_service=MagicMock(),
        ... )
        >>> sheet = spreadsheet.sheet(1)
        >>> sheet.columns
        26
        """
        return self._properties["gridProperties"]["columnCount"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    def to_arrays(
        self,
        *,
        sheet_range: str | None = None,
    ) -> list[list[object]]:
        """
        Fetch raw cell values from the sheet as a 2D list.

        Call the Sheets ``values.get`` endpoint to pull cell values
        from the tab. When ``sheet_range`` is ``None`` the full grid
        from ``A1`` to the bottom-right cell (inferred from
        :attr:`rows` and :attr:`columns`) is requested. The API may
        truncate trailing empty cells or rows.

        Parameters
        ----------
        sheet_range
            A1-style range without the sheet prefix (for example
            ``"B2:D10"``). When ``None``, the full grid is fetched.

        Returns
        -------
            List of rows where each row is a list of cell values
            returned by the Sheets API.

        See Also
        --------
        Sheet.to_pandas : Returns the same data as a DataFrame.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> service = MagicMock()
        >>> service.spreadsheets().values().get().execute.return_value = {
        ...     "values": [["header1", "header2"], ["a", "b"]],
        ... }
        >>> spreadsheet = Sheets(
        ...     {
        ...         "spreadsheetId": "abc",
        ...         "properties": {"title": "My Report"},
        ...         "sheets": [
        ...             {
        ...                 "properties": {
        ...                     "sheetId": 0,
        ...                     "title": "Sheet1",
        ...                     "index": 0,
        ...                     "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...                 }
        ...             }
        ...         ],
        ...     },
        ...     sheets_service=service,
        ... )
        >>> sheet = spreadsheet.sheet(1)
        >>> sheet.to_arrays(sheet_range="A1:B2")
        [['header1', 'header2'], ['a', 'b']]
        """
        data = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=self.parent.id,
                range=f"{self.title}!A1:{Xlsx.column_to_excel(self.columns)}{self.rows}"
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
        """
        Return the sheet contents as a pandas DataFrame.

        Delegate to :meth:`to_arrays` and wrap the resulting 2D list
        with :class:`pandas.DataFrame`. No header inference is
        performed, so the first row remains data; callers should
        promote it manually if a header row is expected.

        Parameters
        ----------
        sheet_range
            A1-style range without the sheet prefix to restrict the
            read. When ``None``, the full grid is returned.

        Returns
        -------
            Pandas DataFrame of the raw cell values returned by
            :meth:`to_arrays`.

        See Also
        --------
        Sheet.to_arrays : Underlying list-of-lists accessor.
        Sheet.df : Property form for fetching the full sheet.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from pandas import DataFrame
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> service = MagicMock()
        >>> service.spreadsheets().values().get().execute.return_value = {
        ...     "values": [["header1", "header2"], ["a", "b"]],
        ... }
        >>> spreadsheet = Sheets(
        ...     {
        ...         "spreadsheetId": "abc",
        ...         "properties": {"title": "My Report"},
        ...         "sheets": [
        ...             {
        ...                 "properties": {
        ...                     "sheetId": 0,
        ...                     "title": "Sheet1",
        ...                     "index": 0,
        ...                     "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...                 }
        ...             }
        ...         ],
        ...     },
        ...     sheets_service=service,
        ... )
        >>> sheet = spreadsheet.sheet(1)
        >>> isinstance(sheet.to_pandas(sheet_range="A1:B2"), DataFrame)
        True
        """
        return DataFrame(data=self.to_arrays(sheet_range=sheet_range))

    def to_polars(
        self,
        *,
        sheet_range: str | None = None,
    ) -> pl.DataFrame:
        """
        Return the sheet contents as a polars DataFrame.

        Placeholder method that will in future convert the sheet's raw
        cell values into a :class:`polars.DataFrame`. The signature is
        fixed so callers can write against it today, but the body
        unconditionally raises ``NotImplementedError`` until the
        conversion is wired up.

        Parameters
        ----------
        sheet_range
            A1-style range without the sheet prefix to restrict the
            read. When ``None``, the full grid is returned.

        Raises
        ------
        NotImplementedError
            Always raised until polars support has been implemented.

        See Also
        --------
        Sheet.to_pandas : Equivalent pandas-backed accessor.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> spreadsheet = Sheets(
        ...     {
        ...         "spreadsheetId": "abc",
        ...         "properties": {"title": "My Report"},
        ...         "sheets": [
        ...             {
        ...                 "properties": {
        ...                     "sheetId": 0,
        ...                     "title": "Sheet1",
        ...                     "index": 0,
        ...                     "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...                 }
        ...             }
        ...         ],
        ...     },
        ...     sheets_service=MagicMock(),
        ... )
        >>> sheet = spreadsheet.sheet(1)
        >>> try:
        ...     sheet.to_polars()
        ... except NotImplementedError:
        ...     print("not implemented")
        not implemented
        """
        msg = "Polars not implemented yet"
        raise NotImplementedError(msg)

    @property
    def df(
        self,
    ) -> DataFrame:
        """
        Return the full sheet as a pandas DataFrame.

        Convenience property that delegates to :meth:`to_pandas` with
        ``sheet_range=None``. Useful for attribute-style access in
        notebooks and repl sessions where the caller simply wants the
        entire tab materialised.

        Returns
        -------
            Equivalent to ``self.to_pandas(sheet_range=None)``.

        See Also
        --------
        Sheet.to_pandas : Range-aware accessor that this property calls.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from pandas import DataFrame
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> service = MagicMock()
        >>> service.spreadsheets().values().get().execute.return_value = {
        ...     "values": [["header1", "header2"], ["a", "b"]],
        ... }
        >>> spreadsheet = Sheets(
        ...     {
        ...         "spreadsheetId": "abc",
        ...         "properties": {"title": "My Report"},
        ...         "sheets": [
        ...             {
        ...                 "properties": {
        ...                     "sheetId": 0,
        ...                     "title": "Sheet1",
        ...                     "index": 0,
        ...                     "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...                 }
        ...             }
        ...         ],
        ...     },
        ...     sheets_service=service,
        ... )
        >>> sheet = spreadsheet.sheet(1)
        >>> isinstance(sheet.df, DataFrame)
        True
        """
        return self.to_pandas(sheet_range=None)

    def __repr__(
        self,
    ) -> str:
        """
        Return an unambiguous representation derived from the DataFrame.

        Delegate to the pandas DataFrame ``repr`` produced from the
        full sheet so interactive environments render tabular data
        rather than an opaque object address. The output is identical
        to ``repr(self.df)`` and therefore triggers a network fetch
        on first access.

        Returns
        -------
            ``repr`` of the full sheet rendered as a pandas DataFrame.

        See Also
        --------
        Sheet.df : Underlying DataFrame accessor.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> service = MagicMock()
        >>> service.spreadsheets().values().get().execute.return_value = {
        ...     "values": [["header1", "header2"], ["a", "b"]],
        ... }
        >>> spreadsheet = Sheets(
        ...     {
        ...         "spreadsheetId": "abc",
        ...         "properties": {"title": "My Report"},
        ...         "sheets": [
        ...             {
        ...                 "properties": {
        ...                     "sheetId": 0,
        ...                     "title": "Sheet1",
        ...                     "index": 0,
        ...                     "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...                 }
        ...             }
        ...         ],
        ...     },
        ...     sheets_service=service,
        ... )
        >>> sheet = spreadsheet.sheet(1)
        >>> isinstance(repr(sheet), str)
        True
        """
        return repr(self.df)

    def _repr_html_(
        self,
    ) -> str:
        """
        Return an HTML representation for Jupyter-style front-ends.

        Build an HTML table from :attr:`df` via the pandas ``Styler``
        helper attached to mayutils DataFrames, setting the tab title
        as the caption so notebook output clearly identifies which
        sheet is being displayed.

        Returns
        -------
            HTML fragment rendered by the DataFrame styler.

        See Also
        --------
        Sheet._repr_latex_ : Latex equivalent used by Jupyter.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.objects.dataframes import setup_pandas
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> setup_pandas()
        >>> service = MagicMock()
        >>> service.spreadsheets().values().get().execute.return_value = {
        ...     "values": [["header1", "header2"], ["a", "b"]],
        ... }
        >>> spreadsheet = Sheets(
        ...     {
        ...         "spreadsheetId": "abc",
        ...         "properties": {"title": "My Report"},
        ...         "sheets": [
        ...             {
        ...                 "properties": {
        ...                     "sheetId": 0,
        ...                     "title": "Sheet1",
        ...                     "index": 0,
        ...                     "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...                 }
        ...             }
        ...         ],
        ...     },
        ...     sheets_service=service,
        ... )
        >>> sheet = spreadsheet.sheet(1)
        >>> isinstance(sheet._repr_html_(), str)
        True
        """
        return self.df.utils.styler.set_caption(self.title)._repr_html_()

    def _repr_latex_(
        self,
    ) -> str:
        """
        Return a LaTeX representation for Jupyter-style front-ends.

        Produce a LaTeX table from :attr:`df` via the pandas Styler
        helper attached to mayutils DataFrames, with the tab title
        used as the caption. Intended for Jupyter environments that
        render LaTeX MIME output such as nbconvert PDF pipelines.

        Returns
        -------
            LaTeX source rendered by the DataFrame styler.

        See Also
        --------
        Sheet._repr_html_ : HTML equivalent used by Jupyter.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.objects.dataframes import setup_pandas
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> setup_pandas()
        >>> service = MagicMock()
        >>> service.spreadsheets().values().get().execute.return_value = {
        ...     "values": [["header1", "header2"], ["a", "b"]],
        ... }
        >>> spreadsheet = Sheets(
        ...     {
        ...         "spreadsheetId": "abc",
        ...         "properties": {"title": "My Report"},
        ...         "sheets": [
        ...             {
        ...                 "properties": {
        ...                     "sheetId": 0,
        ...                     "title": "Sheet1",
        ...                     "index": 0,
        ...                     "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...                 }
        ...             }
        ...         ],
        ...     },
        ...     sheets_service=service,
        ... )
        >>> sheet = spreadsheet.sheet(1)
        >>> sheet._repr_latex_() is None or isinstance(sheet._repr_latex_(), str)
        True
        """
        return self.df.utils.styler.set_caption(self.title)._repr_latex_()

    def _repr_mimebundle_(
        self,
        include: None = None,  # noqa: ARG002
        exclude: None = None,  # noqa: ARG002
    ) -> dict[str, str]:
        """
        Return a MIME bundle with HTML and plain-text renderings.

        Emit the canonical Jupyter-compatible MIME bundle containing
        both an HTML table (from the underlying DataFrame's
        ``_repr_html_``) and a plain-text fallback (from ``repr``).
        The ``include`` and ``exclude`` parameters exist to match the
        IPython protocol but are currently ignored.

        Parameters
        ----------
        include
            Accepted for IPython compatibility; currently unused.
        exclude
            Accepted for IPython compatibility; currently unused.

        Returns
        -------
            Mapping from MIME type to rendered representation with
            keys ``"text/html"`` and ``"text/plain"``.

        See Also
        --------
        Sheet._repr_html_ : HTML-only representation.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> service = MagicMock()
        >>> service.spreadsheets().values().get().execute.return_value = {
        ...     "values": [["header1", "header2"], ["a", "b"]],
        ... }
        >>> spreadsheet = Sheets(
        ...     {
        ...         "spreadsheetId": "abc",
        ...         "properties": {"title": "My Report"},
        ...         "sheets": [
        ...             {
        ...                 "properties": {
        ...                     "sheetId": 0,
        ...                     "title": "Sheet1",
        ...                     "index": 0,
        ...                     "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...                 }
        ...             }
        ...         ],
        ...     },
        ...     sheets_service=service,
        ... )
        >>> sheet = spreadsheet.sheet(1)
        >>> bundle = sheet._repr_mimebundle_()
        >>> sorted(bundle.keys())
        ['text/html', 'text/plain']
        """
        return {
            "text/html": self.df._repr_html_(),  # pyright: ignore[reportCallIssue]  # ty:ignore[call-non-callable]
            "text/plain": repr(self.df),
        }

    def update_values(
        self,
        values: list[list[object]],
        /,
        *,
        sheet_range: str,
        as_user: bool = True,
    ) -> Self:
        """
        Write ``values`` to ``sheet_range`` and refresh local metadata.

        Forward the write request to the parent :class:`Sheets` so the
        batch executes against the spreadsheet as a whole, then swap
        in the refreshed sheet payload for this tab (looked up by
        one-based position computed from :attr:`index`) so the cached
        ``internal`` state stays consistent with the remote copy.

        Parameters
        ----------
        values
            Row-major 2D list of values to write. Inner lists
            correspond to spreadsheet rows.
        sheet_range
            Fully qualified A1-style range including the sheet prefix
            (for example ``"Sheet1!A1:C3"``).
        as_user
            When ``True``, values are parsed as ``USER_ENTERED`` so
            strings such as ``"1/1/2024"`` or ``"=A1+1"`` become dates
            or formulas. When ``False``, the values are written ``RAW``
            and stored verbatim.

        Returns
        -------
            The same :class:`Sheet` instance with its cached
            ``internal`` payload refreshed to match the remote state.

        See Also
        --------
        Sheets.update_values : Spreadsheet-level write invoked here.
        Sheet.insert : Convenience wrapper that defaults the anchor.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [
        ...         {
        ...             "properties": {
        ...                 "sheetId": 0,
        ...                 "title": "Sheet1",
        ...                 "index": 0,
        ...                 "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...             }
        ...         }
        ...     ],
        ... }
        >>> service = MagicMock()
        >>> service.spreadsheets().get().execute.return_value = payload
        >>> spreadsheet = Sheets(payload, sheets_service=service)
        >>> sheet = spreadsheet.sheet(1)
        >>> _ = sheet.update_values([[1, 2], [3, 4]], sheet_range="Sheet1!A1:B2")
        >>> service.spreadsheets().values().update.called
        True
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
        values: list[list[object]],
        /,
        *,
        sheet_range: str | None,
        as_user: bool = True,
    ) -> Self:
        """
        Write ``values`` into this sheet defaulting the anchor to ``A1``.

        Prepend the tab's title to ``sheet_range`` (or fall back to
        ``"A1"`` when ``None``) to form a fully qualified range then
        delegate to :meth:`update_values`. This is the convenient
        entry point for writing into a specific tab without having to
        repeat the tab title at the call site.

        Parameters
        ----------
        values
            Row-major 2D list of values to write.
        sheet_range
            A1-style range without the sheet prefix indicating the
            top-left anchor of the write (for example ``"B2"``). When
            ``None``, ``A1`` is used.
        as_user
            When ``True``, values are interpreted as ``USER_ENTERED``
            and formulas are evaluated; otherwise written ``RAW``.

        Returns
        -------
            The same :class:`Sheet` instance with refreshed metadata.

        See Also
        --------
        Sheet.update_values : Lower-level write that this delegates to.
        Sheet.insert_df : DataFrame-aware variant.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [
        ...         {
        ...             "properties": {
        ...                 "sheetId": 0,
        ...                 "title": "Sheet1",
        ...                 "index": 0,
        ...                 "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...             }
        ...         }
        ...     ],
        ... }
        >>> service = MagicMock()
        >>> service.spreadsheets().get().execute.return_value = payload
        >>> spreadsheet = Sheets(payload, sheets_service=service)
        >>> sheet = spreadsheet.sheet(1)
        >>> _ = sheet.insert([[1, 2], [3, 4]], sheet_range=None)
        >>> service.spreadsheets().values().update.called
        True
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
        """
        Write a pandas DataFrame (with its index) into the sheet.

        Promote the DataFrame's index to a regular column named
        ``index_name`` via ``reset_index`` before serialising, then
        prepend a header row taken from ``df.columns``. The resulting
        table is written starting at the requested anchor using
        :meth:`update_values` so the spreadsheet metadata is refreshed
        after the call returns.

        Parameters
        ----------
        df
            Pandas DataFrame to materialise into the sheet. Its index
            is reset with ``names=index_name`` prior to writing.
        sheet_range
            A1-style range without the sheet prefix indicating the
            top-left anchor of the write. When ``None``, ``A1`` is
            used.
        as_user
            When ``True``, values are interpreted as ``USER_ENTERED``;
            otherwise written ``RAW``.
        index_name
            Column name assigned to the DataFrame's index when
            promoting it to a column.

        Returns
        -------
            The same :class:`Sheet` instance with refreshed metadata.

        See Also
        --------
        Sheet.insert : Raw-values equivalent.
        Sheets.add_sheet_from_dataframe : Creates a new tab from a DataFrame.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from pandas import DataFrame
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [
        ...         {
        ...             "properties": {
        ...                 "sheetId": 0,
        ...                 "title": "Sheet1",
        ...                 "index": 0,
        ...                 "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...             }
        ...         }
        ...     ],
        ... }
        >>> service = MagicMock()
        >>> service.spreadsheets().get().execute.return_value = payload
        >>> spreadsheet = Sheets(payload, sheets_service=service)
        >>> sheet = spreadsheet.sheet(1)
        >>> df = DataFrame({"a": [1, 2], "b": [3, 4]})
        >>> _ = sheet.insert_df(df, sheet_range=None)
        >>> service.spreadsheets().values().update.called
        True
        """
        df_with_index = df.reset_index(names=index_name)

        return self.update_values(
            [df_with_index.columns.to_list(), *df_with_index.to_numpy().tolist()],
            sheet_range=f"{self.title}!{'A1' if sheet_range is None else sheet_range}",
            as_user=as_user,
        )

    # TODO(@mayurankv): Insert values, Insert formula  # noqa: TD003


class Sheets:
    """
    Represent a whole Google Sheets spreadsheet file.

    Wrap a Drive-backed spreadsheet and expose methods for managing
    its tabs (create, copy, move, rename, delete), reading and writing
    data, and round-tripping pandas DataFrames. Instances are
    constructed via the ``fresh_from_creds``, ``retrieve_from_id``,
    ``retrieve_from_name``, ``create_new`` or ``create_from_template``
    classmethods rather than directly, all of which are thin wrappers
    over the Sheets and Drive REST APIs.

    Parameters
    ----------
    sheets
        Raw spreadsheet payload returned by the Sheets API, containing
        at minimum ``spreadsheetId``, ``properties`` and ``sheets``.
    sheets_service
        Authenticated Google Sheets API service client used for all
        read, write and batch operations against the spreadsheet.

    See Also
    --------
    Sheet : Per-tab wrapper returned by :meth:`sheet`.
    mayutils.interfaces.cloud.google.Drive : Drive wrapper used to resolve filenames.

    Examples
    --------
    >>> from unittest.mock import MagicMock
    >>> from mayutils.interfaces.filetypes.sheets import Sheets
    >>> payload = {
    ...     "spreadsheetId": "abc",
    ...     "properties": {"title": "My Report"},
    ...     "sheets": [
    ...         {
    ...             "properties": {
    ...                 "sheetId": 0,
    ...                 "title": "Sheet1",
    ...                 "index": 0,
    ...                 "gridProperties": {"rowCount": 1000, "columnCount": 26},
    ...             }
    ...         }
    ...     ],
    ... }
    >>> spreadsheet = Sheets(payload, sheets_service=MagicMock())
    >>> len(spreadsheet.sheets)
    1
    """

    def __init__(
        self,
        sheets: Spreadsheet,
        /,
        *,
        sheets_service: SheetsResource,
    ) -> None:
        """
        Initialise the spreadsheet wrapper from a raw API payload.

        Store the raw Sheets API spreadsheet payload together with the
        authenticated service client, and eagerly extract
        ``spreadsheetId`` so later calls can reference it without
        repeatedly indexing into the typed dict. Instances are
        typically created by the factory classmethods rather than
        constructed directly.

        Parameters
        ----------
        sheets
            Raw spreadsheet payload from the Sheets API.
        sheets_service
            Authenticated Google Sheets API service client.

        See Also
        --------
        Sheets.retrieve_from_id : Factory that calls this constructor.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> service = MagicMock()
        >>> service.spreadsheets().get().execute.return_value = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [],
        ... }
        >>> spreadsheet = Sheets.retrieve_from_id("abc", sheets_service=service)
        >>> spreadsheet.id
        'abc'
        """
        self.service: SheetsResource = sheets_service
        self.internal: Spreadsheet = sheets
        self.id: str = self.internal["spreadsheetId"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def _internal_sheets(
        self,
    ) -> list[SheetSchema]:
        """
        Return the raw ``sheets`` list from the spreadsheet payload.

        Expose the nested ``sheets`` array from the Sheets API payload
        so other methods can look up per-tab metadata without
        repeating the typed-dict indexing. The list is ordered to
        match the tab order in the spreadsheet UI.

        Returns
        -------
            Raw per-tab payloads taken from ``self.internal["sheets"]``.

        See Also
        --------
        Sheets.sheet : Uses this list to construct Sheet wrappers.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [
        ...         {
        ...             "properties": {
        ...                 "sheetId": 0,
        ...                 "title": "Sheet1",
        ...                 "index": 0,
        ...                 "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...             }
        ...         }
        ...     ],
        ... }
        >>> spreadsheet = Sheets(payload, sheets_service=MagicMock())
        >>> len(spreadsheet._internal_sheets)
        1
        """
        return self.internal["sheets"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    @property
    def link(
        self,
    ) -> str:
        """
        Return the shareable browser URL for the spreadsheet.

        Construct the canonical
        ``https://docs.google.com/spreadsheets/d/<id>/edit`` URL from
        the cached spreadsheet ID. The URL is useful for logging and
        for passing to :func:`webbrowser.open` via :meth:`open`, but
        performs no authentication of its own.

        Returns
        -------
            Canonical spreadsheet URL built from :attr:`id`.

        See Also
        --------
        Sheets.open : Opens this URL in the default browser.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [],
        ... }
        >>> spreadsheet = Sheets(payload, sheets_service=MagicMock())
        >>> spreadsheet.link
        'https://docs.google.com/spreadsheets/d/abc/edit'
        """
        return f"https://docs.google.com/spreadsheets/d/{self.id}/edit"

    def sheet(
        self,
        sheet_number: int,
        /,
    ) -> Sheet:
        """
        Return the :class:`Sheet` at a 1-indexed position.

        Translate the 1-indexed ``sheet_number`` into the zero-based
        offset used inside :attr:`_internal_sheets`, validate it falls
        within the spreadsheet's current tab count, and wrap the
        selected raw payload in a :class:`Sheet`. Raises when the
        caller asks for a position that does not exist yet.

        Parameters
        ----------
        sheet_number
            1-indexed tab position (``1`` is the leftmost tab).

        Returns
        -------
            Wrapper around the sheet entry at the requested position.

        Raises
        ------
        IndexError
            If ``sheet_number`` is less than ``1`` or exceeds the
            number of sheets in the spreadsheet.

        See Also
        --------
        Sheets.sheet_from_name : Lookup by tab title instead of index.
        Sheets.sheets : Returns all sheets in display order.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [
        ...         {
        ...             "properties": {
        ...                 "sheetId": 0,
        ...                 "title": "Sheet1",
        ...                 "index": 0,
        ...                 "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...             }
        ...         }
        ...     ],
        ... }
        >>> spreadsheet = Sheets(payload, sheets_service=MagicMock())
        >>> first_tab = spreadsheet.sheet(1)
        >>> first_tab.index
        0
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
        """
        Return the :class:`Sheet` whose tab title matches ``sheet_name``.

        Iterate :attr:`_internal_sheets` searching for the first tab
        whose ``properties.title`` equals ``sheet_name``, then delegate
        to :meth:`sheet` to wrap the matching payload. The comparison
        is case-sensitive and requires an exact match.

        Parameters
        ----------
        sheet_name
            Exact tab title to look up (case-sensitive).

        Returns
        -------
            Wrapper around the first sheet whose ``properties.title``
            equals ``sheet_name``.

        Raises
        ------
        ValueError
            If no sheet in the spreadsheet has the given title.

        See Also
        --------
        Sheets.sheet : Lookup by 1-indexed position.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [
        ...         {
        ...             "properties": {
        ...                 "sheetId": 0,
        ...                 "title": "Summary",
        ...                 "index": 0,
        ...                 "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...             }
        ...         }
        ...     ],
        ... }
        >>> spreadsheet = Sheets(payload, sheets_service=MagicMock())
        >>> tab = spreadsheet.sheet_from_name("Summary")
        >>> tab.title
        'Summary'
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
        """
        Return all sheets in the spreadsheet in display order.

        Iterate over :attr:`_internal_sheets` and wrap each raw
        payload in a :class:`Sheet`, preserving the UI ordering
        (leftmost tab first). Cheap to call as each wrapper is just
        a thin view over the cached payload on ``self.internal``.

        Returns
        -------
            :class:`Sheet` wrappers for every tab, ordered
            left-to-right as they appear in the UI.

        See Also
        --------
        Sheets.sheet : Fetch a single tab by 1-indexed position.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [
        ...         {
        ...             "properties": {
        ...                 "sheetId": 0,
        ...                 "title": "Sheet1",
        ...                 "index": 0,
        ...                 "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...             }
        ...         }
        ...     ],
        ... }
        >>> spreadsheet = Sheets(payload, sheets_service=MagicMock())
        >>> [tab.title for tab in spreadsheet.sheets]
        ['Sheet1']
        """
        return [self.sheet(sheet_idx + 1) for sheet_idx in range(len(self._internal_sheets))]

    @property
    def title(
        self,
    ) -> str:
        """
        Return the title of the spreadsheet file as stored in Drive.

        Read ``properties.title`` from the cached spreadsheet payload.
        Calls to :meth:`rename_sheet` only alter tab titles; the
        spreadsheet-level title is set at creation time or via Drive.

        Returns
        -------
            Spreadsheet-level title from ``properties.title``.

        See Also
        --------
        Sheet.title : Per-tab equivalent.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [],
        ... }
        >>> spreadsheet = Sheets(payload, sheets_service=MagicMock())
        >>> spreadsheet.title
        'My Report'
        """
        return self.internal["properties"]["title"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    def open(
        self,
    ) -> None:
        """
        Open the spreadsheet in the system default web browser.

        Call :func:`webbrowser.open` on :attr:`link` to launch the
        spreadsheet in whichever browser the user has configured as
        the system default. No authentication handshake is performed;
        the browser is expected to handle sign-in if needed.

        See Also
        --------
        Sheets.link : URL opened by this method.

        Examples
        --------
        >>> from unittest.mock import MagicMock, patch
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [],
        ... }
        >>> spreadsheet = Sheets(payload, sheets_service=MagicMock())
        >>> with patch("mayutils.interfaces.filetypes.sheets.webbrowser") as mock_wb:
        ...     spreadsheet.open()
        ...     mock_wb.open.called
        True
        """
        webbrowser.open(url=self.link)

    def __repr__(
        self,
    ) -> str:
        """
        Render the first sheet as a compact preview.

        Return the ``repr`` of the first tab (as a pandas DataFrame)
        so interactive environments show something informative
        instead of an opaque object address. Useful for notebooks
        and repl sessions where previewing the leftmost tab is a
        reasonable default.

        Returns
        -------
            ``repr`` of the first tab rendered as a DataFrame.

        See Also
        --------
        Sheet.__repr__ : Per-tab implementation delegated to here.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> service = MagicMock()
        >>> service.spreadsheets().values().get().execute.return_value = {
        ...     "values": [["a", "b"]],
        ... }
        >>> spreadsheet = Sheets(
        ...     {
        ...         "spreadsheetId": "abc",
        ...         "properties": {"title": "My Report"},
        ...         "sheets": [
        ...             {
        ...                 "properties": {
        ...                     "sheetId": 0,
        ...                     "title": "Sheet1",
        ...                     "index": 0,
        ...                     "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...                 }
        ...             }
        ...         ],
        ...     },
        ...     sheets_service=service,
        ... )
        >>> isinstance(repr(spreadsheet), str)
        True
        """
        return self.sheet(1).__repr__()

    def _repr_html_(
        self,
    ) -> str:
        """
        Return the HTML representation of the first tab.

        Delegate to the first tab's ``_repr_html_`` so Jupyter
        environments render a DataFrame preview of the leftmost
        sheet. Useful as a summary view for interactive debugging
        without having to explicitly select a tab.

        Returns
        -------
            HTML fragment rendered by the first tab's styler.

        See Also
        --------
        Sheet._repr_html_ : Underlying per-tab implementation.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.objects.dataframes import setup_pandas
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> setup_pandas()
        >>> service = MagicMock()
        >>> service.spreadsheets().values().get().execute.return_value = {
        ...     "values": [["a", "b"]],
        ... }
        >>> spreadsheet = Sheets(
        ...     {
        ...         "spreadsheetId": "abc",
        ...         "properties": {"title": "My Report"},
        ...         "sheets": [
        ...             {
        ...                 "properties": {
        ...                     "sheetId": 0,
        ...                     "title": "Sheet1",
        ...                     "index": 0,
        ...                     "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...                 }
        ...             }
        ...         ],
        ...     },
        ...     sheets_service=service,
        ... )
        >>> isinstance(spreadsheet._repr_html_(), str)
        True
        """
        return self.sheet(1)._repr_html_()  # pyright: ignore[reportPrivateUsage]

    def _repr_latex_(
        self,
    ) -> str:
        """
        Return the LaTeX representation of the first tab.

        Delegate to the first tab's ``_repr_latex_`` so LaTeX-aware
        Jupyter exporters (such as nbconvert) render the leftmost
        tab as a table. Relies on the per-tab Styler caption set by
        :meth:`Sheet._repr_latex_`.

        Returns
        -------
            LaTeX source rendered by the first tab's styler.

        See Also
        --------
        Sheet._repr_latex_ : Underlying per-tab implementation.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.objects.dataframes import setup_pandas
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> setup_pandas()
        >>> service = MagicMock()
        >>> service.spreadsheets().values().get().execute.return_value = {
        ...     "values": [["a", "b"]],
        ... }
        >>> spreadsheet = Sheets(
        ...     {
        ...         "spreadsheetId": "abc",
        ...         "properties": {"title": "My Report"},
        ...         "sheets": [
        ...             {
        ...                 "properties": {
        ...                     "sheetId": 0,
        ...                     "title": "Sheet1",
        ...                     "index": 0,
        ...                     "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...                 }
        ...             }
        ...         ],
        ...     },
        ...     sheets_service=service,
        ... )
        >>> spreadsheet._repr_latex_() is None or isinstance(spreadsheet._repr_latex_(), str)
        True
        """
        return self.sheet(1)._repr_latex_()  # pyright: ignore[reportPrivateUsage]

    def _repr_mimebundle_(
        self,
        include: None = None,
        exclude: None = None,
    ) -> dict[str, str]:
        """
        Return a MIME bundle derived from the first tab.

        Forward the ``include`` and ``exclude`` arguments to the first
        tab's :meth:`Sheet._repr_mimebundle_`, which emits both HTML
        and plain-text renderings keyed by MIME type. This gives
        Jupyter a reasonable default preview of the spreadsheet's
        leftmost tab.

        Parameters
        ----------
        include
            Forwarded to :meth:`Sheet._repr_mimebundle_`; currently
            ignored downstream.
        exclude
            Forwarded to :meth:`Sheet._repr_mimebundle_`; currently
            ignored downstream.

        Returns
        -------
            MIME-keyed dict produced by the first tab's mime bundle.

        See Also
        --------
        Sheet._repr_mimebundle_ : Per-tab implementation.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> service = MagicMock()
        >>> service.spreadsheets().values().get().execute.return_value = {
        ...     "values": [["a", "b"]],
        ... }
        >>> spreadsheet = Sheets(
        ...     {
        ...         "spreadsheetId": "abc",
        ...         "properties": {"title": "My Report"},
        ...         "sheets": [
        ...             {
        ...                 "properties": {
        ...                     "sheetId": 0,
        ...                     "title": "Sheet1",
        ...                     "index": 0,
        ...                     "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...                 }
        ...             }
        ...         ],
        ...     },
        ...     sheets_service=service,
        ... )
        >>> bundle = spreadsheet._repr_mimebundle_()
        >>> sorted(bundle.keys())
        ['text/html', 'text/plain']
        """
        return self.sheet(1)._repr_mimebundle_(  # pyright: ignore[reportPrivateUsage]
            include=include,
            exclude=exclude,
        )

    def refresh(
        self,
    ) -> Self:
        """
        Re-fetch remote spreadsheet metadata into ``self.internal``.

        Call ``spreadsheets.get`` and replace the cached ``internal``
        payload so downstream properties (tab list, titles, grid
        sizes) reflect the current remote state. Invoked after every
        mutating operation to keep the wrapper and the server in sync.

        Returns
        -------
            The same instance with ``internal`` refreshed from the
            Sheets API.

        See Also
        --------
        Sheets.update : Batch mutator that calls refresh after write.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [],
        ... }
        >>> service = MagicMock()
        >>> service.spreadsheets().get().execute.return_value = payload
        >>> spreadsheet = Sheets(payload, sheets_service=service)
        >>> _ = spreadsheet.refresh()
        >>> service.spreadsheets().get.called
        True
        """
        self.internal = self.service.spreadsheets().get(spreadsheetId=self.id).execute()

        return self

    def update(
        self,
        requests: list[SheetsRequest],
        /,
    ) -> Self:
        """
        Apply a batch of Sheets API request dicts.

        Submit ``requests`` to ``spreadsheets.batchUpdate`` when the
        list is non-empty and then invoke :meth:`refresh` so the
        cached payload matches the post-update state. Passing an
        empty list skips the network call but still triggers a
        refresh.

        Parameters
        ----------
        requests
            Sequence of raw request bodies in the ``batchUpdate``
            format (each entry is one of ``addSheet``,
            ``updateSheetProperties``, ``deleteSheet``, etc.). If
            empty, the API call is skipped.

        Returns
        -------
            The same instance, with :meth:`refresh` already invoked.

        See Also
        --------
        Sheets.refresh : Called at the end of this method.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [],
        ... }
        >>> service = MagicMock()
        >>> service.spreadsheets().get().execute.return_value = payload
        >>> spreadsheet = Sheets(payload, sheets_service=service)
        >>> _ = spreadsheet.update([])
        >>> service.spreadsheets().get.called
        True
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
        values: list[list[object]],
        /,
        *,
        sheet_range: str,
        as_user: bool = True,
    ) -> Self:
        """
        Write ``values`` to ``sheet_range`` on the spreadsheet.

        Call ``spreadsheets.values.update`` with the supplied row-major
        2D list and A1 range, then refresh local metadata so
        :attr:`internal` reflects the post-update state. The
        ``as_user`` flag selects between the API's ``USER_ENTERED``
        and ``RAW`` value input options.

        Parameters
        ----------
        values
            Row-major 2D list of values to write.
        sheet_range
            Fully qualified A1-style range including the sheet prefix
            (for example ``"Sheet1!A1:C3"``).
        as_user
            When ``True``, uses ``valueInputOption=USER_ENTERED`` so
            strings like ``"1/1/2024"`` or ``"=A1+1"`` are parsed as
            dates or formulas. When ``False``, uses ``RAW`` so values
            are stored verbatim.

        Returns
        -------
            The same instance, refreshed so that ``self.internal``
            reflects the updated spreadsheet state.

        See Also
        --------
        Sheet.update_values : Per-tab counterpart that forwards here.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [],
        ... }
        >>> service = MagicMock()
        >>> service.spreadsheets().get().execute.return_value = payload
        >>> spreadsheet = Sheets(payload, sheets_service=service)
        >>> _ = spreadsheet.update_values([[1]], sheet_range="Sheet1!A1")
        >>> service.spreadsheets().values().update.called
        True
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
        """
        Build a Google Sheets v4 API service client.

        Call :func:`googleapiclient.discovery.build` with the supplied
        OAuth credentials and return the typed resource object used
        by every wrapper in this module. The credentials must carry
        at minimum the ``spreadsheets`` scope and, when used via
        :meth:`fresh_from_creds`, Drive scopes too.

        Parameters
        ----------
        creds
            OAuth 2.0 credentials authorised for at least the
            ``spreadsheets`` scope.

        Returns
        -------
            Authenticated ``sheets v4`` API client.

        See Also
        --------
        Sheets.fresh_from_creds : High-level entry point that uses this.

        Examples
        --------
        >>> from unittest.mock import MagicMock, patch
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> with patch("mayutils.interfaces.filetypes.sheets.build") as mock_build:
        ...     mock_build.return_value = MagicMock()
        ...     service = Sheets.service_from_creds(MagicMock())
        ...     mock_build.called
        True
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
        """
        Get an existing spreadsheet by name or create one if missing.

        Build Drive and Sheets clients from the supplied credentials
        and delegate to :meth:`get`, which looks the file up on Drive
        and, when absent, creates a blank spreadsheet or copies the
        template. Provides a one-call entry point for scripts that
        only have raw OAuth credentials available.

        Parameters
        ----------
        sheets_name
            Desired Drive filename of the spreadsheet to retrieve or
            create.
        creds
            OAuth 2.0 credentials authorised for Drive and Sheets.
        template
            Drive filename of a template spreadsheet to clone when no
            spreadsheet named ``sheets_name`` yet exists. When ``None``,
            a blank spreadsheet is created.

        Returns
        -------
            :class:`Sheets` wrapping either the pre-existing file or
            the newly created or copied one.

        See Also
        --------
        Sheets.get : Underlying logic that selects between paths.

        Examples
        --------
        >>> from unittest.mock import MagicMock, patch
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [],
        ... }
        >>> with patch("mayutils.interfaces.filetypes.sheets.Drive") as MockDrive:
        ...     with patch("mayutils.interfaces.filetypes.sheets.build") as mock_build:
        ...         drive = MagicMock()
        ...         drive.find_file_id.return_value = "abc"
        ...         MockDrive.from_creds.return_value = drive
        ...         service = MagicMock()
        ...         service.spreadsheets().get().execute.return_value = payload
        ...         mock_build.return_value = service
        ...         spreadsheet = Sheets.fresh_from_creds("My Report", creds=MagicMock())
        ...         isinstance(spreadsheet, Sheets)
        True
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
        """
        Fetch an existing spreadsheet by Drive file ID.

        Hit the Sheets ``spreadsheets.get`` endpoint with the supplied
        ID and wrap the returned payload in a :class:`Sheets`. The
        ``sheets_service`` must already be authenticated; this method
        performs no credential negotiation of its own.

        Parameters
        ----------
        sheets_id
            Drive file ID of the target spreadsheet (the opaque string
            between ``/d/`` and ``/edit`` in the browser URL).
        sheets_service
            Authenticated Sheets API service client.

        Returns
        -------
            :class:`Sheets` wrapping the retrieved spreadsheet metadata.

        See Also
        --------
        Sheets.retrieve_from_name : Filename-based counterpart.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> service = MagicMock()
        >>> service.spreadsheets().get().execute.return_value = {
        ...     "spreadsheetId": "abc123",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [],
        ... }
        >>> spreadsheet = Sheets.retrieve_from_id("abc123", sheets_service=service)
        >>> spreadsheet.id
        'abc123'
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
        """
        Fetch an existing spreadsheet by its Drive filename.

        Resolve the filename to a Drive file ID via the supplied
        :class:`Drive` wrapper and then call
        :meth:`retrieve_from_id`. Any Drive lookup errors raised by
        :meth:`Drive.find_file_id` propagate unchanged so callers
        can distinguish missing files from permission errors.

        Parameters
        ----------
        sheets_name
            Drive filename of the target spreadsheet.
        drive
            Drive wrapper used to resolve the filename to a file ID.
        sheets_service
            Authenticated Sheets API service client.

        Returns
        -------
            :class:`Sheets` wrapping the retrieved spreadsheet
            metadata.

        See Also
        --------
        Sheets.retrieve_from_id : Target of this delegation.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> drive = MagicMock()
        >>> drive.find_file_id.return_value = "abc"
        >>> service = MagicMock()
        >>> service.spreadsheets().get().execute.return_value = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [],
        ... }
        >>> spreadsheet = Sheets.retrieve_from_name(
        ...     "My Report",
        ...     drive=drive,
        ...     sheets_service=service,
        ... )
        >>> spreadsheet.id
        'abc'
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
        """
        Create a new blank spreadsheet with the given title.

        Issue a ``spreadsheets.create`` call whose payload sets
        ``properties.title`` to ``sheets_name``, then wrap the
        returned metadata. The resulting file appears in Drive under
        the same name and contains the default ``Sheet1`` tab only.

        Parameters
        ----------
        sheets_name
            Title to assign to the newly created spreadsheet. Also
            acts as the Drive filename.
        sheets_service
            Authenticated Sheets API service client.

        Returns
        -------
            :class:`Sheets` wrapping the freshly created, empty
            spreadsheet (one default ``Sheet1`` tab).

        See Also
        --------
        Sheets.create_from_template : Template-based alternative.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> service = MagicMock()
        >>> service.spreadsheets().create().execute.return_value = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [],
        ... }
        >>> spreadsheet = Sheets.create_new("My Report", sheets_service=service)
        >>> spreadsheet.title
        'My Report'
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
        """
        Create a spreadsheet by copying a template file.

        Resolve ``template_name`` to a Drive file ID and invoke
        ``drive.files().copy`` with the new filename, then wrap the
        returned file via :meth:`retrieve_from_id`. Useful when
        bootstrapping reports that rely on pre-formatted tabs,
        formulas or named ranges.

        Parameters
        ----------
        sheets_name
            Title of the newly created copy.
        template_name
            Drive filename of the source template spreadsheet.
        drive
            Drive wrapper used to resolve the template name and
            perform the copy.
        sheets_service
            Authenticated Sheets API service client attached to the
            returned :class:`Sheets` instance.

        Returns
        -------
            :class:`Sheets` wrapping the copied spreadsheet.

        See Also
        --------
        Sheets.create_new : Non-template alternative.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> drive = MagicMock()
        >>> drive.find_file_id.return_value = "tpl"
        >>> drive.files().copy().execute.return_value = {"id": "abc"}
        >>> service = MagicMock()
        >>> service.spreadsheets().get().execute.return_value = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [],
        ... }
        >>> spreadsheet = Sheets.create_from_template(
        ...     "My Report",
        ...     template_name="Report Template",
        ...     drive=drive,
        ...     sheets_service=service,
        ... )
        >>> spreadsheet.id
        'abc'
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
        """
        Retrieve a spreadsheet by name, creating it if it does not exist.

        Attempt :meth:`retrieve_from_name` first; if Drive has no file
        with that name, fall back to :meth:`create_from_template` when
        ``template`` is supplied, or :meth:`create_new` otherwise.
        Provides idempotent "get or create" semantics for automation
        scripts that own their target spreadsheet.

        Parameters
        ----------
        sheets_name
            Drive filename to look up and, if absent, to create.
        drive
            Drive wrapper used for name resolution and template
            copying.
        sheets_service
            Authenticated Sheets API service client.
        template
            Drive filename of a template spreadsheet to clone if
            ``sheets_name`` does not exist. When ``None``, a blank
            spreadsheet is created instead.

        Returns
        -------
            :class:`Sheets` wrapping the resolved (or newly created)
            spreadsheet.

        See Also
        --------
        Sheets.fresh_from_creds : Credential-based wrapper around this.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> drive = MagicMock()
        >>> drive.find_file_id.return_value = "abc"
        >>> service = MagicMock()
        >>> service.spreadsheets().get().execute.return_value = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [],
        ... }
        >>> spreadsheet = Sheets.get(
        ...     "My Report",
        ...     drive=drive,
        ...     sheets_service=service,
        ... )
        >>> spreadsheet.id
        'abc'
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
        """
        Delete and recreate the spreadsheet to clear all content.

        Delete the existing Drive file and create a new blank
        spreadsheet with the same title, then update this instance's
        ``internal`` and ``id`` attributes in place. Useful for test
        harnesses that need a clean file under a stable name.

        Parameters
        ----------
        drive
            Drive wrapper used to delete the underlying file.

        Returns
        -------
            The same instance, now pointing at the fresh, empty
            spreadsheet.

        See Also
        --------
        Sheets.create_new : Creates the replacement file.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> service = MagicMock()
        >>> service.spreadsheets().create().execute.return_value = {
        ...     "spreadsheetId": "new",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [],
        ... }
        >>> spreadsheet = Sheets(
        ...     {
        ...         "spreadsheetId": "abc",
        ...         "properties": {"title": "My Report"},
        ...         "sheets": [],
        ...     },
        ...     sheets_service=service,
        ... )
        >>> drive = MagicMock()
        >>> _ = spreadsheet.reset(drive)
        >>> drive.delete_file_by_id.called
        True
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
        """
        Rename a tab within the spreadsheet.

        Guard against duplicate titles (the Sheets API rejects them
        anyway, but a local check yields a clearer error) and issue
        an ``updateSheetProperties`` batch request for the supplied
        tab. The batch is applied via :meth:`update`, which refreshes
        ``self.internal`` on success.

        Parameters
        ----------
        sheet
            Tab whose title should be changed.
        new_title
            New tab title. Must not collide with any existing tab
            title in the same spreadsheet.

        Returns
        -------
            The same instance, refreshed after the rename.

        Raises
        ------
        ValueError
            If another tab in the spreadsheet already uses
            ``new_title``.

        See Also
        --------
        Sheets.update : Batch-apply mechanism this method uses.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [
        ...         {
        ...             "properties": {
        ...                 "sheetId": 0,
        ...                 "title": "Sheet1",
        ...                 "index": 0,
        ...                 "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...             }
        ...         }
        ...     ],
        ... }
        >>> service = MagicMock()
        >>> service.spreadsheets().get().execute.return_value = payload
        >>> spreadsheet = Sheets(payload, sheets_service=service)
        >>> _ = spreadsheet.rename_sheet(spreadsheet.sheet(1), new_title="Data")
        >>> service.spreadsheets().batchUpdate.called
        True
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
        """
        Move a tab to a new position in the tab bar.

        Translate the 1-indexed ``to_position`` into a zero-based
        target index, validate it falls within the current tab
        count, and submit an ``updateSheetProperties`` batch request
        touching only the ``index`` field. When ``to_position`` is
        ``None`` the tab is moved to the rightmost slot.

        Parameters
        ----------
        sheet
            Tab to reposition.
        to_position
            1-indexed destination position. When ``None``, the tab is
            moved to the rightmost slot.

        Returns
        -------
            The same instance, refreshed after the move.

        Raises
        ------
        IndexError
            If the computed zero-based target index falls outside
            ``[0, number_of_sheets)``.

        See Also
        --------
        Sheets.copy_sheet : Duplicate-and-move combined operation.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [
        ...         {
        ...             "properties": {
        ...                 "sheetId": 0,
        ...                 "title": "Sheet1",
        ...                 "index": 0,
        ...                 "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...             }
        ...         },
        ...         {
        ...             "properties": {
        ...                 "sheetId": 1,
        ...                 "title": "Sheet2",
        ...                 "index": 1,
        ...                 "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...             }
        ...         },
        ...     ],
        ... }
        >>> service = MagicMock()
        >>> service.spreadsheets().get().execute.return_value = payload
        >>> spreadsheet = Sheets(payload, sheets_service=service)
        >>> _ = spreadsheet.move_sheet(spreadsheet.sheet(1), to_position=2)
        >>> service.spreadsheets().batchUpdate.called
        True
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
        """
        Duplicate a tab within the spreadsheet.

        Copy the source tab into the same spreadsheet via
        ``sheets.copyTo`` and, in a single follow-up batch update,
        optionally rename and reposition the resulting tab. When
        ``sheet`` is ``None`` the last tab is duplicated, but in that
        case ``to_position`` must also be ``None`` to avoid ambiguity.

        Parameters
        ----------
        sheet
            Tab to duplicate. When ``None``, defaults to the last tab,
            but ``to_position`` must then also be ``None``.
        new_title
            Title to apply to the new copy. When ``None``, the Sheets
            API assigns a default ``"Copy of ..."`` name. Must not
            collide with existing tab titles.
        to_position
            1-indexed destination position for the copy. When
            ``None``, the copy is placed in its default position
            (end of the tab list). Requires ``sheet`` to be provided.

        Returns
        -------
            The same instance, refreshed after the copy, rename and
            move.

        Raises
        ------
        ValueError
            If ``to_position`` is provided while ``sheet`` is ``None``,
            or if ``new_title`` collides with an existing tab title.
        IndexError
            If the resolved source or target positions fall outside
            the valid range for the current spreadsheet.

        See Also
        --------
        Sheets.move_sheet : Repositions without copying.
        Sheets.rename_sheet : Renames without copying.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [
        ...         {
        ...             "properties": {
        ...                 "sheetId": 0,
        ...                 "title": "Sheet1",
        ...                 "index": 0,
        ...                 "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...             }
        ...         }
        ...     ],
        ... }
        >>> service = MagicMock()
        >>> service.spreadsheets().get().execute.return_value = payload
        >>> service.spreadsheets().sheets().copyTo().execute.return_value = {"sheetId": 1}
        >>> spreadsheet = Sheets(payload, sheets_service=service)
        >>> _ = spreadsheet.copy_sheet(
        ...     sheet=spreadsheet.sheet(1),
        ...     new_title="Backup",
        ... )
        >>> service.spreadsheets().sheets().copyTo.called
        True
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
        """
        Remove a tab from the spreadsheet.

        Submit a single ``deleteSheet`` batch request targeting the
        supplied tab's ``sheetId`` and rely on :meth:`update` to
        refresh local metadata. Google's API rejects requests that
        remove the only remaining sheet, so callers must ensure at
        least one other tab survives.

        Parameters
        ----------
        sheet
            Tab to delete. The spreadsheet must retain at least one
            tab afterwards — the Sheets API rejects requests that
            remove the only remaining sheet.

        Returns
        -------
            The same instance, refreshed after the deletion.

        See Also
        --------
        Sheets.insert_sheet : Inverse operation that adds a tab.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [
        ...         {
        ...             "properties": {
        ...                 "sheetId": 0,
        ...                 "title": "Sheet1",
        ...                 "index": 0,
        ...                 "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...             }
        ...         },
        ...         {
        ...             "properties": {
        ...                 "sheetId": 1,
        ...                 "title": "Sheet2",
        ...                 "index": 1,
        ...                 "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...             }
        ...         },
        ...     ],
        ... }
        >>> service = MagicMock()
        >>> service.spreadsheets().get().execute.return_value = payload
        >>> spreadsheet = Sheets(payload, sheets_service=service)
        >>> _ = spreadsheet.delete_sheet(spreadsheet.sheet(2))
        >>> service.spreadsheets().batchUpdate.called
        True
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
        """
        Add a new blank tab to the spreadsheet.

        Validate any explicit ``to_position`` and guard against title
        collisions, then issue an ``addSheet`` batch request carrying
        only the optional ``index`` and ``title`` fields. The batch is
        applied via :meth:`update` which refreshes local metadata so
        :attr:`sheets` includes the new tab on return.

        Parameters
        ----------
        new_title
            Title for the new tab. When ``None``, Google assigns the
            default ``SheetN`` name. Must not collide with existing
            tab titles.
        to_position
            1-indexed position at which to insert the tab. When
            ``None``, the tab is appended at the end.

        Returns
        -------
            The same instance, refreshed so ``self.sheets`` includes
            the new tab.

        Raises
        ------
        IndexError
            If ``to_position`` resolves to a zero-based index outside
            ``[0, number_of_sheets]``.
        ValueError
            If ``new_title`` is already used by another tab.

        See Also
        --------
        Sheets.delete_sheet : Inverse operation that removes a tab.
        Sheets.add_sheet_from_dataframe : Combined insert + populate.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [
        ...         {
        ...             "properties": {
        ...                 "sheetId": 0,
        ...                 "title": "Sheet1",
        ...                 "index": 0,
        ...                 "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...             }
        ...         }
        ...     ],
        ... }
        >>> service = MagicMock()
        >>> service.spreadsheets().get().execute.return_value = payload
        >>> spreadsheet = Sheets(payload, sheets_service=service)
        >>> _ = spreadsheet.insert_sheet(new_title="Extra")
        >>> service.spreadsheets().batchUpdate.called
        True
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
        **kwargs: object,
    ) -> Self:
        """
        Create a new tab and populate it from a pandas DataFrame.

        Call :meth:`insert_sheet` to create the tab at the requested
        position with the requested title, then locate the newly
        inserted tab and delegate to :meth:`Sheet.insert_df` anchored
        at ``A1``. Extra keyword arguments (for example ``index_name``)
        are forwarded to :meth:`Sheet.insert_df`.

        Parameters
        ----------
        df
            Pandas DataFrame whose contents (header + index + values)
            should populate the new tab.
        new_title
            Title for the new tab. When ``None``, Google assigns a
            default name.
        to_position
            1-indexed position at which to insert the new tab. When
            ``None``, the tab is appended at the end.
        as_user
            Passed through to :meth:`Sheet.insert_df`. When ``True``,
            values are parsed as ``USER_ENTERED``; otherwise written
            ``RAW``.
        **kwargs
            Additional keyword arguments forwarded to
            :meth:`Sheet.insert_df` (for example ``index_name``).

        Returns
        -------
            The same instance, refreshed so ``self.internal`` mirrors
            the post-insert state.

        See Also
        --------
        Sheets.insert_sheet : Tab-creation step.
        Sheet.insert_df : DataFrame writer invoked after the insert.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from pandas import DataFrame
        >>> from mayutils.interfaces.filetypes.sheets import Sheets
        >>> initial_payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [
        ...         {
        ...             "properties": {
        ...                 "sheetId": 0,
        ...                 "title": "Sheet1",
        ...                 "index": 0,
        ...                 "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...             }
        ...         }
        ...     ],
        ... }
        >>> refreshed_payload = {
        ...     "spreadsheetId": "abc",
        ...     "properties": {"title": "My Report"},
        ...     "sheets": [
        ...         {
        ...             "properties": {
        ...                 "sheetId": 0,
        ...                 "title": "Sheet1",
        ...                 "index": 0,
        ...                 "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...             }
        ...         },
        ...         {
        ...             "properties": {
        ...                 "sheetId": 1,
        ...                 "title": "Data",
        ...                 "index": 1,
        ...                 "gridProperties": {"rowCount": 1000, "columnCount": 26},
        ...             }
        ...         },
        ...     ],
        ... }
        >>> service = MagicMock()
        >>> service.spreadsheets().get().execute.return_value = refreshed_payload
        >>> spreadsheet = Sheets(initial_payload, sheets_service=service)
        >>> df = DataFrame({"a": [1, 2], "b": [3, 4]})
        >>> _ = spreadsheet.add_sheet_from_dataframe(df, new_title="Data")
        >>> service.spreadsheets().batchUpdate.called
        True
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
