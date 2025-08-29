from typing import get_args, Literal

type Scale = Literal["relative", "absolute", "percentage"]
type Operation = Literal[
    "division",
    "normalise",
    "standardise",
    "dot_product",
    "inverse",
    "constant",
    "drop",
]
type Calculations = dict[Operation, dict[str, tuple[str, ...]]]

OPERATIONS: tuple = get_args(Operation.__value__)
