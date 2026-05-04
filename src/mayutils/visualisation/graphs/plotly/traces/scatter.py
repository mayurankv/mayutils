"""Scatter trace with sensible defaults.

Thin wrapper around :class:`plotly.graph_objects.Scatter` that defaults to
``mode="markers"`` and reserves the ``meta`` field for internal trace-type
identification.
"""

from typing import Any

from mayutils.core.extras import may_require_extras

with may_require_extras():
    import plotly.graph_objects as go


class Scatter(go.Scatter):
    """Scatter trace defaulting to marker mode.

    Parameters
    ----------
    mode : str | None, optional
        Plotly drawing mode, by default ``"markers"``.
    **kwargs : Any
        Forwarded to :class:`plotly.graph_objects.Scatter`.

    Raises
    ------
    ValueError
        If ``meta`` is passed, since it is reserved for internal use.
    """

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
