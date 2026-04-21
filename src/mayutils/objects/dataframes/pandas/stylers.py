"""Extended pandas ``Styler`` with null masking, diverging heatmaps and image export.

This module exposes a :class:`Styler` subclass of :class:`pandas.io.formats.style.Styler`
that layers convenience helpers on top of the vanilla pandas styling machinery.
It adds a transparent-NaN renderer, a symmetric diverging heatmap keyed to a
reference value, per-row display formatters, an ``itables``-powered interactive
view, and a one-call image export pipeline built on ``dataframe-image`` that
produces a palette-consistent PNG with optional dark-mode rendering.
"""

from collections.abc import Callable, Hashable, Mapping, Sequence
from pathlib import Path
from typing import Any, Self

from pandas.io.formats.style_render import Subset

from mayutils.core.extras import may_require_extras
from mayutils.objects.colours import Colour

with may_require_extras():
    import numpy as np
    from dataframe_image._pandas_accessor import (
        disable_max_image_pixels,
        generate_html,  # pyright: ignore[reportUnknownVariableType]
        prepare_converter,  # pyright: ignore[reportUnknownVariableType]
        save_image,  # pyright: ignore[reportUnknownVariableType]
    )
    from itables import show
    from pandas import DataFrame, Index
    from pandas._typing import Axis, Level
    from pandas.io.formats.style import Styler as Style
    from pandas.io.formats.style_render import Subset


type StyleMap = Callable[[Any], str | None]
"""Per-cell styling callback.

Takes an individual cell value and returns the CSS declaration string that
pandas should inject into the rendered ``<td>`` element. Returning ``None``
leaves the cell unstyled.
"""

type RowFormatter = Callable[[Any], str] | str
"""Per-row display formatter.

Either a callable that turns a cell value into its display string, or a
:func:`format`-compatible spec (e.g. ``",.2f"``) applied uniformly to every
cell in the row.
"""


