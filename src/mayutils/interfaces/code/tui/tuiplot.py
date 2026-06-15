"""
Query, transform and plot tabular data directly in the terminal.

Provides both a one-shot CLI and an interactive Textual TUI around the
same pipeline: load a DataFrame (inline SQL or a ``.sql`` file executed
through a :class:`~mayutils.data.read.QueryReader`, or a data file such
as ``.csv``/``.parquet`` read via the
:class:`~mayutils.interfaces.filetypes.DataFile` registry), optionally
apply a Python transform expression, build a figure with the house
:class:`~mayutils.visualisation.graphs.plotly.Plot` API, and render it
as a PNG sized to the terminal. The CLI displays the PNG via kitty's
``icat`` protocol; the TUI renders it inline through ``textual-image``
and can alternatively show the raw DataFrame in a table. SQL execution
defaults to :func:`mayutils.interfaces.data.get_env_reader` (driven by
``SNOWFLAKE_*`` environment variables) but any reader can be injected,
and reader keyword overrides can be supplied from the CLI or spec file.

See Also
--------
mayutils.interfaces.code.tui.textual : Transparent ANSI app building blocks.
mayutils.interfaces.data.get_env_reader : Default environment-driven reader.
mayutils.interfaces.filetypes.DataFile : Suffix-dispatched data file readers.
mayutils.visualisation.graphs.plotly.Plot : Figure type produced here.

Examples
--------
>>> from mayutils.interfaces.code.tui.tuiplot import PlotType
>>> PlotType.line.value
'line'
"""

from __future__ import annotations

import ast
import io
import shutil
import subprocess
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, NoReturn, cast

from mayutils.core.extras import may_require_extras
from mayutils.environment.memoisation.files import register_datafile
from mayutils.interfaces.code.tui.textual import TransparentApp, TransparentFooter
from mayutils.interfaces.data import get_env_reader
from mayutils.interfaces.filetypes import DataFile
from mayutils.visualisation.graphs.plotly import Line, Plot, Scatter, set_template

with may_require_extras():
    from rich.console import Console
    from textual import work
    from textual.binding import Binding
    from textual.widgets import (
        DataTable,
        Input,
        Select,
        Switch,
        TextArea,
    )
    from textual_image.widget import Image
    from typer import Exit, Option, Typer

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    import pandas as pd
    import plotly.graph_objects as go
    from PIL import Image as PILImage
    from textual.app import ComposeResult
    from textual.binding import BindingType
    from textual.widgets import Button

    from mayutils.data.read import QueryReader


console = Console(stderr=True)

app = Typer(
    add_completion=False,
    pretty_exceptions_enable=False,
)

PX_PER_COLUMN = 8
PX_PER_ROW = 16
DEFAULT_HEIGHT = 900
DEFAULT_SCALE = 2.0

DISPLAY_MODE_OPTIONS = [
    ("Plot", "plot"),
    ("DataFrame", "dataframe"),
    ("Sample (20)", "sample"),
]


class PlotType(StrEnum):
    """
    Supported chart styles for :func:`make_figure`.

    Each member selects the trace constructor used for every y column
    (:class:`~mayutils.visualisation.graphs.plotly.Line`,
    :class:`plotly.graph_objects.Bar` or
    :class:`~mayutils.visualisation.graphs.plotly.Scatter`), and the
    string values double as the CLI ``--plot`` choices and the TUI
    plot-type dropdown options.

    See Also
    --------
    make_figure : Consumer that dispatches members to trace constructors.

    Examples
    --------
    >>> from mayutils.interfaces.code.tui.tuiplot import PlotType
    >>> PlotType("bar").value
    'bar'
    """

    line = "line"
    bar = "bar"
    scatter = "scatter"


def die(
    message: str,
    /,
    *,
    code: int = 1,
) -> NoReturn:
    """
    Print an error message to stderr and exit the CLI.

    Renders the message in bold red on the module-level stderr console
    and then terminates the typer application with the given exit code,
    so callers never continue past a fatal condition.

    Parameters
    ----------
    message
        Human-readable error text printed to stderr.
    code
        Process exit code carried by the raised :class:`typer.Exit`.

    Raises
    ------
    typer.Exit
        Always, carrying the given exit code.

    See Also
    --------
    main : CLI entry point that funnels fatal errors through this helper.

    Examples
    --------
    >>> from mayutils.interfaces.code.tui.tuiplot import die
    >>> die("something went wrong", code=2)  # doctest: +SKIP
    """
    console.print(f"[bold red]error:[/bold red] {message}")

    raise Exit(code)


