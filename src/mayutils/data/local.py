from pathlib import Path

from pandas import DataFrame, read_csv, read_excel, read_parquet


class DataFile(object):
    def __init__(
        self,
        path: Path | str,
        validate: bool = True,
        *args,
        **kwargs,
    ) -> None:
        self.path = Path(path)
        if validate and not self.exists():
            raise ValueError("No such file exists")

        return super().__init__(
            *args,
            **kwargs,
        )

    def exists(
        self,
    ) -> bool:
        return self.path.exists() and self.path.is_file()

    def to_pandas(
        self,
    ) -> DataFrame:
        if self.path.suffix == ".parquet":
            return read_parquet(path=self.path)
        elif self.path.suffix == ".feather":
            raise NotImplementedError("Feather not implemented")
        elif self.path.suffix == ".csv":
            return read_csv(
                filepath_or_buffer=self.path,
                index_col=0,
            )
        elif self.path.suffix == ".xlsx":
            return read_excel(
                io=self.path,
                index_col=0,
            )
        else:
            raise ValueError(
                f"Format {self.path.suffix} cannot be extracted to pandas DataFrame"
            )

    def convert(
        self,
    ) -> None:
        raise NotImplementedError("Conversion not supported yet")
