from typing import Any

from sqlalchemy.sql.schema import MetaData, SchemaItem

from .options import IdentifierOption, IdentifierOptionType, KeywordOptionType, TargetLagOption, TargetLagOptionType
from .table_from_query import TableFromQueryBase

class DynamicTable(TableFromQueryBase):
    __table_prefixes__ = ...
    _support_primary_and_foreign_keys = ...
    _required_parameters = ...
    @property
    def warehouse(self) -> IdentifierOption | None: ...
    @property
    def target_lag(self) -> TargetLagOption | None: ...
    def __init__(
        self,
        name: str,
        metadata: MetaData,
        *args: SchemaItem,
        warehouse: IdentifierOptionType = ...,
        target_lag: TargetLagOptionType | KeywordOptionType = ...,
        refresh_mode: KeywordOptionType = ...,
        **kw: Any,
    ) -> None: ...