class Styler(Style):
    """pandas ``Styler`` with null masking, diverging heatmaps and image export.

    Subclasses :class:`pandas.io.formats.style.Styler` and layers on four
    categories of helper: transparent rendering of NaN cells via
    :meth:`ignore_null`, a symmetric reference-anchored heatmap via
    :meth:`change_map`, per-row display formatters via :meth:`row_format`,
    and a palette-consistent PNG export via :meth:`save`. Every builder-style
    method returns ``self`` so calls can be chained fluently.

    Notes
    -----
    Instances wrap the same underlying :class:`pandas.DataFrame` as the parent
    class; no data is copied. ``__repr__`` silently applies :meth:`ignore_null`
    so NaN cells display as blanks in notebooks without requiring an explicit
    call.
    """

    def map(  # ty: ignore[invalid-method-override] # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        style_map: StyleMap,
        /,
        *,
        subset: Subset[Hashable] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        """Apply a cell-by-cell CSS mapping to the Styler.

        Thin wrapper around the pandas base-class
        :meth:`pandas.io.formats.style.Styler.map` that accepts the callback
        as a named ``style_map`` argument for readability and returns the
        ``Styler`` itself to support method chaining.

        Parameters
        ----------
        style_map : StyleMap
            Callable invoked once per cell with the cell value; its return
            value is injected as a CSS declaration into the cell.
        *args : Any
            Positional arguments forwarded unchanged to the pandas base-class
            ``map`` implementation (typically the optional ``subset`` slice).
        **kwargs : Any
            Keyword arguments forwarded to the pandas base-class
            implementation. A ``func=`` keyword, if supplied, takes priority
            over ``style_map`` and becomes the applied callback instead.

        Returns
        -------
        Styler
            This :class:`Styler` instance with the mapping registered, enabling
            fluent chained calls.
        """
        super().map(
            func=kwargs.pop("func", style_map),
            subset=subset,
            **kwargs,
        )

        return self

    @property
    def df(
        self,
    ) -> DataFrame:
        """Return the underlying DataFrame being styled.

        Convenience accessor that exposes the private ``data`` attribute of
        the pandas base class under a shorter, public name. The returned
        object is the same instance held by the ``Styler``, not a copy;
        mutating it also mutates the data the ``Styler`` will render.

        Returns
        -------
        pandas.DataFrame
            The DataFrame that this ``Styler`` is configured to render.
        """
        return self.data  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportAttributeAccessIssue] # ty:ignore[unresolved-attribute]

    def ignore_null(
        self,
    ) -> Self:
        """Make NaN cells render as fully transparent blanks.

        Registers a cell-level style map that emits a CSS rule setting both
        foreground text colour and background colour to fully transparent
        whenever the cell value is a float/int NaN. Non-numeric and
        non-missing values are left untouched. Any pre-existing styling on
        the same cells continues to be applied underneath.

        Returns
        -------
        Styler
            This :class:`Styler` instance with the NaN-masking rule
            registered, enabling fluent chained calls.
        """

        def style_map(
            value: np.float64 | str,
        ) -> str:
            """Return transparent CSS for NaN numerics, otherwise an empty string.

            Parameters
            ----------
            value : Any
                The cell value being inspected. Only numeric scalars
                (``float``, ``int``, ``numpy.floating``, ``numpy.integer``)
                are checked for NaN; all other types are treated as present.

            Returns
            -------
            str
                A CSS declaration making the cell fully transparent when
                ``value`` is NaN, or an empty string to leave the cell
                unstyled.
            """
            return (
                "color: rgba(0,0,0,0); background-color: rgba(0, 0, 0, 0);"
                if isinstance(value, (float, int, np.floating, np.integer)) and np.isnan(value)
                else ""
            )

        return self.map(style_map)

    def change_map(
        self,
        max_abs: float,
        /,
        *,
        reference_value: float = 0,
        scaling: float = 0.6,
        columns: Sequence[Hashable] | Index | None = None,
        max_colour: Colour | None = None,
        min_colour: Colour | None = None,
    ) -> Self:
        """Apply a diverging heatmap anchored on a reference value.

        Cells above ``reference_value`` are tinted toward ``max_colour`` and
        cells below are tinted toward ``min_colour``, with per-cell opacity
        proportional to the absolute deviation from the reference divided by
        ``max_abs`` and multiplied by ``scaling``. Cells equal to
        ``reference_value`` are rendered with a fully transparent background.

        Parameters
        ----------
        max_abs : float
            The deviation magnitude that corresponds to peak opacity.
            Deviations are normalised by this value before being scaled, so
            it effectively sets the colour-saturation ceiling of the heatmap.
        reference_value : float, default 0
            The neutral midpoint of the diverging scale. Values equal to
            this receive no colour; values either side of it are tinted with
            ``max_colour`` or ``min_colour`` accordingly.
        scaling : float, default 0.6
            Multiplier applied to the normalised deviation before it is used
            as the background opacity. Values in ``(0, 1]`` cap the maximum
            colour saturation at that fraction.
        columns : Sequence[Hashable] | Index | None, default None
            Restricts the heatmap to the given column labels. When ``None``
            the mapping is applied across every column.
        max_colour : Colour, default rgba(0, 255, 154, 1)
            Base colour used to tint cells strictly greater than
            ``reference_value``.
        min_colour : Colour, default rgba(226, 0, 0, 1)
            Base colour used to tint cells strictly less than
            ``reference_value``.

        Returns
        -------
        Styler
            This :class:`Styler` instance with the heatmap rule registered,
            enabling fluent chained calls.
        """
        if max_colour is None:
            max_colour = Colour.parse("rgba(0, 255, 154, 1)")
        if min_colour is None:
            min_colour = Colour.parse("rgba(226, 0, 0, 1)")

        def style_map(
            val: float,
        ) -> str:
            """Render a diverging background colour for a single cell value.

            Parameters
            ----------
            val : float
                The numeric cell value being styled.

            Returns
            -------
            str
                A CSS ``background-color`` declaration. Uses ``min_colour``
                below, ``max_colour`` above, and a fully transparent rgba at
                the reference value itself.
            """
            if val < reference_value:
                return f"background-color: {min_colour.to_str(opacity=scaling * abs(val - reference_value) / max_abs)};"

            if val > reference_value:
                return f"background-color: {max_colour.to_str(opacity=scaling * abs(val - reference_value) / max_abs)};"

            return "background-color: rgba(0, 0, 0, 0);"

        if columns is None:
            return self.map(style_map)

        return self.map(style_map, subset=columns)  # pyright: ignore[reportArgumentType] # ty:ignore[invalid-argument-type]

    def row_format(
        self,
        formatter: Mapping[Hashable, RowFormatter],
        /,
    ) -> Self:
        """Attach per-row display formatters keyed by row label.

        For each ``label -> formatter`` entry whose label exists in the
        DataFrame index, installs the formatter against every cell of that
        row by writing directly into the ``Styler``'s internal
        ``_display_funcs`` table. String values are treated as
        :func:`format`-compatible specs and wrapped in a lambda; callables
        are installed verbatim. Row labels absent from the index are
        silently skipped.

        Parameters
        ----------
        formatter : Mapping[Hashable, RowFormatter]
            Mapping from row label to either a callable
            ``value -> display_str`` or a :func:`format`-compatible spec
            (e.g. ``",.2%"``) applied to every cell of the matching row.

        Returns
        -------
        Styler
            This :class:`Styler` instance with the row formatters installed,
            enabling fluent chained calls.
        """
        for row, row_formatter in formatter.items():
            if row in self.index:
                row_num = self.index.get_loc(row)

                display_func: Callable[[Any], str] = (
                    (lambda x, _spec=row_formatter: format(x, _spec)) if isinstance(row_formatter, str) else row_formatter
                )

                for col_num in range(len(self.columns)):
                    self._display_funcs[(row_num, col_num)] = display_func  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]  # ty: ignore[unresolved-attribute]

        return self

    def __repr__(
        self,
    ) -> str:
        """Return the default ``Styler`` repr with NaNs rendered as blanks.

        Applies :meth:`ignore_null` before delegating to the pandas base-class
        ``__repr__`` so NaN cells appear visually empty in notebook output
        without the caller needing to opt in.

        Returns
        -------
        str
            The HTML representation produced by the pandas base class after
            the transparent-NaN mask has been applied.
        """
        return super(Styler, self.ignore_null()).__repr__()

    def interact(
        self,
        *,
        caption: str | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Render the Styler as an interactive ``itables`` table.

        Hands the current ``Styler`` to :func:`itables.show` with
        ``allow_html=True`` so embedded CSS from other helper methods is
        preserved, producing a sortable, searchable, paginated view in
        notebook environments.

        Parameters
        ----------
        *args : Any
            Positional arguments forwarded verbatim to :func:`itables.show`.
        **kwargs : Any
            Keyword arguments forwarded verbatim to :func:`itables.show`
            (for example ``paging``, ``classes`` or ``lengthMenu``).
        """
        return show(
            df=self,
            caption=caption,
            allow_html=True,
            **kwargs,
        )

    def hide(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        *,
        subset: Subset[Hashable] | None = None,
        axis: Axis = 0,
        level: Level | list[Level] | None = None,
        names: bool = False,
    ) -> Self:  # ty:ignore[invalid-method-override]
        """Hide columns, rows or index levels while preserving chaining.

        Thin passthrough to :meth:`pandas.io.formats.style.Styler.hide`; the
        only behavioural difference from the base implementation is the
        return value, which is this ``Styler`` itself to support fluent
        chaining.

        Parameters
        ----------
        *args : Any
            Positional arguments forwarded to the pandas base-class
            ``hide`` method (typically ``subset`` and ``axis``).
        **kwargs : Any
            Keyword arguments forwarded to the pandas base-class
            implementation (e.g. ``names``, ``level``).

        Returns
        -------
        Styler
            This :class:`Styler` instance with the hide rules registered,
            enabling fluent chained calls.
        """
        super().hide(
            subset=subset,
            axis=axis,
            level=level,
            names=names,
        )

        return self

    def save(
        self,
        path: Path | str,
        /,
        *,
        dark: bool = False,
        fontsize: int = 14,
        dpi: int = 200,
        use_mathjax: bool = True,
        max_rows: int | None = None,
        max_cols: int | None = None,
        additional_css: str = "",
    ) -> Path:
        """Render the Styler to disk as an image via ``dataframe-image``.

        Prepares a Selenium-backed HTML-to-image converter, generates the
        ``Styler`` HTML, wraps it in a palette-consistent stylesheet
        (respecting the ``dark`` flag) and writes the result to ``path``.
        The image palette is derived from a single base colour using
        :meth:`Colour.blend` so header and zebra-striping rows remain
        coherent across light and dark modes.

        Parameters
        ----------
        path : Path | str
            Output filesystem path for the image. The extension determines
            the output format (PNG, JPG, etc.).
        dark : bool, default False
            When ``True`` uses a dark neutral base (``rgb(31, 36, 48)``)
            with a light font colour; when ``False`` uses a white base with
            black text.
        fontsize : int, default 14
            Font size in pixels used by the HTML-to-image converter.
        dpi : int, default 200
            Rendering resolution in dots per inch, passed through to the
            converter; controls pixel density of the output image.
        use_mathjax : bool, default True
            When ``True`` loads MathJax into the rendering browser so LaTeX
            fragments embedded in cell values are typeset before capture.
        max_rows : int | None, default None
            Optional cap on the number of rows included in the image; rows
            beyond the cap are omitted. ``None`` renders every row.
        max_cols : int | None, default None
            Optional cap on the number of columns included in the image;
            columns beyond the cap are omitted. ``None`` renders every
            column.
        additional_css : str, default ""
            Extra CSS appended verbatim to the generated stylesheet,
            allowing callers to override or extend the default palette
            without forking the method.

        Returns
        -------
        pathlib.Path
            The path the image was written to, normalised to a
            :class:`pathlib.Path` instance.
        """
        path = Path(path)
        table_conversion = "selenium"
        chrome_path = None
        crop_top = True

        converter: Callable[[str], bytes] = prepare_converter(  # pyright: ignore[reportUnknownVariableType]
            filename=path,
            fontsize=fontsize,
            max_rows=max_rows,
            max_cols=max_cols,
            table_conversion=table_conversion,
            chrome_path=chrome_path,
            dpi=dpi,
            use_mathjax=use_mathjax,
            crop_top=crop_top,
        )

        html: str = generate_html(  # pyright: ignore[reportUnknownVariableType]
            obj=self,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            filename=path,
            max_rows=max_rows,
            max_cols=max_cols,
        )

        base = Colour.parse("rgb(31, 36, 48)" if dark else "#FFFFFF")
        font_colour = "#cccac2" if dark else "#000000"
        style = """
            <style>
                div {{
                    color: {font_colour};
                    background-color: {base};
                    border-color: transparent;
                }}
                table {{
                    border-color: transparent;
                    background-color: {base};
                    color: {font_colour};
                }}
                tbody tr:nth-child(odd) {{
                    background-color: {base};
                }}
                tr:nth-child(even) {{
                    background-color: {even};
                }}
                thead {{
                    background-color: {header} !important;
                }}
                table, thead, tr, th, td, tbody {{
                    border: none;
                    border-spacing: 0;
                    border-collapse: collapse;
                    border-color: transparent;
                }}
                {additional_css}
            </style>
        """.format(
            base=base.to_str(),
            even=(
                Colour.blend(
                    foreground=Colour.parse("rgba(130, 130, 130, 0.08)"),
                    background=base,
                )
                .round()
                .to_str()
            ),
            header=(
                Colour.blend(
                    foreground=Colour.parse("rgba(130, 130, 130, 0.16)"),
                    background=base,
                )
                .round()
                .to_str()
            ),
            font_colour=font_colour,
            additional_css=additional_css,
        )

        with disable_max_image_pixels():
            img_str = converter(style + html)  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]

        save_image(
            img_str=img_str,
            filename=path,
        )

        return path