def load_spec(
    path: Path | None,
    /,
) -> dict[str, Any]:
    """
    Load a YAML spec file into a mapping, or an empty one when *path* is ``None``.

    The spec file provides defaults for the plotting options of
    :func:`main` (``transform``, ``plot``, ``x``, ``width``, ``height``,
    ``scale`` and ``reader_args``); explicit command-line flags take
    precedence over the values loaded here.

    Parameters
    ----------
    path
        Location of the YAML spec file, or ``None`` to skip loading.

    Returns
    -------
        The parsed spec mapping.

    Raises
    ------
    TypeError
        If the file parses to something other than a mapping.

    See Also
    --------
    main : CLI entry point that merges the spec with command-line flags.

    Examples
    --------
    >>> from mayutils.interfaces.code.tui.tuiplot import load_spec
    >>> load_spec(None)
    {}
    """
    with may_require_extras():
        import yaml

    if path is None:
        return {}

    data = cast("object", yaml.safe_load(stream=path.read_text(encoding="utf-8")))
    if data is None:
        return {}

    if not isinstance(data, dict):
        msg = f"Spec file {path} must be a YAML mapping"
        raise TypeError(msg)

    return cast("dict[str, Any]", data)


def eval_transform(
    df: pd.DataFrame,
    /,
    *,
    expression: str,
) -> pd.DataFrame:
    """
    Evaluate a user-supplied transform expression against ``df``.

    The expression is evaluated with builtins stripped and only ``df``
    (a copy of the input, so the original frame is never mutated) and
    ``pd`` in scope. A Series result is promoted to a single-column
    DataFrame so downstream plotting always receives a frame.

    Parameters
    ----------
    df
        Input DataFrame bound to the name ``df`` inside the expression.
    expression
        Python expression returning a DataFrame or Series.

    Returns
    -------
        The transformed DataFrame (a Series result is promoted to a frame).

    Raises
    ------
    TypeError
        If the expression returns neither a DataFrame nor a Series.

    See Also
    --------
    load_data : Producer of the DataFrame this transform is applied to.
    pandas.DataFrame.eval : Vectorised expression evaluation alternative.

    Examples
    --------
    >>> import pandas as pd
    >>> from mayutils.interfaces.code.tui.tuiplot import eval_transform
    >>> df = pd.DataFrame({"a": [1, 2, 3]})
    >>> eval_transform(df, expression="df.head(2)")["a"].tolist()
    [1, 2]
    """
    with may_require_extras():
        import pandas as pd

    result = eval(expression, {"__builtins__": {}}, {"df": df.copy(), "pd": pd})  # noqa: S307

    if isinstance(result, pd.Series):
        result = result.to_frame()

    if not isinstance(result, pd.DataFrame):
        msg = f"Transform must return a DataFrame or Series, got {type(result)!r}"
        raise TypeError(msg)

    return result


def load_data(
    *,
    sql: str | None = None,
    source: Path | None = None,
    reader_factory: Callable[[], QueryReader] | None = None,
) -> pd.DataFrame:
    """
    Load a DataFrame from inline SQL, a ``.sql`` file, or a data file.

    A *source* with a ``.sql`` suffix is read and executed as SQL; any
    other suffix is dispatched through the
    :class:`~mayutils.interfaces.filetypes.DataFile` registry (``.csv``,
    ``.parquet``, ``.feather``, ...). SQL is executed by the reader from
    *reader_factory*, defaulting to
    :func:`~mayutils.interfaces.data.get_env_reader`.

    Parameters
    ----------
    sql
        Inline SQL query string, used when no data *source* is given.
    source
        Path to a ``.sql`` query file or a tabular data file.
    reader_factory
        Zero-argument callable producing the reader that executes SQL;
        defaults to :func:`~mayutils.interfaces.data.get_env_reader`.

    Returns
    -------
        The loaded DataFrame.

    Raises
    ------
    ValueError
        If neither *sql* nor *source* is provided.

    See Also
    --------
    mayutils.interfaces.data.get_env_reader : Default reader factory.
    mayutils.interfaces.filetypes.DataFile : Registry handling non-SQL files.

    Examples
    --------
    >>> from mayutils.interfaces.code.tui.tuiplot import load_data
    >>> load_data(sql="SELECT 1 AS one")  # doctest: +SKIP
       one
    0    1
    """
    if source is not None and source.suffix.lower() != ".sql":
        register_datafile(source.suffix)

        return DataFile.from_path(source).read()

    if source is not None:
        sql = source.read_text(encoding="utf-8")

    if sql is None:
        msg = "Provide inline SQL or a source file"
        raise ValueError(msg)

    reader = reader_factory() if reader_factory is not None else get_env_reader()

    return reader(sql)


