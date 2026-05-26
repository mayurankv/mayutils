"""Line trace with optional text labels and confidence bands."""

import itertools
import re
from collections.abc import Sequence
from typing import Any, ClassVar, Self

from mayutils.core.extras import may_require_extras
from mayutils.objects.colours import Colour
from mayutils.visualisation.graphs.plotly.traces.types import TraceType

with may_require_extras():
    import numpy as np
    import plotly.graph_objects as go
    from numpy.typing import ArrayLike
    from pandas import DataFrame, Series

_bounds_counter = itertools.count(1)


class Line(go.Scatter):
    """
    Line trace with optional end-of-line text labels.

    Thin wrapper around :class:`plotly.graph_objects.Scatter` that defaults
    to ``mode="lines"`` and can optionally append a text label at the last
    data point.  Reserves the ``meta`` field for internal trace-type
    identification.

    Parameters
    ----------
    label_name : bool | str
        When a string, the value is rendered as a text label at the last
        point.  When ``True``, the trace ``name`` is used instead.
        ``False`` (default) disables the label.
    **kwargs : Any
        Forwarded to :class:`plotly.graph_objects.Scatter`.

    Raises
    ------
    ValueError
        If ``meta`` is passed, since it is reserved for internal use.

    See Also
    --------
    mayutils.visualisation.graphs.plotly.traces.scatter.Scatter :
        Marker-mode scatter trace.
    mayutils.visualisation.graphs.plotly.traces.ecdf.Ecdf :
        ECDF trace built on top of Line.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.traces.line import Line
    >>> Line(x=[1, 2, 3], y=[4, 5, 6])  # doctest: +SKIP
    """

    trace_type: ClassVar[TraceType] = TraceType.LINE

    def __init__(
        self,
        *,
        label_name: bool | str = False,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """
        Initialise a Line trace.

        Sets ``mode="lines"`` by default, appending ``"+text"`` when a
        label is requested.  Reserves ``meta`` for internal trace-type
        identification.

        Parameters
        ----------
        label_name : bool | str
            Text label rendered at the last data point.  A string value
            is used directly; ``True`` copies the trace ``name``;
            ``False`` (default) disables labelling.
        **kwargs : Any
            Forwarded to :class:`plotly.graph_objects.Scatter`.

        Raises
        ------
        ValueError
            If ``meta`` is passed, since it is reserved for internal use.

        See Also
        --------
        Line.from_series : Build a Line from a pandas Series.

        Examples
        --------
        >>> Line(x=[0, 1], y=[2, 3], label_name="trend")  # doctest: +SKIP
        """
        if "meta" in kwargs:
            msg = "The 'meta' argument is reserved for internal use of `mayutils` and cannot be set by the user."
            raise ValueError(msg)

        mode: str = kwargs.pop("mode", "lines")
        if ("text" in kwargs or label_name is not False) and not bool(re.search(pattern=r"text\+|\+text$|\+text\+", string=mode)):
            mode += "+text"
        kwargs["mode"] = mode

        if ("textposition" not in kwargs or kwargs["textposition"] is None) and label_name is not False:
            kwargs["textposition"] = "middle right"

        label_name = kwargs.get("name", False) if label_name is True else label_name
        if label_name is not False and "text" not in kwargs:
            kwargs["text"] = [""] * (len(kwargs.get("x", [])) - 1) + [label_name]

        super().__init__(
            meta=self.trace_type,
            **kwargs,
        )

    @classmethod
    def from_series(
        cls,
        series: Series,
        /,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        """
        Build a Line trace from a pandas Series.

        Uses the Series index as x-values and its values as y-values.

        Parameters
        ----------
        series
            Source data whose index maps to x and values to y.
        **kwargs
            Forwarded to the :class:`Line` constructor.

        Returns
        -------
        Self
            A new ``Line`` trace.

        See Also
        --------
        Line.__init__ : Direct constructor.

        Examples
        --------
        >>> import pandas as pd
        >>> Line.from_series(pd.Series([1, 2, 3]))  # doctest: +SKIP
        """
        return cls(
            x=series.index,
            y=series.values,
            **kwargs,
        )

    @classmethod
    def with_bounds(
        cls,
        *,
        x: ArrayLike,
        y: ArrayLike,
        y_upper: Sequence[ArrayLike],
        y_lower: Sequence[ArrayLike],
        max_opacity: float = 0.4,
        **kwargs: Any,  # noqa: ANN401
    ) -> tuple[Self, ...]:
        """
        Create a line trace with symmetric confidence bands.

        Returns the central line together with filled band traces whose
        opacity is spread evenly up to *max_opacity*.  Upper and lower
        bound arrays must be provided in matched pairs and must widen
        monotonically from the centre.

        Parameters
        ----------
        x
            Shared x-values for the line and all bands.
        y
            Central y-values.
        y_upper
            Sequence of upper-bound arrays, one per band level.
        y_lower
            Sequence of lower-bound arrays, one per band level.
        max_opacity
            Maximum cumulative fill opacity across all bands.
        **kwargs
            Forwarded to the :class:`Line` constructor for every trace.

        Returns
        -------
        tuple[Self, ...]
            Band traces followed by the central line as the last element.

        Raises
        ------
        ValueError
            If *y_upper* and *y_lower* have different lengths, if any
            bound array length differs from *y*, or if bounds are not
            monotonically widening.

        See Also
        --------
        Line.from_bounds_dataframe : Build bands from a DataFrame.

        Examples
        --------
        >>> Line.with_bounds(
        ...     x=[1, 2, 3],
        ...     y=[4, 5, 6],
        ...     y_upper=[[5, 6, 7]],
        ...     y_lower=[[3, 4, 5]],
        ... )  # doctest: +SKIP
        """
        if len(y_lower) != len(y_upper):
            msg = "Asymmetric bounds provided"
            raise ValueError(msg)

        x_arr = np.asarray(x)
        y_arr = np.asarray(y)
        n = len(y_arr)
        last_lower = y_arr
        last_upper = y_arr

        for lower_raw, upper_raw in zip(y_lower, y_upper, strict=True):
            lower = np.asarray(lower_raw)
            upper = np.asarray(upper_raw)
            if len(lower) != n or len(upper) != n:
                msg = "Y Values of different length provided"
                raise ValueError(msg)
            if np.any(lower > last_lower) or np.any(upper < last_upper):
                msg = "Monotonic bounds not passed"
                raise ValueError(msg)

            last_lower = lower
            last_upper = upper

        line_kwargs: dict[str, str | int | float] = kwargs.pop("line", {})
        color_str = str(line_kwargs.get("color", kwargs.get("line_color", "black")))

        base_trace = cls(
            x=x_arr,
            y=y_arr,
            line=line_kwargs,
            **kwargs,
        )
        legendgroup = kwargs.pop("legendgroup", f"_bounds_{next(_bounds_counter)}")
        base_trace.legendgroup = legendgroup

        color = Colour.parse(color_str)
        x_reversed = x_arr[::-1]
        band_opacity = max_opacity / (1 + len(y_upper))
        band_kwargs = {key: value for key, value in kwargs.items() if key != "line_color"}

        bands = tuple(
            cls(
                x=np.concatenate([x_arr, x_reversed]),
                y=np.concatenate([np.asarray(upper), np.asarray(lower)[::-1]]),
                fill="toself",
                showlegend=False,
                fillcolor=color.to_str(opacity=band_opacity),
                line={"color": color.to_str(opacity=0)},
                legendgroup=legendgroup,
                hoverinfo="skip",
                **band_kwargs,
            )
            for lower, upper in zip(y_lower, y_upper, strict=True)
        )

        return (*bands, base_trace)

    @classmethod
    def from_bounds_dataframe(
        cls,
        df: DataFrame,
        /,
        *,
        max_opacity: float = 0.4,
        y_index: int | str = 0,
        y_upper_indices: Sequence[int] | Sequence[str] | None = None,
        y_lower_indices: Sequence[int] | Sequence[str] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> tuple[Self, ...]:
        """
        Build a line with confidence bands from a DataFrame.

        Extracts the central line and paired upper/lower bound columns
        from *df* and delegates to :meth:`with_bounds`.  When index
        arguments are omitted the columns are split by alternating
        position (odd columns upper, even columns lower).

        Parameters
        ----------
        df
            DataFrame whose index maps to x.  One column supplies the
            central y-values; remaining columns supply the bounds.
        max_opacity
            Maximum cumulative fill opacity across all bands.
        y_index
            Column position or label for the central y-values.
        y_upper_indices
            Column positions or labels for upper-bound series.
        y_lower_indices
            Column positions or labels for lower-bound series.
        **kwargs
            Forwarded to :meth:`with_bounds`.

        Returns
        -------
        tuple[Self, ...]
            Band traces followed by the central line as the last element.

        Raises
        ------
        ValueError
            If only one of *y_upper_indices* / *y_lower_indices* is
            provided, or if bounds are asymmetric.

        See Also
        --------
        Line.with_bounds : Array-based constructor for bands.

        Examples
        --------
        >>> import pandas as pd
        >>> df = pd.DataFrame({"y": [1, 2], "hi": [2, 3], "lo": [0, 1]})
        >>> Line.from_bounds_dataframe(
        ...     df,
        ...     y_index="y",
        ...     y_upper_indices=["hi"],
        ...     y_lower_indices=["lo"],
        ... )  # doctest: +SKIP
        """
        x = df.index
        y = df.iloc[:, y_index] if isinstance(y_index, int) else df[y_index]

        if y_upper_indices is None and y_lower_indices is None:
            y_upper_indices = list(range(1, len(df.columns), 2))
            y_lower_indices = list(range(2, len(df.columns), 2))
        elif y_upper_indices is None or y_lower_indices is None:
            msg = "Both y_upper_indices and y_lower_indices must be provided together"
            raise ValueError(msg)

        y_upper = [df.iloc[:, i] if isinstance(i, int) else df[i] for i in y_upper_indices]
        y_lower = [df.iloc[:, i] if isinstance(i, int) else df[i] for i in y_lower_indices]

        return cls.with_bounds(
            x=x,
            y=y,
            y_upper=y_upper,
            y_lower=y_lower,
            max_opacity=max_opacity,
            **kwargs,
        )
