from typing import Literal, TypedDict


type DisplayType = Literal["notebook", "slides_light", "slides_dark"]
type PlotType = Literal["plotly", "matplotlib"]

type Scale = Literal["relative", "absolute", "percentage"]
type Operation = Literal[
    "division", "normalise", "standardise", "dot_product", "inverse", "constant", "drop"
]
type Calculations = dict[Operation, dict[str, tuple[str, ...]]]


type Interval = Literal["second", "minute", "hour", "day", "month", "year"]

DataName = str
