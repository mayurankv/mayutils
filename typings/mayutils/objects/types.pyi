from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")

class RecursiveDict(dict[K, V | "RecursiveDict[K, V]"], Generic[K, V]): ...
