from datetime import datetime, tzinfo

from .converter import SnowflakeConverter

logger = ...

class SnowflakeConverterIssue23517(SnowflakeConverter):
    def __init__(self, **kwargs) -> None: ...
    @staticmethod
    def create_timestamp_from_string(value: str, scale: int, tz: tzinfo | None = ...) -> datetime: ...
