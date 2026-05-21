from enum import StrEnum


class TraceType(StrEnum):
    LINE = "line"
    SCATTER = "scatter"
    ECDF = "ecdf"
    KDE = "kde"
    NULL = "null"
    BAR3D = "bar3d"
