from typing import Any

from sqlalchemy.sql.schema import MetaData, SchemaItem

from .options import LiteralOption, LiteralOptionType
from .table_from_query import TableFromQueryBase

class IcebergTable(TableFromQueryBase):
    __table_prefixes__ = ...
    _support_structured_types = ...
    @property
    def external_volume(self) -> LiteralOption | None: ...
    @property
    def base_location(self) -> LiteralOption | None: ...
    @property
    def catalog(self) -> LiteralOption | None: ...
    def __init__(
        self,
        name: str,
        metadata: MetaData,
        *args: SchemaItem,
        external_volume: LiteralOptionType = ...,
        base_location: LiteralOptionType = ...,
        **kw: Any,
    ) -> None: ...
