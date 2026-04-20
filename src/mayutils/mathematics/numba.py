"""Numba JIT-accelerated NumPy helpers for sampling and reductions.

This module provides a small collection of ``@njit`` compiled routines
that fill gaps in the NumPy surface exposed to Numba's nopython mode.
It supplies a weighted sampling primitive (:func:`choice_replacement`)
and a 2-D variant of :func:`numpy.apply_along_axis` together with
convenience wrappers (:func:`mean2d`, :func:`std2d`) for the most
common column/row reductions. These helpers allow performance-critical
numerical code to remain inside Numba-compiled call stacks while
retaining familiar NumPy semantics.
"""

from collections.abc import Callable

from mayutils.core.extras import may_require_extras

with may_require_extras():
    import numpy as np
    from numba import njit  # pyright: ignore[reportUnknownVariableType, reportAttributeAccessIssue]
    from numpy.typing import NDArray


@njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def choice_replacement(
    arr: NDArray[np.float64],
    /,
    *,
    p: NDArray[np.float64] | None = None,
    size: tuple[int, ...] | None = None,
    seed: int | None = None,
) -> NDArray[np.float64]:
    """Draw samples with replacement from an array under optional weights.

    Provides a Numba-compatible substitute for :func:`numpy.random.choice`
    with a probability vector, which is not supported inside ``@njit``
    code. When weights are supplied the implementation builds the
    cumulative distribution of ``p`` and uses inverse-transform
    sampling via :func:`numpy.searchsorted` on uniform draws, so the
    statistical behaviour matches NumPy's weighted sampling.

    Parameters
    ----------
    arr : NDArray
        Population of values to sample from. The flat sequence of
        elements defines the support of the distribution; each
        position is matched index-wise with the corresponding weight
        in ``p`` when weights are provided.
    p : NDArray or None, optional
        Sampling probabilities aligned with ``arr``. Values must be
        non-negative and sum to ``1``; they determine the likelihood
        of selecting each element. When ``None``, elements of ``arr``
        are drawn with equal probability.
    size : tuple of int or None, optional
        Shape of the returned sample. When ``None``, a single scalar
        draw is produced; otherwise the output has exactly the given
        shape, populated with independent draws.
    seed : int or None, optional
        Seed applied to the global NumPy RNG before sampling to make
        the output deterministic. When ``None``, the current global
        RNG state is used and successive calls produce independent
        draws.

    Returns
    -------
    NDArray
        Array of values sampled with replacement from ``arr``. The
        shape matches ``size`` (scalar when ``size`` is ``None``) and
        the dtype is inherited from ``arr``.

    Notes
    -----
    Setting ``seed`` reseeds the *global* NumPy RNG, which affects any
    subsequent uses of :mod:`numpy.random` in the same process. Pass
    ``seed=None`` when interleaving this function with other stochastic
    code that manages its own state.
    """
    rng = np.random.default_rng(seed=seed)

    if p is None:
        return rng.choice(a=arr, size=size)

    indices = np.searchsorted(
        a=np.cumsum(a=p),
        v=rng.random(size=size),
        side="right",
    )

    return arr[indices.ravel()].reshape(indices.shape)


@njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def np_apply_along_axis_2d(
    func1d: Callable[[NDArray[np.float64]], float],
    /,
    *,
    arr: NDArray[np.float64],
    axis: int,
) -> NDArray[np.float64]:
    """Apply a scalar-valued 1-D function along an axis of a 2-D array.

    Serves as a Numba-friendly stand-in for
    :func:`numpy.apply_along_axis`, which is not available inside
    ``@njit`` functions. The reducer is invoked once per slice along
    the requested axis and the returned scalars are packed into a
    contiguous 1-D output.

    Parameters
    ----------
    func1d : Callable[[NDArray], float]
        Reduction applied to each 1-D slice of ``arr``. Must accept a
        1-D NumPy array and return a single floating-point value;
        typical choices are :func:`numpy.mean`, :func:`numpy.std`, or
        any Numba-compilable scalar reducer.
    arr : NDArray
        Two-dimensional input whose slices are fed to ``func1d``. The
        array must be exactly 2-D; higher-rank inputs are rejected by
        the internal assertion.
    axis : int
        Axis over which to reduce. ``0`` iterates over columns and
        passes each column to ``func1d``, producing one output per
        column; ``1`` iterates over rows, producing one output per
        row. Values other than ``0`` or ``1`` are rejected.

    Returns
    -------
    NDArray
        One-dimensional array holding the reduction of each slice.
        Its length is ``arr.shape[1]`` when ``axis == 0`` and
        ``arr.shape[0]`` when ``axis == 1``.

    Raises
    ------
    AssertionError
        Raised when ``arr`` is not 2-D or when ``axis`` is neither
        ``0`` nor ``1``.
    """
    if arr.ndim != 2:  # noqa: PLR2004
        msg = f"Input array must be 2-D; got shape {arr.shape}"
        raise AssertionError(msg)
    if axis not in (0, 1):
        msg = f"Axis must be 0 or 1; got {axis}"
        raise AssertionError(msg)

    if axis == 0:
        result = np.empty(arr.shape[1])
        for i in range(len(result)):
            result[i] = func1d(arr[:, i])
    else:
        result = np.empty(arr.shape[0])
        for i in range(len(result)):
            result[i] = func1d(arr[i, :])

    return result


@njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def mean2d(
    arr: NDArray[np.float64],
    /,
    *,
    axis: int,
) -> NDArray[np.float64]:
    """Compute per-column or per-row arithmetic means of a 2-D array.

    Thin wrapper around :func:`np_apply_along_axis_2d` that dispatches
    :func:`numpy.mean` as the reducer, exposed as a standalone helper
    so that Numba can inline and cache the compiled result at each
    call site.

    Parameters
    ----------
    arr : NDArray
        Two-dimensional input whose entries are averaged. Must be
        exactly 2-D.
    axis : int
        Axis along which to compute the mean. ``0`` averages within
        each column and yields one value per column; ``1`` averages
        within each row and yields one value per row.

    Returns
    -------
    NDArray
        One-dimensional array of arithmetic means. Its length equals
        ``arr.shape[1]`` when ``axis == 0`` and ``arr.shape[0]`` when
        ``axis == 1``.

    Raises
    ------
    AssertionError
        Raised when ``arr`` is not 2-D or when ``axis`` is neither
        ``0`` nor ``1``.
    """
    return np_apply_along_axis_2d(
        np.mean,
        arr=arr,
        axis=axis,
    )


@njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def std2d(
    arr: NDArray[np.float64],
    /,
    *,
    axis: int,
) -> NDArray[np.float64]:
    """Compute per-column or per-row standard deviations of a 2-D array.

    Thin wrapper around :func:`np_apply_along_axis_2d` that dispatches
    :func:`numpy.std` as the reducer. Like NumPy's default, the
    population standard deviation (``ddof=0``) is used for each
    slice.

    Parameters
    ----------
    arr : NDArray
        Two-dimensional input whose dispersion is measured. Must be
        exactly 2-D.
    axis : int
        Axis along which to compute the standard deviation. ``0``
        reduces each column to its standard deviation, yielding one
        value per column; ``1`` reduces each row, yielding one value
        per row.

    Returns
    -------
    NDArray
        One-dimensional array of standard deviations. Its length
        equals ``arr.shape[1]`` when ``axis == 0`` and
        ``arr.shape[0]`` when ``axis == 1``.

    Raises
    ------
    AssertionError
        Raised when ``arr`` is not 2-D or when ``axis`` is neither
        ``0`` nor ``1``.
    """
    return np_apply_along_axis_2d(
        np.std,
        arr=arr,
        axis=axis,
    )
