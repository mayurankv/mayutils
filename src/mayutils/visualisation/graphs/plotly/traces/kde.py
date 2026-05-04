from typing import Any, cast

from mayutils.core.extras import may_require_extras
from mayutils.visualisation.graphs.plotly.traces.line import Line

with may_require_extras():
    import numpy as np
    from numpy.typing import ArrayLike, NDArray
    from scipy.stats import gaussian_kde


class Kde(Line):
    def __init__(
        self,
        *,
        x: ArrayLike,
        bandwidth: float | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        x_arr = np.asarray(x)
        kde = gaussian_kde(dataset=x_arr, bw_method=bandwidth)

        x_grid = cast("NDArray[np.float64]", np.linspace(start=np.min(a=x_arr), stop=np.max(a=x_arr), num=1000))
        y_arr = kde(points=x_grid)

        kwargs["meta"] = kwargs.pop("meta", "kde")

        super().__init__(
            x=x_grid,
            y=y_arr,
            customdata=x_arr,
            fill=kwargs.pop("fill", "tozeroy"),
            **kwargs,
        )
