from typing import Any

from mayutils.core.extras import may_require_extras

with may_require_extras():
    import plotly.graph_objects as go


class Scatter(go.Scatter):
    def __init__(
        self,
        mode: str | None = "markers",
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        if "meta" in kwargs:
            msg = "The 'meta' argument is reserved for internal use and cannot be set by the user."
            raise ValueError(msg)

        super().__init__(
            mode=mode,
            meta="scatter",
            **kwargs,
        )
