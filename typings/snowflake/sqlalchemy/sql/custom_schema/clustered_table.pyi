from typing import Any

from sqlalchemy.sql.schema import MetaData, SchemaItem

from .custom_table_base import CustomTableBase
from .options.as_query_option import AsQueryOption
from .options.cluster_by_option import ClusterByOptionType

class ClusteredTableBase(CustomTableBase):
    @property
    def cluster_by(self) -> AsQueryOption | None: ...
    def __init__(self, name: str, metadata: MetaData, *args: SchemaItem, cluster_by: ClusterByOptionType = ..., **kw: Any) -> None: ...
