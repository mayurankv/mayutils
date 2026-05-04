from typing import Any, Literal

from mayutils.core.extras import may_require_extras
from mayutils.visualisation.graphs.plotly.traces.line import Line

with may_require_extras():
    import numpy as np
    from numpy.typing import ArrayLike


class Ecdf(Line):
    def __init__(
        self,
        *,
        x: ArrayLike,
        y: ArrayLike | None = None,
        y_shift: float = 0,
        norm: Literal["probability", "percentage", "count"] = "probability",
        mode: Literal["standard", "reversed", "complementary"] = "standard",
        fill: Literal["tozeroy", "tonexty", "toself"] = "toself",
        left_inclusive: bool = False,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        x_arr = np.asarray(x)
        idx = np.argsort(x_arr)

        if mode == "reversed":
            idx = np.flip(idx)

        x_arr = x_arr[idx]

        if y is None:
            y_arr = np.ones(shape=len(x_arr))
        else:
            y_arr = np.asarray(y)
            if len(y_arr) != len(x_arr):
                msg = "x and y arrays are not the same length"
                raise ValueError(msg)

            y_arr = y_arr[idx]

        y_sum = np.sum(y_arr)
        y_arr = np.cumsum(y_arr)
        if mode == "complementary":
            y_arr = y_sum - y_arr

        if norm == "probability":
            y_arr = y_arr / y_sum
        elif norm == "percentage":
            y_arr = 100 * y_arr / y_sum

        y_arr += y_shift

        kwargs["line_shape"] = "hv" if ((mode != "reversed") ^ (not left_inclusive)) else "vh"
        kwargs["fill"] = fill
        kwargs["meta"] = kwargs.pop("meta", "ecdf")

        if fill == "toself":
            x_arr = np.insert(x_arr, 0, x_arr[-1])
            y_arr = np.insert(y_arr, 0, y_shift)

        super().__init__(
            x=x_arr,
            y=y_arr,
            customdata=y_arr - y_shift,
            hovertemplate="<b>%{fullData.name}</b><br>x: %{x}<br>y: %{customdata}<extra></extra>",
            **kwargs,
        )
