from functools import wraps

from .connection import SnowflakeConnection
from .cursor import DictCursor
from .dbapi import BINARY, DATETIME, NUMBER, ROWID, STRING, Binary, Date, DateFromTicks, Time, TimeFromTicks, Timestamp, TimestampFromTicks
from .errors import (
    DatabaseError,
    DataError,
    Error,
    IntegrityError,
    InterfaceError,
    InternalError,
    NotSupportedError,
    OperationalError,
    ProgrammingError,
    _Warning,
)
from .log_configuration import EasyLoggingConfigPython

apilevel = ...
threadsafety = ...
paramstyle = ...

@wraps(SnowflakeConnection.__init__)
def Connect(**kwargs) -> SnowflakeConnection: ...

connect = ...
SNOWFLAKE_CONNECTOR_VERSION = ...
__version__ = ...
__all__ = [
    "BINARY",
    "DATETIME",
    "NUMBER",
    "ROWID",
    "STRING",
    "Binary",
    "DataError",
    "DatabaseError",
    "Date",
    "DateFromTicks",
    "DictCursor",
    "EasyLoggingConfigPython",
    "Error",
    "IntegrityError",
    "InterfaceError",
    "InternalError",
    "NotSupportedError",
    "OperationalError",
    "ProgrammingError",
    "SnowflakeConnection",
    "Time",
    "TimeFromTicks",
    "Timestamp",
    "TimestampFromTicks",
    "_Warning",
    "apilevel",
    "connect",
    "paramstyle",
    "threadsafety",
]
