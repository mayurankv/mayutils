from collections.abc import Sequence
from typing import Any, NamedTuple


class SubplotRef(NamedTuple):
    subplot_type: str
    layout_keys: tuple[str, ...]
    trace_kwargs: dict[str, Any]


class SubplotDomain(NamedTuple):
    x: tuple[float, float]
    y: tuple[float, float]


class SubplotXY(NamedTuple):
    xaxis: Any
    yaxis: Any


def _build_subplot_title_annotations(
    subplot_titles: Sequence[str],
    list_of_domains: Sequence[tuple[float, float]],
    title_edge: str = ...,
    offset: float = ...,
) -> list[dict[str, Any]]: ...
