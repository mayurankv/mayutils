from pathlib import Path
from typing import Callable, Literal, Optional, Self
from great_tables import GT
from pandas import (
    DataFrame,
    ExcelWriter,
    Index,
    MultiIndex,
    Series,
    to_datetime,
    to_numeric,
)
from pandas.io.formats.style import Styler as Style
from pandas.api.extensions import (
    register_dataframe_accessor,
    register_series_accessor,
    register_index_accessor,
)
from dataframe_image._pandas_accessor import (
    disable_max_image_pixels,
    generate_html,
    prepare_converter,
    save_image,
)
import numpy as np
from mayutils.objects.colours import Colour
from mayutils.export import OUTPUT_FOLDER

DATA_FOLDER = OUTPUT_FOLDER / "Data"


class Styler(Style):
    def map(
        self,
        style_map: Callable,
        *args,
        **kwargs,
    ) -> Self:
        return super().map(  # type: ignore
            kwargs.pop("func", style_map),
            *args,
            **kwargs,
        )

    @property
    def df(
        self,
    ) -> DataFrame:
        return self.data  # type: ignore

    def ignore_null(
        self,
    ) -> Self:
        def style_map(value):
            return (
                "color: rgba(0,0,0,0); background-color: rgba(0, 0, 0, 0);"
                if np.isnan(value)
                else ""
            )

        return self.map(style_map=style_map)

    def change_map(
        self,
        max_abs: float,
        reference_value: float = 0,
        scaling: float = 0.6,
    ) -> Self:
        def style_map(
            val: float,
        ) -> str:
            if val < reference_value:
                return f"background-color: rgba(226, 0, 0, {scaling * abs(val - reference_value) / max_abs});"
            elif val > reference_value:
                return f"background-color: rgba(0, 255, 154, {scaling * abs(val - reference_value) / max_abs});"
            else:
                return "background-color: rgba(0, 0, 0, 0);"

        return self.map(style_map=style_map)

    def row_format(
        self,
        formatter: dict[str, Callable | str],
    ) -> Self:
        for row, row_formatter in formatter.items():
            if row in self.index:
                row_num = self.index.get_loc(row)

                for col_num in range(len(self.columns)):
                    self._display_funcs[(row_num, col_num)] = (  # type: ignore
                        row_formatter
                        if not isinstance(row_formatter, str)
                        else lambda x: format(x, row_formatter)  # type: ignore
                    )

        return self

    def __repr__(
        self,
    ) -> str:
        return super(Styler, self.ignore_null()).__repr__()

    def save(
        self,
        path: Path | str,
        dark: bool = False,
        fontsize: int = 14,
        dpi: int = 200,
        max_rows: Optional[int] = None,
        max_cols: Optional[int] = None,
    ) -> None:
        path = Path(path)
        table_conversion = "selenium"
        chrome_path = None
        use_mathjax = True
        crop_top = True

        converter = prepare_converter(
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

        html = generate_html(
            obj=self,  # type: ignore
            filename=path,
            max_rows=max_rows,
            max_cols=max_cols,
        )

        base = Colour.parse(colour="rgb(31, 36, 48)" if dark else "#FFFFFF")
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
            </style>
        """.format(
            base=base.to_str(),
            even=(
                Colour.blend(
                    foreground=Colour.parse(colour="rgba(130, 130, 130, 0.08)"),
                    background=base,
                )
                .round()
                .to_str()
            ),
            header=(
                Colour.blend(
                    foreground=Colour.parse(colour="rgba(130, 130, 130, 0.16)"),
                    background=base,
                )
                .round()
                .to_str()
            ),
            font_colour=font_colour,
        )

        with disable_max_image_pixels():
            img_str = converter(style + html)

        save_image(
            img_str=img_str,
            filename=path,
        )

        return


class DataframeUtilsAccessor(object):
    def __init__(
        self,
        df: DataFrame,
    ) -> None:
        self.df = df

    def save(
        self,
        path: Path | str,
        *args,
        **kwargs,
    ) -> None:
        path = Path(path)

        if path.suffix in [".png", ".jpeg", ".jpg", ".pdf", ".svg", ".eps"]:
            return self.styler.save(
                path=path,
                *args,
                **kwargs,
            )
        elif path.suffix == ".parquet":
            self.df.to_parquet(
                path=path,
                index=True,
            )
        elif path.suffix == ".feather":
            raise NotImplementedError("Feather not implemented")
            self.df.to_feather(path)
        elif path.suffix == ".csv":
            self.df.to_csv(
                path_or_buf=path,
                index=True,
            )
        elif path.suffix == ".xlsx":
            with ExcelWriter(path=path) as excel_writer:
                self.df.to_excel(
                    excel_writer=excel_writer,
                    index=True,
                )
        else:
            # TODO:
            raise NotImplementedError(f"Format {path.suffix} is an unsupported format")

    def max_abs(
        self,
        reference_value: float = 0,
    ) -> float:
        min_neg: float = min(
            float((self.df - reference_value).min(axis=None)),  # type: ignore
            0,
        )
        max_pos: float = max(
            float((self.df - reference_value).max(axis=None)),  # type: ignore
            0,
        )
        max_abs = max(max_pos, -min_neg)
        if max_abs == 0:
            raise ValueError(f"All values are constant equal to {reference_value}")

        return max_abs

    def change_map(
        self,
        reference_value: float = 0,
        scaling: float = 0.6,
    ) -> Styler:
        return self.styler.change_map(
            max_abs=self.max_abs(
                reference_value=reference_value,
            ),
            reference_value=reference_value,
            scaling=scaling,
        )

    @property
    def styler(
        self,
    ) -> Styler:
        return Styler(data=self.df)

    @property
    def gt(
        self,
    ) -> GT:
        return GT(data=self.df)

    def map_dtypes(
        self,
        mapper: dict[str, str | type],
        datetime_format: str = "%Y-%m-%d %H:%M:%S",
        date_format: str = "%Y-%m-%d %H:%M:%S",
        time_format: str = "%H:%M:%S",
    ) -> DataFrame:
        def convert_datetime(
            series: Series,
            datetime_type: Literal["datetime", "date", "time"],
        ) -> Series:
            if datetime_type == "datetime":
                return to_datetime(series, format=datetime_format)
            elif datetime_type == "date":
                return to_datetime(series, format=date_format).dt.date
            elif datetime_type == "time":
                return to_datetime(series, format=time_format).dt.time
            else:
                raise ValueError(f"Unknown datetime_type: {datetime_type}")

        for col, dtype in mapper.items():
            try:
                self.df[col] = (
                    convert_datetime(
                        series=self.df[col],
                        datetime_type=dtype,  # type: ignore
                    )
                    if dtype in ["datetime", "date", "time"]
                    else to_numeric(self.df[col])
                    if dtype == "numeric"
                    else self.df[col].astype(dtype)  # type: ignore
                )
            except (
                KeyError,
                ValueError,
                TypeError,
            ):
                raise TypeError(f"Error parsing dtype {dtype} for columns {col}")

        return self.df


class SeriesUtilsAccessor(object):
    def __init__(
        self,
        series: Series,
    ) -> None:
        self.series = series

    def save(
        self,
        path: Path | str,
    ) -> None:
        # TODO: Finish
        raise NotImplementedError(
            "Not implemented for series yet: leverage existing df methods"
        )


class IndexUtilsAccessor(object):
    def __init__(
        self,
        index: Index,
    ) -> None:
        self.index = index

    def get_multiindex(
        self,
        transpose: bool = False,
    ) -> list[list]:
        if not isinstance(self.index, MultiIndex):
            raise TypeError("Index is not of type MultiIndex")

        return (
            list(map(list, self.index))
            if not transpose
            else list(
                list(self.index.get_level_values(level=level))
                for level in range(len(self.index.names))
            )
        )


# def save_dataframe(
#     df,
#     path: Path,
#     format: Literal["parquet", "csv", "feather"] = "parquet",
# ):
#     if format not in ("parquet", "feather", "csv"):
#         raise ValueError("Format must be one of: 'parquet', 'feather', 'csv'")

#     df_module = type(df).__module__

#     if df_module in ["polars"]:
#         if format == "parquet":
#             df.write_parquet(path)
#         elif format == "feather":
#             df.write_ipc(path)
#         elif format == "csv":
#             df.write_csv(path)

#     elif df_module in ["pyarrow"]:
#         import pyarrow.parquet as pq
#         import pyarrow.feather as feather

#         if format == "parquet":
#             pq.write_table(
#                 table=df,
#                 where=path,
#             )
#         elif format == "feather":
#             feather.write_feather(
#                 df=df,
#                 dest=path,
#             )
#         elif format == "csv":
#             # pyarrow can't write CSVs natively; convert to pandas
#             df.to_pandas().to_csv(
#                 path,
#                 index=True,
#             )

#     elif df_module in ["datatable"]:
#         if format == "csv":
#             df.to_csv(path)
#         elif format == "parquet":
#             df.to_pandas().to_parquet(
#                 path,
#                 index=True,
#             )
#         elif format == "feather":
#             df.to_pandas().to_feather(path)

#     elif df_module in ["pyspark.sql"]:
#         if format == "csv":
#             df.write.mode("overwrite").option("header", True).csv(path)
#         elif format == "parquet":
#             df.write.mode("overwrite").parquet(path)
#         elif format == "feather":
#             raise NotImplementedError("Spark does not support Feather format.")

#     elif df_module in ["dask.dataframe"]:
#         if format == "csv":
#             df.to_csv(
#                 path,
#                 index=True,
#                 single_file=True,
#             )
#         elif format == "parquet":
#             df.to_parquet(
#                 path,
#                 write_index=True,
#             )
#         elif format == "feather":
#             df.compute().to_feather(path)  # must convert to pandas
#     else:
#         raise TypeError(f"Unsupported DataFrame type: {type(df)}")


def setup_dataframes() -> None:
    register_dataframe_accessor(name="utils")(DataframeUtilsAccessor)
    register_series_accessor(name="utils")(SeriesUtilsAccessor)
    register_index_accessor(name="utils")(IndexUtilsAccessor)
    # register_styler_accessor(name="utils")(StylerUtilsAccessor)


# import dataframe_image as dfi
# async def save_dataframe(
#     df: DataFrame | Styler,
#     filename: str,
# ) -> None:
#     await dfi.export_async(
#         obj=df,  # type: ignore
#         filename=DATA_FOLDER / f"{filename}.png",
#         table_conversion="playwright",
#         use_mathjax=True,
#         chrome_path=None,
#     )
