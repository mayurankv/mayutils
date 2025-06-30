from __future__ import annotations
from typing import TypeVar, Generic

T = TypeVar("T")


class RecursiveDict(dict[str, "T | RecursiveDict[T]"], Generic[T]):
    pass
