from datetime import datetime
from typing import Literal, Optional, Self

from mayutils.visualisation.graphs.plotly.utilities import (
    map_categorical_array,
    melt_dataframe,
)
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from numpy.typing import ArrayLike
from pandas import DataFrame
from plotly.basedatatypes import BaseTraceType as Trace
from scipy.stats import gaussian_kde

from mayutils.objects.colours import Colour
from mayutils.objects.types import RecursiveDict


class Null(go.Scatter):
    def __init__(
        self,
        x_datetime: bool = False,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(
            x=[] if not x_datetime else pd.to_datetime([datetime.today()]),
            y=[],
            showlegend=False,
            meta="null",
            *args,
            **kwargs,
        )


class Line(go.Scatter):
    _counter = 0

    def __init__(
        self,
        label_name: bool | str = False,
        textposition: str = "middle right",
        *args,
        **kwargs,
    ) -> None:
        mode: str = kwargs.pop("mode", "lines")
        mode += (
            "+text" if label_name is not False and not mode.endswith("+text") else ""
        )
        kwargs["mode"] = mode
        kwargs["textposition"] = textposition

        label_name = (
            kwargs.get("name", None) if label_name is True else label_name
        ) or ""
        kwargs["text"] = [""] * (len(kwargs.get("x", [])) - 1) + [label_name]

        super().__init__(
            meta="line",
            *args,
            **kwargs,
        )

        type(self)._counter += 1
        self._count = type(self)._counter

    @classmethod
    def with_bounds(
        cls,
        x: ArrayLike,
        y: ArrayLike,
        y_upper: list[ArrayLike],
        y_lower: list[ArrayLike],
        max_opacity: float = 0.4,
        *args,
        **kwargs,
    ) -> tuple[Self, ...]:
        if len(y_lower) != len(y_upper):
            raise ValueError("Asymmetric bounds provided")
        last_lower = np.asarray(y)
        last_upper = last_lower
        for lower, upper in zip(y_lower, y_upper):
            if len(lower) != len(y) or len(upper) != len(y):  # type: ignore
                raise ValueError("Y Values of different length provided")
            elif np.any(np.asarray(lower) > last_lower) or np.any(
                np.asarray(upper) < last_upper
            ):
                raise ValueError("Monotonic bounds not passed")

            last_lower = lower
            last_upper = upper

        base_trace = cls(
            x=x,
            y=y,
            line=kwargs.pop("line", {}),
            *[*args],
            **{**kwargs},
        )
        legendgroup = kwargs.pop("legendgroup", f"bounds{base_trace._count}")
        base_trace.legendgroup = legendgroup

        # TODO: Set colour
        color_str = base_trace.line.color or "black"  # type: ignore
        color = Colour.parse(colour=color_str)
        return (
            *[
                cls(
                    x=np.concatenate([x, x[::-1]]),  # type: ignore
                    y=np.concatenate([upper, lower[::-1]]),  # type: ignore
                    fill="toself",
                    showlegend=False,
                    fillcolor=color.to_str(opacity=max_opacity / (1 + len(y_upper))),
                    line=dict(color=color.to_str(opacity=0)),
                    legendgroup=legendgroup,
                    hoverinfo="skip",
                    *[*args],
                    **{
                        key: value
                        for key, value in kwargs.items()
                        if key != "line_color"
                    },
                )
                for lower, upper in zip(y_lower, y_upper)
            ],
            base_trace,
        )

    @classmethod
    def from_bounds_dataframe(
        cls,
        df: DataFrame,
        *args,
        **kwargs,
    ) -> tuple[Self, ...]:
        # TODO: Complete
        raise NotImplementedError("Method incomplete")


class Ecdf(Line):
    def __init__(
        self,
        x: ArrayLike,
        y: Optional[ArrayLike] = None,
        y_shift: float = 0,
        norm: Literal["probability", "percentage", "count"] = "probability",
        mode: Literal["standard", "reversed", "complementary"] = "standard",
        fill: Literal["tozeroy", "tonexty", "toself"] = "toself",
        left_inclusive: bool = False,
        *args,
        **kwargs,
    ) -> None:
        _x = np.asarray(x)
        idx = np.argsort(_x)

        if mode == "reversed":
            idx = np.flip(idx)

        _x = _x[idx]

        if y is None:
            _y = np.ones(shape=len(_x))
        else:
            _y = np.asarray(y)
            if len(_y) != len(_x):
                raise ValueError("x and y arrays are not the same length")

            _y = _y[idx]

        y_sum = np.sum(_y)
        _y = np.cumsum(_y)
        if mode == "complementary":
            _y = y_sum - _y

        if norm == "probability":
            _y = _y / y_sum
        elif norm == "percentage":
            _y = 100 * _y / y_sum

        _y += y_shift

        kwargs["line_shape"] = (
            "hv" if ((mode != "reversed") ^ (not left_inclusive)) else "vh"
        )
        kwargs["fill"] = fill

        if fill == "toself":
            _x = np.insert(_x, 0, _x[-1])
            _y = np.insert(_y, 0, y_shift)
            # np.append(_x, [_x[-1]])
            # _y = np.append(_y, [y_shift])

        super().__init__(
            x=_x,
            y=_y,
            customdata=_y - y_shift,
            hovertemplate="<b>%{fullData.name}</b><br>x: %{x}<br>y: %{customdata}<extra></extra>",
            *args,
            **kwargs,
        )

        self.meta = "ecdf"


class Kde(Line):
    def __init__(
        self,
        x: ArrayLike,
        bandwidth: Optional[float] = None,
        *args,
        **kwargs,
    ) -> None:
        _x = np.asarray(x)
        kde = gaussian_kde(_x, bw_method=bandwidth)

        _x_grid = np.linspace(np.min(_x), np.max(_x), 1000)
        _y = kde(_x_grid)

        super().__init__(
            x=_x_grid,
            y=_y,
            customdata=_x,
            fill=kwargs.pop("fill", "tozeroy"),
            *args,
            **kwargs,
        )

        self.meta = "kde"


class Scatter(go.Scatter):
    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(
            mode="markers",
            meta="scatter",
            *args,
            **kwargs,
        )


class Icicle(go.Icicle):
    @classmethod
    def from_dict(
        cls,
        icicle_dict: RecursiveDict[str, float],
        **kwargs,
    ) -> Self:
        node_values: dict[str, float] = {}

        def calculate_values(
            d: RecursiveDict[str, float],
            path: str = "",
        ) -> float:
            if path in node_values:
                return node_values[path]

            total = 0.0
            for key, value in d.items():
                new_path = f"{path}/{key}" if path else key
                if isinstance(value, dict):
                    node_value = calculate_values(value, new_path)
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
            d: RecursiveDict[str, float],
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
                        d=value,
                        parent_path=current_path,
                    )

        calculate_values(d=icicle_dict)
        build_lists(d=icicle_dict)

        return cls(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            **kwargs,
        )


