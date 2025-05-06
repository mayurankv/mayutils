from typing import Self
from pandas import DataFrame, read_sql
from sqlalchemy import create_engine
from sqlalchemy import Engine
from snowflake.sqlalchemy import URL


class EngineWrapper(object):
    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        self.engine = create_engine(
            *args,
            **kwargs,
        )

        return

    @classmethod
    def via_snowflake(
        cls,
        *args,
        **kwargs,
    ) -> Self:
        return cls(URL(*args, **kwargs))

    def read_pandas(
        self,
        query_string: str,
        lower_case: bool = True,
        *args,
        **kwargs,
    ) -> DataFrame:
        df: DataFrame = read_sql(  # type: ignore
            sql=query_string,
            con=self.engine,
            *args,
            **kwargs,
        )

        if lower_case:
            df.columns = df.columns.str.lower()

        return df

    def __call__(
        self,
    ) -> Engine:
        return self.engine
