from typing import Any

from sqlalchemy.sql.schema import MetaData, SchemaItem

from .clustered_table import ClusteredTableBase
from .options.as_query_option import AsQueryOption, AsQueryOptionType

class TableFromQueryBase(ClusteredTableBase):
    @property
    def as_query(self) -> AsQueryOption | None: ...
    def __init__(self, name: str, metadata: MetaData, *args: SchemaItem, as_query: AsQueryOptionType = ..., **kw: Any) -> None: ...
