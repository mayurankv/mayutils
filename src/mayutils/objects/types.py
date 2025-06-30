from __future__ import annotations
from typing import TypeVar, Generic

K = TypeVar("K")
V = TypeVar("V")


class RecursiveDict(
    dict[K, V | "RecursiveDict[K, V]"],
    Generic[K, V],
):
    pass