class Cuboid(go.Mesh3d):
    def __init__(
        self,
        x: tuple[float, float],
        y: tuple[float, float],
        z: tuple[float, float],
        weight: float = 1,
        flatshading: bool = True,
        showscale: bool = False,
        alphahull: float = 1,
        cmin: float = 0,
        cmax: float = 1,
        *args,
        **kwargs,
    ) -> None:
        x0, x1 = x
        y0, y1 = y
        z0, z1 = z

        super().__init__(
            x=[x0, x0, x1, x1, x0, x0, x1, x1],
            y=[y0, y1, y1, y0, y0, y1, y1, y0],
            z=[z0, z0, z0, z0, z1, z1, z1, z1],
            i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
            j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
            k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
            intensity=[weight for _ in range(8)],
            cmin=cmin,
            cmax=cmax,
            alphahull=alphahull,
            flatshading=flatshading,
            showscale=showscale,
            *args,
            **kwargs,
        )


class Bar3d(go.Mesh3d):
    def __init__(
        self,
        x: ArrayLike,
        y: ArrayLike,
        z: ArrayLike,
        w: Optional[ArrayLike] = None,
        showscale: bool = True,
        alphahull: float = 1,
        flatshading: bool = True,
        dx: float = 1,
        dy: float = 1,
        z0: float = 0,
        x_start: float = 0,
        y_start: float = 0,
        z_start: float = 0,
        x_mapping: Optional[ArrayLike] = None,
        y_mapping: Optional[ArrayLike] = None,
        *args,
        **kwargs,
    ) -> None:
        x_arr = np.asarray(x)
        y_arr = np.asarray(y)
        z_arr = np.asarray(z, dtype=np.float64)
        w_arr = (
            np.asarray(w, dtype=np.float64)
            if w is not None
            else np.ones(z_arr.shape, dtype=np.float64)
        )

        if any(len(arr) != len(w_arr) for arr in [x_arr, y_arr, z_arr]):
            raise ValueError("Input arrays are not same length")

        nan_idxs = np.isnan(z_arr)
        self._x_arr = x_arr[~nan_idxs]
        self._y_arr = y_arr[~nan_idxs]
        self._z_arr = z_arr[~nan_idxs]
        self._w_arr = w_arr[~nan_idxs]

        x_arr_numerical = (
            map_categorical_array(
                arr=self._x_arr,
                mapping=x_mapping,
            )
            * dx
        )
        self._x = (
            np.stack([x_arr_numerical - dx / 2, x_arr_numerical + dx / 2], axis=1)[
                np.arange(x_arr_numerical.size)[:, None], [0, 0, 1, 1, 0, 0, 1, 1]
            ].reshape(-1)
            + x_start
        )
        y_arr_numerical = (
            map_categorical_array(
                arr=self._y_arr,
                mapping=y_mapping,
            )
            * dy
        )
        self._y = (
            np.stack([y_arr_numerical - dy / 2, y_arr_numerical + dy / 2], axis=1)[
                np.arange(y_arr_numerical.size)[:, None], [0, 1, 1, 0, 0, 1, 1, 0]
            ].reshape(-1)
            + y_start
        )
        self._z = np.ones(self._z_arr.size * 8, dtype=self._z_arr.dtype) * z0
        self._z[(np.arange(self._z_arr.size) * 8)[:, None] + np.array([4, 5, 6, 7])] = (
            self._z_arr[:, None]
        )
        self._z += z_start
        self._w = np.repeat(
            self._w_arr,
            repeats=8,
        )

        i = (
            np.tile([7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2], (len(self._x_arr), 1))
            + np.arange(len(self._x_arr))[:, np.newaxis] * 8
        ).flatten()
        j = (
            np.tile([3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3], (len(self._x_arr), 1))
            + np.arange(len(self._x_arr))[:, np.newaxis] * 8
        ).flatten()
        k = (
            np.tile([0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6], (len(self._x_arr), 1))
            + np.arange(len(self._x_arr))[:, np.newaxis] * 8
        ).flatten()

        return super().__init__(
            x=self._x,
            y=self._y,
            z=self._z,
            intensity=self._w,
            i=i,
            j=j,
            k=k,
            showscale=showscale,
            alphahull=alphahull,
            flatshading=flatshading,
            hovertemplate="x: %{customdata[0]}<br>"
            "y: %{customdata[1]}<br>"
            "z: %{customdata[2]}<br>"
            "w: %{customdata[3]}<extra></extra>",
            customdata=np.stack(
                [
                    np.repeat(self._x_arr, repeats=8),
                    np.repeat(self._y_arr, repeats=8),
                    np.repeat(self._z[8 - 1 :: 8], repeats=8),
                    self._w,
                ],
                axis=1,
            ),
            meta="bar3d",
            *args,
            **kwargs,
        )

    @classmethod
    def from_dataframe(
        cls,
        df: DataFrame,
        value_weights: bool = False,
        x_mapping: Optional[ArrayLike] = None,
        y_mapping: Optional[ArrayLike] = None,
        **kwargs,
    ) -> Self:
        if not df.columns.is_unique:
            raise ValueError("Dataframe columns are not unique")
        elif not df.index.is_unique:
            raise ValueError("Dataframe index is not unique")

        x, y, z = melt_dataframe(
            df.loc[  # type: ignore
                x_mapping if x_mapping is not None else slice(None),
                y_mapping if y_mapping is not None else slice(None),
            ]
        )

        return cls(
            x=x,
            y=y,
            z=z,
            w=z if value_weights else kwargs.pop("w", None),
            **kwargs,
        )


