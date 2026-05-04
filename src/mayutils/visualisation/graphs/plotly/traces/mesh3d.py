from typing import Any, Self

from mayutils.core.extras import may_require_extras
from mayutils.visualisation.graphs.plotly.utilities import (
    map_categorical_array,
    melt_dataframe,
)

with may_require_extras():
    import numpy as np
    import plotly.graph_objects as go
    from numpy.typing import ArrayLike
    from pandas import DataFrame


class Cuboid(go.Mesh3d):
    def __init__(
        self,
        *,
        x: tuple[float, float],
        y: tuple[float, float],
        z: tuple[float, float],
        weight: float = 1,
        flatshading: bool = True,
        showscale: bool = False,
        alphahull: float = 1,
        cmin: float = 0,
        cmax: float = 1,
        **kwargs: Any,
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
            **kwargs,
        )


class Bar3d(go.Mesh3d):
    def __init__(
        self,
        *,
        x: ArrayLike,
        y: ArrayLike,
        z: ArrayLike,
        w: ArrayLike | None = None,
        showscale: bool = True,
        alphahull: float = 1,
        flatshading: bool = True,
        dx: float = 1,
        dy: float = 1,
        z0: float = 0,
        x_start: float = 0,
        y_start: float = 0,
        z_start: float = 0,
        x_mapping: ArrayLike | None = None,
        y_mapping: ArrayLike | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        x_arr = np.asarray(x)
        y_arr = np.asarray(y)
        z_arr = np.asarray(z, dtype=np.float64)
        w_arr = np.asarray(w, dtype=np.float64) if w is not None else np.ones(z_arr.shape, dtype=np.float64)

        if any(len(arr) != len(w_arr) for arr in [x_arr, y_arr, z_arr]):
            msg = "Input arrays are not same length"
            raise ValueError(msg)

        nan_idxs = np.isnan(z_arr)
        self._x_arr = x_arr[~nan_idxs]
        self._y_arr = y_arr[~nan_idxs]
        self._z_arr = z_arr[~nan_idxs]
        self._w_arr = w_arr[~nan_idxs]

        x_arr_numerical = (
            map_categorical_array(
                self._x_arr,
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
                self._y_arr,
                mapping=y_mapping,
            )
            * dy
        )
        self._y = (
            np.stack(arrays=[y_arr_numerical - dy / 2, y_arr_numerical + dy / 2], axis=1)[
                np.arange(y_arr_numerical.size)[:, None], [0, 1, 1, 0, 0, 1, 1, 0]
            ].reshape(-1)
            + y_start
        )
        self._z = np.ones(shape=self._z_arr.size * 8, dtype=self._z_arr.dtype) * z0
        self._z[(np.arange(self._z_arr.size) * 8)[:, None] + np.array([4, 5, 6, 7])] = self._z_arr[:, None]
        self._z += z_start
        self._w = np.repeat(
            a=self._w_arr,
            repeats=8,
        )

        i = (
            np.tile([7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2], reps=(len(self._x_arr), 1)) + np.arange(len(self._x_arr))[:, np.newaxis] * 8
        ).flatten()
        j = (
            np.tile([3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3], reps=(len(self._x_arr), 1)) + np.arange(len(self._x_arr))[:, np.newaxis] * 8
        ).flatten()
        k = (
            np.tile([0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6], reps=(len(self._x_arr), 1)) + np.arange(len(self._x_arr))[:, np.newaxis] * 8
        ).flatten()

        super().__init__(
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
            hovertemplate="x: %{customdata[0]}<br>y: %{customdata[1]}<br>z: %{customdata[2]}<br>w: %{customdata[3]}<extra></extra>",
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
            **kwargs,
        )

    @classmethod
    def from_dataframe(
        cls,
        df: DataFrame,
        /,
        *,
        value_weights: bool = False,
        x_mapping: ArrayLike | None = None,
        y_mapping: ArrayLike | None = None,
        **kwargs: Any,
    ) -> Self:
        if not df.columns.is_unique:
            msg = "Dataframe columns are not unique"
            raise ValueError(msg)
        if not df.index.is_unique:
            msg = "Dataframe index is not unique"
            raise ValueError(msg)

        x_mapping_arr = np.asarray(x_mapping) if x_mapping is not None else None
        y_mapping_arr = np.asarray(y_mapping) if y_mapping is not None else None

        x, y, z = melt_dataframe(
            df.loc[
                x_mapping_arr if x_mapping_arr is not None else slice(None),
                y_mapping_arr if y_mapping_arr is not None else slice(None),
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
    i = (np.tile([7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2], (len(cuboids), 1)) + np.arange(len(cuboids))[:, np.newaxis] * 8).flatten()
    j = (np.tile([3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3], (len(cuboids), 1)) + np.arange(len(cuboids))[:, np.newaxis] * 8).flatten()
    k = (np.tile([0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6], (len(cuboids), 1)) + np.arange(len(cuboids))[:, np.newaxis] * 8).flatten()

    for idx, cuboid in enumerate(cuboids):
        x[idx * 8 : (idx + 1) * 8] = cuboid["x"]
        y[idx * 8 : (idx + 1) * 8] = cuboid["y"]
        z[idx * 8 : (idx + 1) * 8] = cuboid["z"]
        intensity[idx * 8 : (idx + 1) * 8] = cuboid["intensity"]

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
