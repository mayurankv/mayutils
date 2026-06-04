"""3-D mesh traces for cuboids and bar charts."""

from typing import Any, ClassVar, Self

from mayutils.core.extras import may_require_extras
from mayutils.visualisation.graphs.plotly.traces.types import TraceType
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
    """
    Single axis-aligned cuboid rendered as a :class:`go.Mesh3d`.

    Constructs the eight vertices and twelve triangular faces of a
    rectangular box from axis-aligned min/max pairs.

    Parameters
    ----------
    x
        ``(min, max)`` bounds along the x-axis.
    y
        ``(min, max)`` bounds along the y-axis.
    z
        ``(min, max)`` bounds along the z-axis.
    weight
        Uniform intensity value applied to every vertex.
    flatshading
        Enable flat shading on the mesh faces.
    showscale
        Show the colour-bar scale.
    alphahull
        Alpha-hull parameter forwarded to :class:`go.Mesh3d`.
    cmin
        Lower bound of the colour scale.
    cmax
        Upper bound of the colour scale.
    **kwargs
        Forwarded to :class:`go.Mesh3d`.

    See Also
    --------
    merge_cuboids : Combine several cuboids into one mesh.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.traces.mesh3d import Cuboid
    >>> trace = Cuboid(x=(0, 1), y=(0, 1), z=(0, 1))
    """

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
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """
        Build the cuboid vertices and faces.

        Expands the three ``(min, max)`` pairs into eight vertices and
        delegates to :class:`go.Mesh3d`.

        Parameters
        ----------
        x
            ``(min, max)`` bounds along the x-axis.
        y
            ``(min, max)`` bounds along the y-axis.
        z
            ``(min, max)`` bounds along the z-axis.
        weight
            Uniform intensity value applied to every vertex.
        flatshading
            Enable flat shading on the mesh faces.
        showscale
            Show the colour-bar scale.
        alphahull
            Alpha-hull parameter forwarded to :class:`go.Mesh3d`.
        cmin
            Lower bound of the colour scale.
        cmax
            Upper bound of the colour scale.
        **kwargs
            Forwarded to :class:`go.Mesh3d`.

        See Also
        --------
        merge_cuboids : Combine several cuboids into one mesh.

        Examples
        --------
        >>> trace = Cuboid(x=(0, 2), y=(0, 3), z=(0, 1))
        """
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
    """
    3-D bar chart rendered as a :class:`go.Mesh3d`.

    Constructs a grid of cuboid bars from parallel x/y/z arrays,
    optionally coloured by a separate weight array *w*.

    Parameters
    ----------
    x
        Bar x-positions (may be categorical).
    y
        Bar y-positions (may be categorical).
    z
        Bar heights.
    w
        Optional per-bar colour weights; defaults to uniform.
    showscale
        Show the colour-bar scale.
    alphahull
        Alpha-hull parameter forwarded to :class:`go.Mesh3d`.
    flatshading
        Enable flat shading on the mesh faces.
    dx
        Bar width along the x-axis.
    dy
        Bar width along the y-axis.
    z0
        Baseline z-value for all bars.
    x_start
        Global x-offset applied to all bars.
    y_start
        Global y-offset applied to all bars.
    z_start
        Global z-offset applied to all bars.
    x_mapping
        Optional categorical-to-numeric mapping for x values.
    y_mapping
        Optional categorical-to-numeric mapping for y values.
    **kwargs
        Forwarded to :class:`go.Mesh3d`.

    Raises
    ------
    ValueError
        If input arrays have mismatched lengths.

    See Also
    --------
    Cuboid : Single-box primitive used internally.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.traces.mesh3d import Bar3d
    >>> trace = Bar3d(x=[0, 1], y=[0, 1], z=[5, 10])
    """

    trace_type: ClassVar[TraceType] = TraceType.BAR3D

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
        """
        Construct the 3-D bar mesh from parallel arrays.

        Converts x/y positions to a grid of cuboid vertices and
        delegates to :class:`go.Mesh3d`.

        Parameters
        ----------
        x
            Bar x-positions.
        y
            Bar y-positions.
        z
            Bar heights.
        w
            Optional colour weights; defaults to uniform.
        showscale
            Show the colour-bar scale.
        alphahull
            Alpha-hull parameter forwarded to :class:`go.Mesh3d`.
        flatshading
            Enable flat shading.
        dx
            Bar width along x.
        dy
            Bar width along y.
        z0
            Baseline z-value.
        x_start
            Global x-offset.
        y_start
            Global y-offset.
        z_start
            Global z-offset.
        x_mapping
            Categorical-to-numeric mapping for x.
        y_mapping
            Categorical-to-numeric mapping for y.
        **kwargs
            Forwarded to :class:`go.Mesh3d`.

        Raises
        ------
        ValueError
            If input arrays have mismatched lengths.

        See Also
        --------
        Bar3d.from_dataframe : Build from a pandas DataFrame.

        Examples
        --------
        >>> trace = Bar3d(x=[0], y=[0], z=[5])
        """
        if "meta" in kwargs:
            msg = "The 'meta' argument is reserved for internal use and cannot be set by the user."
            raise ValueError(msg)

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
            meta=self.trace_type,
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
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        """
        Build a 3-D bar chart from a pandas DataFrame.

        Melts *df* into x/y/z arrays using its index and columns, then
        delegates to the standard constructor.

        Parameters
        ----------
        df
            DataFrame whose index maps to x, columns to y, and values
            to z (bar heights).
        value_weights
            When ``True``, use the z-values as colour weights.
        x_mapping
            Optional categorical-to-numeric mapping for x.
        y_mapping
            Optional categorical-to-numeric mapping for y.
        **kwargs
            Forwarded to the constructor.

        Returns
        -------
        Self
            A new ``Bar3d`` trace.

        Raises
        ------
        ValueError
            If the DataFrame has non-unique columns or index.

        See Also
        --------
        Bar3d.__init__ : Array-based constructor.

        Examples
        --------
        >>> import pandas as pd
        >>> trace = Bar3d.from_dataframe(pd.DataFrame({"a": [1, 2]}))
        """
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
    """
    Merge multiple cuboids into a single :class:`go.Mesh3d`.

    Concatenates vertex and face-index arrays from each cuboid so they
    render as one combined mesh trace.

    Parameters
    ----------
    *cuboids
        Cuboid instances to merge.

    Returns
    -------
        A single ``go.Mesh3d`` containing all cuboids.

    See Also
    --------
    Cuboid : Single-box primitive.

    Examples
    --------
    >>> c1 = Cuboid(x=(0, 1), y=(0, 1), z=(0, 1))
    >>> c2 = Cuboid(x=(1, 2), y=(0, 1), z=(0, 1))
    >>> c3 = Cuboid(x=(0, 1), y=(1, 2), z=(0, 1))
    >>> merged = merge_cuboids(c1, c2, c3)
    """
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