def make_figure(
    data: pd.DataFrame,
    /,
    *,
    plot: PlotType,
    x: str | None = None,
) -> Plot:
    """
    Build a figure plotting every non-x column of *data* against *x*.

    The x column defaults to the index when it is named (or when *x* is
    ``"index"``), and to the first column otherwise.

    Parameters
    ----------
    data
        DataFrame whose columns provide the x and y series.
    plot
        Chart style selecting the trace constructor for each y column.
    x
        Name of the x column, ``"index"`` to plot against the index, or
        ``None`` to infer (named index first, then the first column).

    Returns
    -------
        The constructed figure.

    Raises
    ------
    ValueError
        If no y columns remain or the plot type is unsupported.

    See Also
    --------
    PlotType : Supported chart styles.
    mayutils.visualisation.graphs.plotly.Plot.from_traces : Figure constructor used here.

    Examples
    --------
    >>> import pandas as pd
    >>> from mayutils.interfaces.code.tui.tuiplot import PlotType, make_figure
    >>> df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    >>> type(make_figure(df, plot=PlotType.line, x="x")).__name__
    'Plot'
    """
    with may_require_extras():
        import plotly.graph_objects as go

    df = data.copy()

    if x == "index" or (x is None and df.index.name is not None):
        df = df.reset_index()
        x = str(df.columns[0])

    if x is None:
        x = str(df.columns[0])

    y_columns = [column for column in df.columns if column != x]
    if not y_columns:
        msg = f"No y columns left after taking {x!r} as the x column"
        raise ValueError(msg)

    trace_types: dict[PlotType, Callable[..., go.Scatter | go.Bar]] = {
        PlotType.line: Line,
        PlotType.bar: go.Bar,
        PlotType.scatter: Scatter,
    }
    trace_type = trace_types.get(plot)
    if trace_type is None:
        msg = f"Unsupported plot type: {plot!r}"
        raise ValueError(msg)

    return Plot.from_traces(
        *(
            trace_type(
                x=df[x],
                y=df[column],
                name=str(column),
            )
            for column in y_columns
        ),
        description=f"{plot.value} plot",
        xaxis_config={"title_text": x},
    )


def render_png(
    figure: go.Figure,
    /,
    *,
    width: int,
    height: int,
    scale: float,
) -> bytes:
    """
    Render *figure* to PNG bytes via kaleido.

    Ensures a kaleido-managed Chrome binary is available (downloading
    it on first use) and then rasterises the figure at the requested
    pixel dimensions, with *scale* multiplying the output resolution.

    Parameters
    ----------
    figure
        Plotly figure to rasterise.
    width
        Output image width in pixels.
    height
        Output image height in pixels.
    scale
        Resolution multiplier applied to both dimensions.

    Returns
    -------
        The encoded PNG image.

    See Also
    --------
    display_png_in_kitty : Sends the rendered bytes to the terminal.
    plotly.graph_objects.Figure.to_image : Underlying export primitive.

    Examples
    --------
    >>> from mayutils.interfaces.code.tui.tuiplot import render_png
    >>> png = render_png(figure, width=800, height=600, scale=2.0)  # doctest: +SKIP
    """
    with may_require_extras():
        import kaleido

    kaleido.get_chrome_sync()

    return figure.to_image(
        format="png",
        width=width,
        height=height,
        scale=scale,
    )


