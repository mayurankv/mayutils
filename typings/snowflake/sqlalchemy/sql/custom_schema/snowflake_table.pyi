from typing import Any

from sqlalchemy.sql.schema import MetaData, SchemaItem

from .table_from_query import TableFromQueryBase

class SnowflakeTable(TableFromQueryBase):
    def __init__(self, name: str, metadata: MetaData, *args: SchemaItem, **kw: Any) -> None: ...
