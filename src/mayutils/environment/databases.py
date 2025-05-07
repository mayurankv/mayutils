from typing import Self

from pandas import DataFrame, read_sql
from snowflake.sqlalchemy import URL
from sqlalchemy import Engine, create_engine


class EngineWrapper(object):
    def __init__(
        self,
        engine: Engine,
    ) -> None:
        self.engine = engine

        return

    @classmethod
    def create(
        cls,
        *args,
        **kwargs,
    ) -> Self:
        return cls(
            create_engine(
                *args,
                **kwargs,
            )
        )

    @classmethod
    def via_snowflake(
        cls,
        *args,
        **kwargs,
    ) -> Self:
        return cls.create(URL(*args, **kwargs))

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