def merge_cuboids(
    *cuboids: Cuboid,
) -> go.Mesh3d:
    x = np.zeros(len(cuboids) * 8)
    y = np.zeros(len(cuboids) * 8)
    z = np.zeros(len(cuboids) * 8)
    intensity = np.zeros(len(cuboids) * 8)
    i = (
        np.tile([7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2], (len(cuboids), 1))
        + np.arange(len(cuboids))[:, np.newaxis] * 8
    ).flatten()
    j = (
        np.tile([3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3], (len(cuboids), 1))
        + np.arange(len(cuboids))[:, np.newaxis] * 8
    ).flatten()
    k = (
        np.tile([0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6], (len(cuboids), 1))
        + np.arange(len(cuboids))[:, np.newaxis] * 8
    ).flatten()

    for idx, cuboid in enumerate(cuboids):
        x[idx * 8 : (idx + 1) * 8] = cuboid.x  # type: ignore
        y[idx * 8 : (idx + 1) * 8] = cuboid.y  # type: ignore
        z[idx * 8 : (idx + 1) * 8] = cuboid.z  # type: ignore
        intensity[idx * 8 : (idx + 1) * 8] = cuboid.intensity  # type: ignore

    return go.Mesh3d(
        x=x,
        y=y,
        z=z,
        i=i,
        j=j,
        k=k,
        intensity=intensity,
        flatshading=True,
        showscale=False,
        cmin=0,
        cmax=1,
    )


def is_trace_3d(
    trace: Trace,
) -> bool:
    return (
        trace.type.endswith("3d")  # type: ignore
        or trace.type  # type: ignore
        in ["surface", "mesh3d", "cone", "streamtube", "volume"]
    )
