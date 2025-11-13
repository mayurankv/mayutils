from _typeshed import Incomplete
from great_tables import GT
from mayutils.export import OUTPUT_FOLDER as OUTPUT_FOLDER
from mayutils.objects.colours import Colour as Colour
from mayutils.objects.datetime import Interval as Interval
from pandas import DataFrame, Index, Series
from pandas.io.formats.style import Styler as Style
from pathlib import Path
from typing import Callable, Self

DataframeBackends: Incomplete
DataFrames: Incomplete
DATA_FOLDER: Incomplete

class Styler(Style):
    def map(self, style_map: Callable, *args, **kwargs) -> Self: ...
    @property
    def df(self) -> DataFrame: ...
    def ignore_null(self) -> Self: ...
    def change_map(
        self,
        max_abs: float,
        reference_value: float = 0,
        scaling: float = 0.6,
        columns: list | Index | None = None,
        max_colour: Colour = ...,
        min_colour: Colour = ...,
    ) -> Self: ...
    def row_format(self, formatter: dict[str, Callable | str]) -> Self: ...
    def interact(self, *args, **kwargs) -> None: ...
    def hide(self, *args, **kwargs) -> Self: ...
    def save(
        self,
        path: Path | str,
        dark: bool = False,
        fontsize: int = 14,
        dpi: int = 200,
        use_mathjax: bool = True,
        max_rows: int | None = None,
        max_cols: int | None = None,
        additional_css: str = "",
    ) -> Path: ...

class DataframeUtilsAccessor:
    df: Incomplete
    def __init__(self, df: DataFrame) -> None: ...
    def save(self, path: Path | str, **kwargs) -> Path: ...
    def interact(self, *args, **kwargs) -> None: ...
    def max_abs(
        self, reference_value: float = 0, columns: list | Index | None = None
    ) -> float: ...
    def rename_index(self, index_name: str) -> DataFrame: ...
    def cutoff(
        self, cutoff: int, aggregation: Callable[[DataFrame], Series] | None = ...
    ) -> DataFrame: ...
    def change_map(
        self,
        reference_value: float = 0,
        scaling: float = 0.6,
        columns: list | None = None,
    ) -> Styler: ...
    @property
    def styler(self) -> Styler: ...
    @property
    def gt(self) -> GT: ...
    def map_dtypes(
        self,
        mapper: dict[str, str | type],
        datetime_format: str = "%Y-%m-%d %H:%M:%S",
        date_format: str = "%Y-%m-%d %H:%M:%S",
        time_format: str = "%H:%M:%S",
    ) -> DataFrame: ...

class SeriesUtilsAccessor:
    series: Incomplete
    def __init__(self, series: Series) -> None: ...
    def save(self, path: Path | str) -> Path: ...
    def ground(self, interval: Interval | None = None) -> Series: ...

class IndexUtilsAccessor:
    index: Incomplete
    def __init__(self, index: Index) -> None: ...
    def get_multiindex(self, transpose: bool = False) -> list[list]: ...

def to_parquet(
    df: DataFrames,
    path: Path | str,
    dataframe_backend: DataframeBackends | None = None,
    **kwargs,
) -> None: ...
def read_parquet(
    path: Path | str, dataframe_backend: DataframeBackends = "pandas", **kwargs
) -> DataFrames: ...
def setup_dataframes() -> None: ...
def column_to_excel(column: int) -> str: ...
