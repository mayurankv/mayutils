from collections.abc import Mapping
from typing import Any, Self, cast

from mayutils.core.extras import may_require_extras
from mayutils.objects.types import RecursiveMapping

with may_require_extras():
    import plotly.graph_objects as go


def build_icicle(
    icicle_dict: RecursiveMapping[str, float],
    /,
) -> tuple[list[str], list[str], list[str], list[float]]:
    node_values: dict[str, float] = {}

    def calculate_values(
        d: RecursiveMapping[str, float],
        /,
        *,
        path: str = "",
    ) -> float:
        if path in node_values:
            return node_values[path]

        total = 0.0
        for key, value in d.items():
            new_path = f"{path}/{key}" if path else key
            if isinstance(value, Mapping):
                node_value = calculate_values(cast("RecursiveMapping[str, float]", value), path=new_path)
                total += node_value

            else:
                total += value
                node_values[new_path] = value

        node_values[path] = total

        return total

    ids: list[str] = []
    labels: list[str] = []
    parents: list[str] = []
    values: list[float] = []

    def build_lists(
        d: RecursiveMapping[str, float],
        /,
        *,
        parent_path: str = "",
    ) -> None:
        for key, value in d.items():
            current_path = f"{parent_path}/{key}" if parent_path else key

            ids.append(current_path)
            labels.append(key)
            parents.append(parent_path)
            values.append(node_values[current_path])

            if isinstance(value, dict):
                build_lists(
                    value,
                    parent_path=current_path,
                )

    calculate_values(icicle_dict)
    build_lists(icicle_dict)

    return (
        ids,
        labels,
        parents,
        values,
    )


class Icicle(go.Icicle):
    @classmethod
    def from_dict(
        cls,
        icicle_dict: RecursiveMapping[str, float],
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        ids, labels, parents, values = build_icicle(icicle_dict)

        return cls(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            **kwargs,
        )
