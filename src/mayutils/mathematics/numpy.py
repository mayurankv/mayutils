"""
Provide NumPy-backed numerical helpers for the mathematics namespace.

Centralise thin wrappers and convenience functions built on top of
:mod:`numpy` so that higher-level statistical and modelling code across
:mod:`mayutils.mathematics` can rely on a consistent, typed interface.
Utilities here are array-oriented, operate on :class:`numpy.ndarray`
inputs, and preserve broadcasting semantics and dtype handling inherited
from NumPy. Keeping them in one module avoids scattering low-level
vectorised primitives across the wider :mod:`mayutils` library.

See Also
--------
numpy.ndarray : Core N-dimensional array container used by the helpers.
numpy.linalg : Linear algebra routines that sibling modules build upon.
numpy.typing.ArrayLike : Accepted input protocol for array-coercible values.
mayutils.mathematics : Parent package hosting related numerical utilities.

Examples
--------
>>> from mayutils.mathematics import numpy as mnp
>>> import numpy as np
>>> arr = np.arange(6, dtype=np.float64).reshape(2, 3)
>>> arr.shape
(2, 3)
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from mayutils.core.extras import may_require_extras

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import ArrayLike, NDArray


def broadcast_to_array(
    *,
    value: ArrayLike | NDArray[Any] | None,
    n: int,
) -> NDArray[Any]:
    """
    Broadcast a scalar or sequence to an array of length *n*.

    Uses ``object`` dtype only when the value is ``None``; otherwise
    lets NumPy infer the appropriate dtype from the value.

    Parameters
    ----------
    value : ArrayLike | NDArray[Any] | None
        Scalar, sequence, or ndarray. ``None`` fills the output with
        ``None`` (object dtype). A sequence of length *n* is converted
        directly; any other value is broadcast to every element.
    n : int
        Desired length of the output array.

    Returns
    -------
    NDArray[Any]
        Array of length *n*.
    """
    with may_require_extras():
        import numpy as np

    if value is None:
        return np.full(n, None, dtype=object)

    if isinstance(value, np.ndarray):
        return cast("NDArray[Any]", value)

    if isinstance(value, Sequence) and not isinstance(value, str) and len(value) == n:
        return np.asarray(value)

    return np.full(
        shape=n,
        fill_value=value,
    )


def merge_detail(
    *,
    detail: dict[str, NDArray[Any]],
    detail_out: dict[str, NDArray[Any]],
    mask: NDArray[np.bool_],
    template: NDArray[Any],
) -> dict[str, NDArray[Any]]:
    """
    Merge a per-group detail dict into the full-batch detail dict.

    For each key in *detail_out*, allocates an uninitialised array (via
    ``np.empty``) shaped like *template* on first encounter, then fills
    the *mask* positions.

    Parameters
    ----------
    detail : dict[str, NDArray[Any]]
        Accumulator dict (modified in place).
    detail_out : dict[str, NDArray[Any]]
        Detail values for the current group.
    mask : NDArray[np.bool_]
        Boolean mask identifying which rows belong to this group.
    template : NDArray[Any]
        Array whose shape and size are used to initialise new keys.

    Returns
    -------
    dict[str, NDArray[Any]]
        The accumulator dict, for chaining.

    Notes
    -----
    Across accumulated calls, the masks must jointly cover every
    position: uncovered positions remain uninitialised memory, not
    zeros. When *values* has the same number of dimensions as
    *template* the full template shape is trusted, so trailing
    dimensions must match; otherwise assignment raises a raw NumPy
    broadcast ``ValueError``.
    """
    with may_require_extras():
        import numpy as np

    for key, values in detail_out.items():
        if key not in detail:
            shape = template.shape if values.ndim == template.ndim else template.shape[:1]
            detail[key] = np.empty(shape, dtype=values.dtype)
        detail[key][mask] = values

    return detail


def dictionary_lookup(
    *,
    lookup: ArrayLike | NDArray[Any],
    dictionary: dict[Any, Any],
    default_value: Any,  # noqa: ANN401
) -> NDArray[Any]:
    """
    Map each element of *lookup* through *dictionary* with a default.

    Parameters
    ----------
    lookup : ArrayLike | NDArray[Any]
        Keys to look up.
    dictionary : dict[Any, Any]
        Mapping from key to value.
    default_value : Any
        Value used when a key is not found in *dictionary*.

    Returns
    -------
    NDArray[Any]
        Array of mapped values, same length as *lookup*.
    """
    with may_require_extras():
        import numpy as np

    lookup = np.asarray(lookup)
    return np.array(
        [
            dictionary.get(
                lookup_value,
                default_value,
            )
            for lookup_value in lookup
        ],
    )


def check_lengths(
    **arrays: NDArray[Any],
) -> None:
    """
    Verify that all arrays have the same first-dimension length.

    Parameters
    ----------
    **arrays : NDArray[Any]
        Named arrays to check. Names are used in the error message.

    Raises
    ------
    ValueError
        If any array's first dimension differs from the others.
    """
    lengths = {name: arr.shape[0] for name, arr in arrays.items()}
    unique = set(lengths.values())
    if len(unique) > 1:
        detail = ", ".join(f"{name}={n}" for name, n in lengths.items())
        msg = f"Array length mismatch: {detail}"
        raise ValueError(msg)
