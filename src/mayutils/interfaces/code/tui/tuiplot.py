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
    import kaleido
    import pandas as pd
    import plotly.graph_objects as go
    import textual_image.renderable  # pyright: ignore[reportUnusedImport] # noqa: F401
    import typer
    import yaml
    from PIL import Image as PILImage
    from rich.console import Console
    from rich.traceback import install as rich_traceback_install
    from textual import work
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.widgets import (
        Button,
        DataTable,
        Header,
        Input,
        Label,
        Rule,
        Select,
        Switch,
        TabbedContent,
        TabPane,
        TextArea,
    )
    from textual_image.widget import Image

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from textual.app import ComposeResult
    from textual.binding import BindingType

    from mayutils.data.read import QueryReader


console = Console(stderr=True)

app = typer.Typer(
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
    """Supported chart styles for :func:`make_figure`."""

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

    Raises
    ------
    typer.Exit
        Always, carrying the given exit code.
    """
    console.print(f"[bold red]error:[/bold red] {message}")

    raise typer.Exit(code)


def load_spec(
    path: Path | None,
    /,
) -> dict[str, Any]:
    """
    Load a YAML spec file into a mapping, or an empty one when *path* is ``None``.

    Returns
    -------
        The parsed spec mapping.

    Raises
    ------
    TypeError
        If the file parses to something other than a mapping.
    """
    if path is None:
        return {}

    data = cast("object", yaml.safe_load(path.read_text(encoding="utf-8")))
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

    Returns
    -------
        The transformed DataFrame (a Series result is promoted to a frame).

    Raises
    ------
    TypeError
        If the expression returns neither a DataFrame nor a Series.
    """
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

    Returns
    -------
        The loaded DataFrame.

    Raises
    ------
    ValueError
        If neither *sql* nor *source* is provided.
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

    Returns
    -------
        The constructed figure.

    Raises
    ------
    ValueError
        If no y columns remain or the plot type is unsupported.
    """
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

    Returns
    -------
        The encoded PNG image.
    """
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

    Raises
    ------
    RuntimeError
        If ``kitten icat`` reports that image display is unavailable.
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

    Raises
    ------
    RuntimeError
        If ``kitten icat`` exits with a non-zero status.
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
    """Interactive TUI for querying, transforming and plotting tabular data."""

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
        super().__init__(*args, **kwargs)

        self.reader = reader
        self.reader_kwargs = dict(reader_kwargs or {})

    def get_reader(
        self,
    ) -> QueryReader:
        """
        Return the injected reader, building one from the environment on first use.

        Returns
        -------
            The reader used to execute SQL queries.
        """
        if self.reader is None:
            self.reader = get_env_reader(**self.reader_kwargs)

        return self.reader

    def compose(
        self,
    ) -> ComposeResult:
        """
        Build the widget tree.

        Yields
        ------
            The app's widgets.
        """
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
        """Toggle between the full layout and a fullscreen result panel."""
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
        """Swap between the inline SQL editor and the file path input."""
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
        """Run the query when the Run button is pressed."""
        if event.button.id == "run-btn":
            self.action_run_query()

    def action_run_query(
        self,
    ) -> None:
        """Collect the form state and dispatch the query worker."""
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
        """Surface a status message as a notification."""
        severity = "error" if message.startswith("Error") else "information"
        self.notify(message, severity=severity)

    def show_output(
        self,
        mode: str,
    ) -> None:
        """Toggle visibility of the result table and image based on *mode*."""
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
        """Populate the result table with *df*."""
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
        """Set the inline image widget content."""
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
        """Load, transform and display the data on a worker thread."""
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
    """Launch the interactive TUI."""
    TuiPlotApp(
        reader=reader,
        reader_kwargs=reader_kwargs,
    ).run()


@app.command()
def main(
    *,
    sql: str | None = typer.Option(
        None,
        "--sql",
        help="SQL query string.",
    ),
    source: Path | None = typer.Option(  # noqa: B008
        None,
        "--file",
        help="Path to a .sql query file or a data file (.csv, .parquet, ...).",
    ),
    spec: Path | None = typer.Option(  # noqa: B008
        None,
        "--spec",
        help="Path to a YAML spec file.",
    ),
    transform: str | None = typer.Option(
        None,
        "--transform",
        help="Python expression using df, returning DataFrame/Series.",
    ),
    plot: PlotType | None = typer.Option(  # noqa: B008
        None,
        "--plot",
        help="Plot type.",
    ),
    x: str | None = typer.Option(
        None,
        "--x",
        help='X column name, or "index".',
    ),
    width: int | None = typer.Option(
        None,
        "--width",
        help="Image width in pixels (default: terminal width).",
    ),
    height: int | None = typer.Option(
        None,
        "--height",
        help="Image height in pixels.",
    ),
    scale: float | None = typer.Option(
        None,
        "--scale",
        help="Image scale factor.",
    ),
    env_file: Path | None = typer.Option(  # noqa: B008
        None,
        "--env-file",
        help="Dotenv file used to build the environment reader.",
    ),
    reader_args: str | None = typer.Option(
        None,
        "--reader-args",
        help="YAML/JSON mapping of overrides forwarded to get_env_reader.",
    ),
    print_head: bool = typer.Option(
        False,  # noqa: FBT003
        "--print-head",
        help="Print df.head().",
    ),
    print_cols: bool = typer.Option(
        False,  # noqa: FBT003
        "--print-cols",
        help="Print column names.",
    ),
) -> None:
    """Query, transform and plot data in the terminal; no flags launches the TUI."""
    rich_traceback_install(show_locals=True, extra_lines=3)
    set_template(template="base")

    reader_kwargs_data: object = yaml.safe_load(reader_args) if reader_args else {}
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