def kitty_supports_images() -> None:
    """
    Check that the terminal supports kitty's image protocol.

    Runs ``kitten icat --detect-support`` as a subprocess and raises
    when it reports failure, letting :func:`main` abort with a clear
    message before spending time rendering a PNG it cannot display.

    Raises
    ------
    RuntimeError
        If ``kitten icat`` reports that image display is unavailable.

    See Also
    --------
    display_png_in_kitty : Display step gated by this check.

    Examples
    --------
    >>> from mayutils.interfaces.code.tui.tuiplot import kitty_supports_images
    >>> kitty_supports_images()  # doctest: +SKIP
    """
    process = subprocess.run(
        ["kitten", "icat", "--detect-support"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        msg = f"kitty image display is not available.\nstderr:\n{process.stderr}"
        raise RuntimeError(msg)


def display_png_in_kitty(
    png: bytes,
    /,
) -> None:
    """
    Display PNG bytes inline in the terminal via kitty's ``icat``.

    Pipes the image to ``kitten icat --stdin=yes`` so the rendered plot
    appears directly in the terminal scrollback, which is how the
    one-shot CLI path of :func:`main` presents its output.

    Parameters
    ----------
    png
        Encoded PNG image bytes to display.

    Raises
    ------
    RuntimeError
        If ``kitten icat`` exits with a non-zero status.

    See Also
    --------
    kitty_supports_images : Capability check run before displaying.
    render_png : Producer of the PNG bytes displayed here.

    Examples
    --------
    >>> from mayutils.interfaces.code.tui.tuiplot import display_png_in_kitty
    >>> display_png_in_kitty(png)  # doctest: +SKIP
    """
    process = subprocess.run(
        ["kitten", "icat", "--stdin=yes"],  # noqa: S607
        input=png,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        stderr = process.stderr.decode("utf-8", errors="replace")
        msg = f"kitty icat failed:\n{stderr}"
        raise RuntimeError(msg)


class TuiPlotApp(TransparentApp[None]):
    """
    Interactive TUI for querying, transforming and plotting tabular data.

    Wraps the module's load/transform/plot pipeline in a Textual app: a
    tabbed control panel collects the SQL (or source file path),
    transform expression, plot type, layout overrides and image
    settings, then a worker thread executes the pipeline and displays
    the result as an inline PNG or a populated ``DataTable``.

    Parameters
    ----------
    *args
        Positional arguments forwarded to :class:`TransparentApp`.
    reader
        Query reader used to execute SQL, or ``None`` to build one
        lazily from the environment on first use.
    reader_kwargs
        Keyword overrides forwarded to
        :func:`~mayutils.interfaces.data.get_env_reader` when building
        the default reader.
    **kwargs
        Keyword arguments forwarded to :class:`TransparentApp`.

    See Also
    --------
    tui : Convenience launcher constructing and running this app.
    mayutils.interfaces.code.tui.textual.TransparentApp : ANSI-transparent base app.

    Examples
    --------
    >>> from mayutils.interfaces.code.tui.tuiplot import TuiPlotApp
    >>> TuiPlotApp(reader_kwargs={"role": "ANALYST"}).run()  # doctest: +SKIP
    """

    TITLE = "TUI Plot"

    CSS = """
    TextArea {
        height: 6;
    }

    #controls-panel {
        height: 1fr;
    }

    #main-content {
        width: 100%;
        align: center top;
    }

    #result-panel {
        height: 1fr;
        align: center middle;
    }

    #result-panel.fullscreen {
        height: 1fr;
    }

    #transform-input {
        height: 4;
    }

    #file-label {
        color: $text-muted;
        text-style: italic;
    }

    Button#run-btn {
        margin: 0 1 0 0;
        border: round ansi_cyan;
    }

    #action-bar {
        height: auto;
        align: left middle;
    }

    #sql-header {
        height: 1;
    }

    #sql-file-input {
        display: none;
    }

    #result-table {
        display: none;
        height: 1fr;
        width: 100%;
        border: round ansi_blue;
    }

    #result-image {
        display: none;
        height: 1fr;
        width: 100%;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+enter", "run_query", "Run"),
        Binding("ctrl+f", "toggle_fullscreen", "Fullscreen"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(
        self,
        *args: Any,  # noqa: ANN401
        reader: QueryReader | None = None,
        reader_kwargs: Mapping[str, Any] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """
        Initialise the app and stash the reader configuration.

        Delegates widget and theme setup to :class:`TransparentApp` and
        records the injected reader plus the keyword overrides used to
        build an environment reader lazily on the first query.

        Parameters
        ----------
        *args
            Positional arguments forwarded to :class:`TransparentApp`.
        reader
            Query reader used to execute SQL, or ``None`` to defer to
            :func:`~mayutils.interfaces.data.get_env_reader`.
        reader_kwargs
            Keyword overrides forwarded to the environment reader factory.
        **kwargs
            Keyword arguments forwarded to :class:`TransparentApp`.

        See Also
        --------
        TuiPlotApp.get_reader : Lazy reader construction on first use.

        Examples
        --------
        >>> from mayutils.interfaces.code.tui.tuiplot import TuiPlotApp
        >>> app = TuiPlotApp(reader_kwargs={"role": "ANALYST"})  # doctest: +SKIP
        """
        super().__init__(*args, **kwargs)

        self.reader = reader
        self.reader_kwargs = dict(reader_kwargs or {})

    def get_reader(
        self,
    ) -> QueryReader:
        """
        Return the injected reader, building one from the environment on first use.

        The constructed reader is cached on the instance so repeated
        queries reuse the same connection, with the ``reader_kwargs``
        supplied at construction forwarded to the environment factory.

        Returns
        -------
            The reader used to execute SQL queries.

        See Also
        --------
        mayutils.interfaces.data.get_env_reader : Environment-driven reader factory.

        Examples
        --------
        >>> from mayutils.interfaces.code.tui.tuiplot import TuiPlotApp
        >>> reader = TuiPlotApp().get_reader()  # doctest: +SKIP
        """
        if self.reader is None:
            self.reader = get_env_reader(**self.reader_kwargs)

        return self.reader

    def compose(
        self,
    ) -> ComposeResult:
        """
        Build the widget tree.

        Lays out a tabbed control panel (Query, Plotting and Settings
        tabs) above a result panel holding the data table and inline
        image widgets, framed by a header and a transparent footer.

        Yields
        ------
            The app's widgets.

        See Also
        --------
        mayutils.interfaces.code.tui.textual.TransparentFooter : Footer widget yielded last.
        textual.app.App.compose : Textual hook this method implements.

        Examples
        --------
        >>> from mayutils.interfaces.code.tui.tuiplot import TuiPlotApp
        >>> widgets = list(TuiPlotApp().compose())  # doctest: +SKIP
        """
        with may_require_extras():
            from textual.containers import Horizontal, Vertical, VerticalScroll
            from textual.widgets import Button, Header, Label, Rule, TabbedContent, TabPane

        yield Header()
        with VerticalScroll(id="controls-panel"), Vertical(id="main-content"), TabbedContent():
            with TabPane("Query", id="query-tab"):
                with Horizontal(id="sql-header"):
                    yield Label("SQL", id="sql-label")
                    yield Label("File", id="file-label")
                    yield Switch(value=False, id="file-switch")
                yield TextArea(
                    placeholder="SELECT * FROM table",
                    language="sql",
                    id="sql-input",
                )
                yield Input(
                    placeholder="Path to a .sql, .csv or .parquet file",
                    id="sql-file-input",
                )
                yield Label("Transform", id="transform-label")
                yield TextArea(
                    placeholder="df.head()",
                    language="python",
                    id="transform-input",
                )
                with Horizontal(id="action-bar"):
                    yield Button("Run", id="run-btn", variant="primary")
                    yield Select(
                        DISPLAY_MODE_OPTIONS,
                        value="plot",
                        id="display-mode",
                    )
            with TabPane("Plotting", id="plotting-tab"):
                yield Select(
                    [(plot_type.value.capitalize(), plot_type.value) for plot_type in PlotType],
                    value="line",
                    id="plot-type",
                )
                yield Label("Layout")
                yield TextArea(
                    placeholder="{'title': 'My Plot'}",
                    language="python",
                    id="layout-input",
                )
            with TabPane("Settings", id="settings-tab"):
                yield Input(placeholder="Scale", id="scale-input")
                yield Input(placeholder="Width (px)", id="width-input")
                yield Input(placeholder="Height (px)", id="height-input")
        yield Rule()
        with Vertical(id="result-panel"):
            yield DataTable(id="result-table")
            yield Image(id="result-image")
        yield TransparentFooter()

    def action_toggle_fullscreen(
        self,
    ) -> None:
        """
        Toggle between the full layout and a fullscreen result panel.

        Bound to ``ctrl+f``: hides the controls panel and marks the
        result panel fullscreen, or restores the original layout when
        the result panel is already fullscreen.

        See Also
        --------
        TuiPlotApp.show_output : Chooses which result widget is visible.

        Examples
        --------
        >>> from mayutils.interfaces.code.tui.tuiplot import TuiPlotApp
        >>> TuiPlotApp().action_toggle_fullscreen()  # doctest: +SKIP
        """
        controls = self.query_one("#controls-panel")
        result = self.query_one("#result-panel")
        if result.has_class("fullscreen"):
            result.remove_class("fullscreen")
            controls.styles.display = "block"
        else:
            result.add_class("fullscreen")
            controls.styles.display = "none"

    def on_switch_changed(
        self,
        event: Switch.Changed,
    ) -> None:
        """
        Swap between the inline SQL editor and the file path input.

        Reacts to the ``file-switch`` toggle on the Query tab: when the
        switch is on, the SQL text area is hidden in favour of the file
        path input, and vice versa when it is turned off.

        Parameters
        ----------
        event
            Switch change event carrying the toggled switch and value.

        See Also
        --------
        TuiPlotApp.action_run_query : Reads whichever input is active.

        Examples
        --------
        >>> from mayutils.interfaces.code.tui.tuiplot import TuiPlotApp
        >>> TuiPlotApp().on_switch_changed(event)  # doctest: +SKIP
        """
        if event.switch.id == "file-switch":
            sql_input = self.query_one("#sql-input", TextArea)
            sql_file_input = self.query_one("#sql-file-input", Input)
            if event.value:
                sql_input.add_class("hidden")
                sql_file_input.remove_class("hidden")
                sql_file_input.styles.display = "block"
            else:
                sql_input.remove_class("hidden")
                sql_file_input.add_class("hidden")
                sql_file_input.styles.display = "none"

    def on_button_pressed(
        self,
        event: Button.Pressed,
    ) -> None:
        """
        Run the query when the Run button is pressed.

        Delegates to :meth:`action_run_query` for presses of the
        ``run-btn`` button, making the button equivalent to the
        ``ctrl+enter`` binding.

        Parameters
        ----------
        event
            Button press event carrying the pressed button.

        See Also
        --------
        TuiPlotApp.action_run_query : Action invoked for the Run button.

        Examples
        --------
        >>> from mayutils.interfaces.code.tui.tuiplot import TuiPlotApp
        >>> TuiPlotApp().on_button_pressed(event)  # doctest: +SKIP
        """
        if event.button.id == "run-btn":
            self.action_run_query()

    def action_run_query(
        self,
    ) -> None:
        """
        Collect the form state and dispatch the query worker.

        Reads the SQL (or source file path), transform expression, plot
        settings and display mode from the form widgets, validates that
        an input was provided, and hands everything to
        :meth:`run_worker_query` on a background thread.

        See Also
        --------
        TuiPlotApp.run_worker_query : Worker executing the collected request.

        Examples
        --------
        >>> from mayutils.interfaces.code.tui.tuiplot import TuiPlotApp
        >>> TuiPlotApp().action_run_query()  # doctest: +SKIP
        """
        use_file = self.query_one("#file-switch", Switch).value
        if use_file:
            source = self.query_one("#sql-file-input", Input).value.strip()
            if not source:
                self.set_status("Error: no source file path provided")
                return
            sql = None
        else:
            sql = self.query_one("#sql-input", TextArea).text.strip()
            if not sql:
                self.set_status("Error: no SQL query provided")
                return
            source = None

        transform = self.query_one("#transform-input", TextArea).text.strip() or None
        plot_type = cast("Select[str]", self.query_one("#plot-type", Select)).value
        layout_str = self.query_one("#layout-input", TextArea).text.strip() or None
        width_str = self.query_one("#width-input", Input).value.strip()
        height_str = self.query_one("#height-input", Input).value.strip()
        scale_str = self.query_one("#scale-input", Input).value.strip()
        display_mode = str(cast("Select[str]", self.query_one("#display-mode", Select)).value)

        self.run_worker_query(
            sql=sql,
            source=Path(source) if source is not None else None,
            transform=transform,
            plot_type=str(plot_type),
            layout_str=layout_str,
            width=int(width_str) if width_str else None,
            height=int(height_str) if height_str else None,
            scale=float(scale_str) if scale_str else None,
            display_mode=display_mode,
        )

    def set_status(
        self,
        message: str,
    ) -> None:
        """
        Surface a status message as a notification.

        Messages starting with ``"Error"`` are shown with error
        severity; everything else is informational. The worker thread
        routes all of its progress updates through this method.

        Parameters
        ----------
        message
            Status text to display in the notification toast.

        See Also
        --------
        TuiPlotApp.run_worker_query : Worker reporting progress through this method.

        Examples
        --------
        >>> from mayutils.interfaces.code.tui.tuiplot import TuiPlotApp
        >>> TuiPlotApp().set_status("Ready")  # doctest: +SKIP
        """
        severity = "error" if message.startswith("Error") else "information"
        self.notify(message, severity=severity)

    def show_output(
        self,
        mode: str,
    ) -> None:
        """
        Toggle visibility of the result table and image based on *mode*.

        Shows the inline image widget and hides the table for
        ``"plot"``, and does the reverse for the DataFrame modes, so
        only one result widget is ever visible at a time.

        Parameters
        ----------
        mode
            Display mode; ``"plot"`` shows the image, anything else the table.

        See Also
        --------
        TuiPlotApp.populate_table : Fills the table shown in DataFrame modes.
        TuiPlotApp.show_image : Sets the image shown in plot mode.

        Examples
        --------
        >>> from mayutils.interfaces.code.tui.tuiplot import TuiPlotApp
        >>> TuiPlotApp().show_output("plot")  # doctest: +SKIP
        """
        table = cast("DataTable[str]", self.query_one("#result-table", DataTable))
        image = self.query_one("#result-image", Image)
        if mode == "plot":
            table.styles.display = "none"
            image.styles.display = "block"
        else:
            table.styles.display = "block"
            image.styles.display = "none"

    def populate_table(
        self,
        df: pd.DataFrame,
    ) -> None:
        """
        Populate the result table with *df*.

        Clears any previous contents, resets the index so it appears as
        a leading column, and adds every value stringified so the
        ``DataTable`` can render arbitrary dtypes.

        Parameters
        ----------
        df
            DataFrame whose rows and columns fill the result table.

        See Also
        --------
        TuiPlotApp.show_output : Makes the populated table visible.

        Examples
        --------
        >>> from mayutils.interfaces.code.tui.tuiplot import TuiPlotApp
        >>> TuiPlotApp().populate_table(df)  # doctest: +SKIP
        """
        table = cast("DataTable[str]", self.query_one("#result-table", DataTable))
        table.clear(columns=True)
        show_df = df.reset_index()
        for column in show_df.columns:
            table.add_column(str(column), key=str(column))
        for row in show_df.itertuples(index=False):
            table.add_row(*[str(value) for value in row])

    def show_image(
        self,
        image: PILImage.Image,
    ) -> None:
        """
        Set the inline image widget content.

        Assigns the PIL image to the ``textual-image`` widget in the
        result panel, which re-renders it using the terminal's best
        available graphics protocol.

        Parameters
        ----------
        image
            Decoded PIL image to render inline.

        See Also
        --------
        TuiPlotApp.show_output : Makes the image widget visible.
        render_png : Producer of the PNG bytes decoded into this image.

        Examples
        --------
        >>> from mayutils.interfaces.code.tui.tuiplot import TuiPlotApp
        >>> TuiPlotApp().show_image(image)  # doctest: +SKIP
        """
        self.query_one("#result-image", Image).image = image

    @work(thread=True)
    def run_worker_query(
        self,
        *,
        sql: str | None,
        source: Path | None,
        transform: str | None,
        plot_type: str,
        layout_str: str | None,
        width: int | None,
        height: int | None,
        scale: float | None,
        display_mode: str,
    ) -> None:
        """
        Load, transform and display the data on a worker thread.

        Runs the full pipeline off the UI thread — load, optional
        transform, then either table population or figure building and
        PNG rendering — marshalling every UI update back through
        ``call_from_thread`` and surfacing any failure as an error
        status rather than crashing the app.

        Parameters
        ----------
        sql
            Inline SQL query string, or ``None`` when *source* is used.
        source
            Path to a ``.sql`` or data file, or ``None`` when *sql* is used.
        transform
            Optional Python expression applied to the loaded DataFrame.
        plot_type
            Chart style name coerced to :class:`PlotType`.
        layout_str
            Optional Python literal mapping of figure layout overrides.
        width
            Image width in pixels; defaults to the terminal width.
        height
            Image height in pixels; defaults to the terminal height.
        scale
            Image scale factor; defaults to ``DEFAULT_SCALE``.
        display_mode
            One of ``"plot"``, ``"dataframe"`` or ``"sample"``.

        See Also
        --------
        TuiPlotApp.action_run_query : UI action dispatching this worker.
        load_data : Data loading step executed first.
        make_figure : Figure construction step for plot mode.

        Examples
        --------
        >>> from mayutils.interfaces.code.tui.tuiplot import TuiPlotApp
        >>> TuiPlotApp().action_run_query()  # doctest: +SKIP
        """
        with may_require_extras():
            from PIL import Image as PILImage

        try:
            self.call_from_thread(self.set_status, "Loading data...")
            df = load_data(
                sql=sql,
                source=source,
                reader_factory=self.get_reader,
            )
            self.call_from_thread(
                self.set_status,
                f"Data loaded: {len(df)} rows, {len(df.columns)} cols",
            )

            if transform:
                self.call_from_thread(self.set_status, "Applying transform...")
                data = eval_transform(df, expression=transform)
            else:
                data = df

            if display_mode in ("dataframe", "sample"):
                shown = data if display_mode == "dataframe" else data.sample(min(20, len(data)))
                self.call_from_thread(self.populate_table, shown)
                self.call_from_thread(self.show_output, display_mode)
                self.call_from_thread(self.set_status, "Ready")
                return

            self.call_from_thread(self.set_status, "Building figure...")
            figure = make_figure(data, plot=PlotType(plot_type))

            if layout_str:
                figure.update_layout(**ast.literal_eval(layout_str))

            terminal = shutil.get_terminal_size()

            self.call_from_thread(self.set_status, "Rendering PNG...")
            png = render_png(
                figure,
                width=width or terminal.columns * PX_PER_COLUMN,
                height=height or (terminal.lines - 4) * PX_PER_ROW,
                scale=scale or DEFAULT_SCALE,
            )

            self.call_from_thread(self.show_image, PILImage.open(io.BytesIO(png)))
            self.call_from_thread(self.show_output, "plot")
            self.call_from_thread(self.set_status, "Ready")

        except Exception as err:  # noqa: BLE001  (worker thread must surface, not crash)
            self.call_from_thread(self.set_status, f"Error: {err}")


def tui(
    *,
    reader: QueryReader | None = None,
    reader_kwargs: Mapping[str, Any] | None = None,
) -> None:
    """
    Launch the interactive TUI.

    Constructs a :class:`TuiPlotApp` with the given reader
    configuration and runs it until the user quits. This is the path
    taken by :func:`main` when the CLI is invoked without flags.

    Parameters
    ----------
    reader
        Query reader used to execute SQL, or ``None`` to build one from
        the environment on first use.
    reader_kwargs
        Keyword overrides forwarded to
        :func:`~mayutils.interfaces.data.get_env_reader`.

    See Also
    --------
    TuiPlotApp : The Textual application launched here.
    main : CLI entry point that falls back to this launcher.

    Examples
    --------
    >>> from mayutils.interfaces.code.tui.tuiplot import tui
    >>> tui()  # doctest: +SKIP
    """
    TuiPlotApp(
        reader=reader,
        reader_kwargs=reader_kwargs,
    ).run()


@app.command()
def main(
    *,
    sql: str | None = Option(
        None,
        "--sql",
        help="SQL query string.",
    ),
    source: Path | None = Option(  # noqa: B008
        None,
        "--file",
        help="Path to a .sql query file or a data file (.csv, .parquet, ...).",
    ),
    spec: Path | None = Option(  # noqa: B008
        None,
        "--spec",
        help="Path to a YAML spec file.",
    ),
    transform: str | None = Option(
        None,
        "--transform",
        help="Python expression using df, returning DataFrame/Series.",
    ),
    plot: PlotType | None = Option(  # noqa: B008
        None,
        "--plot",
        help="Plot type.",
    ),
    x: str | None = Option(
        None,
        "--x",
        help='X column name, or "index".',
    ),
    width: int | None = Option(
        None,
        "--width",
        help="Image width in pixels (default: terminal width).",
    ),
    height: int | None = Option(
        None,
        "--height",
        help="Image height in pixels.",
    ),
    scale: float | None = Option(
        None,
        "--scale",
        help="Image scale factor.",
    ),
    env_file: Path | None = Option(  # noqa: B008
        None,
        "--env-file",
        help="Dotenv file used to build the environment reader.",
    ),
    reader_args: str | None = Option(
        None,
        "--reader-args",
        help="YAML/JSON mapping of overrides forwarded to get_env_reader.",
    ),
    print_head: bool = Option(
        False,  # noqa: FBT003
        "--print-head",
        help="Print df.head().",
    ),
    print_cols: bool = Option(
        False,  # noqa: FBT003
        "--print-cols",
        help="Print column names.",
    ),
) -> None:
    """
    Query, transform and plot data in the terminal; no flags launches the TUI.

    With flags, runs the one-shot pipeline: merge the spec file with
    the command-line options, load the DataFrame, optionally print and
    transform it, build the figure, render it to a PNG sized to the
    terminal and display it via kitty's ``icat``. Fatal errors are
    reported through :func:`die` rather than raw tracebacks.

    Parameters
    ----------
    sql
        Inline SQL query string, mutually exclusive with *source*.
    source
        Path to a ``.sql`` query file or a data file, via ``--file``.
    spec
        Path to a YAML spec file supplying option defaults.
    transform
        Python expression using ``df``, returning a DataFrame or Series.
    plot
        Plot type; defaults to the spec value or ``line``.
    x
        X column name, or ``"index"`` to plot against the index.
    width
        Image width in pixels; defaults to the terminal width.
    height
        Image height in pixels; defaults to ``DEFAULT_HEIGHT``.
    scale
        Image scale factor; defaults to ``DEFAULT_SCALE``.
    env_file
        Dotenv file used to build the environment reader.
    reader_args
        YAML/JSON mapping of overrides forwarded to
        :func:`~mayutils.interfaces.data.get_env_reader`.
    print_head
        Whether to print ``df.head()`` after loading.
    print_cols
        Whether to print the column names after loading.

    See Also
    --------
    tui : Interactive fallback used when no flags are passed.
    load_spec : Spec file loader providing option defaults.
    load_data : Data loading step shared with the TUI.

    Examples
    --------
    >>> from mayutils.interfaces.code.tui.tuiplot import main
    >>> main(sql="SELECT 1 AS one", print_head=True)  # doctest: +SKIP
    """
    with may_require_extras():
        import yaml
        from rich.traceback import install as rich_traceback_install

    rich_traceback_install(show_locals=True, extra_lines=3)
    set_template(template="base")

    reader_kwargs_data: object = yaml.safe_load(stream=reader_args) if reader_args else {}
    if not isinstance(reader_kwargs_data, dict):
        die("--reader-args must be a YAML/JSON mapping")
    reader_kwargs = cast("dict[str, Any]", reader_kwargs_data)
    if env_file is not None:
        reader_kwargs["env_file"] = env_file

    has_args = any(value is not None for value in [sql, source, spec, transform, plot, x, width, height, scale]) or print_head or print_cols
    if not has_args:
        tui(reader_kwargs=reader_kwargs)
        return

    if sql is None and source is None:
        die("one of --sql or --file is required")
    if sql is not None and source is not None:
        die("--sql and --file are mutually exclusive")

    try:
        spec_data = load_spec(spec)

        effective_transform = transform or spec_data.get("transform")
        effective_plot = PlotType(plot or spec_data.get("plot", "line"))
        effective_x: str | None = x if x is not None else spec_data.get("x")
        effective_width = width or spec_data.get("width") or shutil.get_terminal_size().columns * PX_PER_COLUMN
        effective_height = height or spec_data.get("height", DEFAULT_HEIGHT)
        effective_scale = scale or spec_data.get("scale", DEFAULT_SCALE)
        reader_kwargs = dict(cast("Mapping[str, Any]", spec_data.get("reader_args", {}))) | reader_kwargs

        console.print("[cyan]Loading data...[/cyan]")
        df = load_data(
            sql=sql,
            source=source,
            reader_factory=lambda: get_env_reader(**reader_kwargs),
        )
        console.print(f"[green]Rows:[/green] {len(df)}  [green]Cols:[/green] {len(df.columns)}")

        if print_cols:
            console.print(list(df.columns))
        if print_head:
            console.print(df.head())

        if effective_transform:
            console.print("[cyan]Applying transform...[/cyan]")
            data = eval_transform(df, expression=effective_transform)
        else:
            data = df

        console.print("[cyan]Building figure...[/cyan]")
        figure = make_figure(data, plot=effective_plot, x=effective_x)

        console.print("[cyan]Checking kitty support...[/cyan]")
        kitty_supports_images()

        console.print("[cyan]Rendering PNG...[/cyan]")
        png = render_png(
            figure,
            width=effective_width,
            height=effective_height,
            scale=effective_scale,
        )

        console.print("[cyan]Displaying in kitty...[/cyan]")
        display_png_in_kitty(png)
    except (RuntimeError, TypeError, ValueError) as err:
        die(str(err))


if __name__ == "__main__":
    app()
