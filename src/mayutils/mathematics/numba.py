"""
Provide Numba JIT-accelerated NumPy helpers for sampling and reductions.

This module collects ``@njit`` compiled routines that fill gaps in the
NumPy surface exposed to Numba's nopython mode. It supplies a weighted
sampling primitive (:func:`choice_replacement`) and a 2-D variant of
:func:`numpy.apply_along_axis` together with convenience wrappers
(:func:`mean2d`, :func:`std2d`) for the most common column/row
reductions. These helpers allow performance-critical numerical code to
remain inside Numba-compiled call stacks while retaining familiar
NumPy semantics.

See Also
--------
numba.njit : Decorator that triggers nopython-mode compilation.
numba.typed : Typed container primitives usable inside compiled code.
numba.cuda : GPU dispatch layer for Numba kernels.
mayutils.mathematics.numpy : Pure NumPy counterparts without JIT.

Examples
--------
>>> import numpy as np
>>> from mayutils.mathematics.numba import choice_replacement
>>> rng_sample = choice_replacement(
...     np.array([0.0, 1.0, 2.0]),
...     p=np.array([0.2, 0.3, 0.5]),
...     size=(4,),
...     seed=1,
... )
>>> rng_sample.shape
(4,)
>>> bool(np.isin(rng_sample, np.array([0.0, 1.0, 2.0])).all())
True
"""

from collections.abc import Callable

from mayutils.core.extras import may_require_extras

with may_require_extras():
    import numpy as np
    from numba import njit  # pyright: ignore[reportUnknownVariableType, reportAttributeAccessIssue]
    from numpy.typing import NDArray


@njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _choice_replacement_uniform(
    arr: NDArray[np.float64],
    rng: "np.random.Generator",
    size: tuple[int, ...],
) -> NDArray[np.float64]:
    """
    Draw uniform samples with replacement from ``arr``.

    Generate random integer indices into ``arr`` via ``rng`` and gather
    the corresponding elements, reshaping the output to match ``size``.

    Parameters
    ----------
    arr
        Population array whose elements are sampled uniformly.
    rng
        NumPy random generator used to produce integer indices.
    size
        Shape of the output sample array.

    Returns
    -------
        Array of elements drawn uniformly from ``arr`` with shape
        ``size``.

    See Also
    --------
    _choice_replacement_weighted : Weighted variant using inverse-CDF
        sampling.
    choice_replacement : Public entry point that dispatches to this
        helper when no probability vector is supplied.

    Examples
    --------
    >>> import numpy as np
    >>> _choice_replacement_uniform(  # doctest: +SKIP
    ...     np.array([1.0, 2.0, 3.0]),
    ...     np.random.default_rng(42),
    ...     (4,),
    ... )
    """
    indices = rng.integers(low=0, high=arr.shape[0], size=size)
    return arr[indices.ravel()].reshape(indices.shape)


@njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _choice_replacement_weighted(
    arr: NDArray[np.float64],
    p: NDArray[np.float64],
    rng: "np.random.Generator",
    size: tuple[int, ...],
) -> NDArray[np.float64]:
    """
    Draw weighted samples with replacement from ``arr`` via inverse-CDF sampling.

    Build the cumulative distribution from ``p``, draw uniforms from
    ``rng``, and use :func:`numpy.searchsorted` to map each uniform to
    the corresponding index in ``arr``.

    Parameters
    ----------
    arr
        Population array whose elements are sampled according to ``p``.
    p
        Probability vector aligned with ``arr``; values must be
        non-negative and sum to ``1``.
    rng
        NumPy random generator used to produce uniform draws.
    size
        Shape of the output sample array.

    Returns
    -------
        Array of elements drawn from ``arr`` according to ``p`` with
        shape ``size``.

    See Also
    --------
    _choice_replacement_uniform : Uniform variant that skips the CDF
        step.
    choice_replacement : Public entry point that dispatches to this
        helper when a probability vector is supplied.

    Examples
    --------
    >>> import numpy as np
    >>> _choice_replacement_weighted(  # doctest: +SKIP
    ...     np.array([1.0, 2.0, 3.0]),
    ...     np.array([0.1, 0.2, 0.7]),
    ...     np.random.default_rng(42),
    ...     (4,),
    ... )
    """
    indices = np.searchsorted(
        a=np.cumsum(a=p),
        v=rng.random(size=size),
        side="right",
    )
    return arr[indices.ravel()].reshape(indices.shape)


def choice_replacement(
    arr: NDArray[np.float64],
    /,
    *,
    p: NDArray[np.float64] | None = None,
    size: tuple[int, ...] | None = None,
    seed: int | None = None,
) -> NDArray[np.float64]:
    """
    Draw samples with replacement from an array under optional weights.

    Serve as a Numba-compatible substitute for
    :func:`numpy.random.choice` with a probability vector, which is not
    supported inside ``@njit`` code. When weights are supplied the
    implementation builds the cumulative distribution of ``p`` and uses
    inverse-transform sampling via :func:`numpy.searchsorted` on
    uniform draws, so the statistical behaviour matches NumPy's
    weighted sampling. The routine is AOT-ready via ``cache=True`` so
    the first call triggers nopython compilation once and reuses the
    cached machine code thereafter.

    Parameters
    ----------
    arr
        Population of values to sample from. The flat sequence of
        elements defines the support of the distribution; each
        position is matched index-wise with the corresponding weight
        in ``p`` when weights are provided.
    p
        Sampling probabilities aligned with ``arr``. Values must be
        non-negative and sum to ``1``; they determine the likelihood
        of selecting each element. When ``None``, elements of ``arr``
        are drawn with equal probability.
    size
        Shape of the returned sample. When ``None``, a single scalar
        draw is produced; otherwise the output has exactly the given
        shape, populated with independent draws.
    seed
        Seed applied to the global NumPy RNG before sampling to make
        the output deterministic. When ``None``, the current global
        RNG state is used and successive calls produce independent
        draws.

    Returns
    -------
        Array of values sampled with replacement from ``arr``. The
        shape matches ``size`` (scalar when ``size`` is ``None``) and
        the dtype is inherited from ``arr``.

    See Also
    --------
    numba.njit : Decorator used to JIT-compile this helper in nopython
        mode so it can run inside other Numba kernels.
    numba.typed : Typed containers that interoperate with the sampled
        array when carried through compiled pipelines.
    numba.cuda : GPU dispatch layer for porting the weighted draw to
        device code.
    mayutils.mathematics.numpy : Pure-NumPy helpers that share the
        statistical contract but bypass JIT compilation.
    np_apply_along_axis_2d : Companion helper for reducing arrays
        produced from weighted draws inside compiled code.

    Notes
    -----
    The ``rng`` is constructed in pure Python and passed as a positional
    argument to the inner Numba kernels, the pattern recommended for
    :class:`numpy.random.Generator` interop with ``@njit`` since Numba
    cannot construct ``Generator`` objects from inside compiled code.

    Examples
    --------
    >>> import numpy as np
    >>> from mayutils.mathematics.numba import choice_replacement
    >>> arr = np.array([10.0, 20.0, 30.0])
    >>> draws = choice_replacement(
    ...     arr,
    ...     p=np.array([0.1, 0.3, 0.6]),
    ...     size=(5,),
    ...     seed=0,
    ... )
    >>> draws.shape
    (5,)
    >>> bool(np.isin(draws, arr).all())
    True
    """
    rng = np.random.default_rng(seed=seed)
    resolved_size: tuple[int, ...] = () if size is None else size

    if p is None:
        return _choice_replacement_uniform(arr, rng, resolved_size)

    return _choice_replacement_weighted(arr, p, rng, resolved_size)


@njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def np_apply_along_axis_2d(
    nb_func1d: Callable[[NDArray[np.float64]], float],
    *,
    arr: NDArray[np.float64],
    axis: int,
) -> NDArray[np.float64]:
    """
    Apply a scalar-valued 1-D function along an axis of a 2-D array.

    Serve as a Numba-friendly stand-in for
    :func:`numpy.apply_along_axis`, which is not available inside
    ``@njit`` functions. The reducer is invoked once per slice along
    the requested axis and the returned scalars are packed into a
    contiguous 1-D output. Because ``func1d`` is received as a first
    argument, Numba specialises the type signature per callable, so
    each reducer produces a separate compiled variant cached on disk.

    Parameters
    ----------
    nb_func1d
        Reduction applied to each 1-D slice of ``arr``. Must accept a
        1-D NumPy array and return a single floating-point value;
        must be a Numba-compiled scalar reducer.
    arr
        Two-dimensional input whose slices are fed to ``func1d``. The
        array must be exactly 2-D; higher-rank inputs are rejected by
        the internal assertion.
    axis
        Axis over which to reduce. ``0`` iterates over columns and
        passes each column to ``func1d``, producing one output per
        column; ``1`` iterates over rows, producing one output per
        row. Values other than ``0`` or ``1`` are rejected.

    Returns
    -------
        One-dimensional array holding the reduction of each slice.
        Its length is ``arr.shape[1]`` when ``axis == 0`` and
        ``arr.shape[0]`` when ``axis == 1``.

    Raises
    ------
    AssertionError
        Raised when ``arr`` is not 2-D or when ``axis`` is neither
        ``0`` nor ``1``.

    See Also
    --------
    numba.njit : Decorator used to compile this helper in nopython
        mode with ``cache=True`` for AOT reuse.
    numba.typed : Typed container utilities that can replace Python
        lists when ``func1d`` expects richer inputs.
    numba.cuda : GPU dispatch layer for porting slice-wise reductions
        to device memory.
    mayutils.mathematics.numpy : Plain NumPy helpers for cases that do
        not need JIT compilation.
    mean2d : Thin wrapper that binds ``func1d`` to :func:`numpy.mean`.
    std2d : Thin wrapper that binds ``func1d`` to :func:`numpy.std`.

    Examples
    --------
    The reducer must itself be Numba-compiled (a raw NumPy function such
    as ``np.sum`` cannot be typed inside ``@njit``); pass a sibling
    kernel such as :func:`mean1d`:

    >>> import numpy as np
    >>> from mayutils.mathematics.numba import np_apply_along_axis_2d, mean1d
    >>> data = np.arange(12.0).reshape(3, 4)
    >>> np_apply_along_axis_2d(mean1d, arr=data, axis=0)
    array([4., 5., 6., 7.])
    >>> np_apply_along_axis_2d(mean1d, arr=data, axis=1)
    array([1.5, 5.5, 9.5])
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
            result[i] = nb_func1d(arr[:, i])
    else:
        result = np.empty(arr.shape[0])
        for i in range(len(result)):
            result[i] = nb_func1d(arr[i, :])

    return result


@njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def mean1d(
    arr: NDArray[np.float64],
) -> float:
    """
    Compute the arithmetic mean of a 1-D array inside Numba-compiled code.

    Wrap :func:`numpy.mean` in an ``@njit`` kernel so that it can be
    passed as a callable argument to other compiled functions such as
    :func:`np_apply_along_axis_2d`. Numba requires any function passed
    at runtime to have a known compiled type; wrapping the NumPy
    dispatcher in this thin kernel satisfies that constraint without
    changing the statistical contract.

    Parameters
    ----------
    arr
        One-dimensional array whose elements are averaged. The result
        is cast to ``float`` to produce a scalar compatible with the
        output buffer of :func:`np_apply_along_axis_2d`.

    Returns
    -------
        Arithmetic mean of ``arr`` as a ``float``.

    See Also
    --------
    numba.njit : Decorator that compiles this helper in nopython mode
        so it can be passed as a first-class callable.
    std1d : Sibling helper that computes the standard deviation of a
        1-D slice.
    mean2d : Higher-level wrapper that applies this reducer along an
        axis of a 2-D array via :func:`np_apply_along_axis_2d`.
    np_apply_along_axis_2d : Dispatch helper that receives this
        function as its ``nb_func1d`` argument.

    Examples
    --------
    >>> import numpy as np
    >>> from mayutils.mathematics.numba import mean1d
    >>> bool(np.isclose(mean1d(np.array([1.0, 2.0, 3.0, 4.0])), 2.5))
    True
    """
    return float(np.mean(arr))


def mean2d(
    arr: NDArray[np.float64],
    *,
    axis: int,
) -> NDArray[np.float64]:
    """
    Compute per-column or per-row arithmetic means of a 2-D array.

    Wrap :func:`np_apply_along_axis_2d` with :func:`numpy.mean` as the
    bound reducer, exposed as a standalone helper so that Numba can
    inline and cache the compiled result at each call site. The
    ``cache=True`` decorator stores the compiled machine code between
    sessions so the JIT overhead is paid only once. The type signature
    is inferred from the concrete ``NDArray[np.float64]`` input, which
    keeps the compiled kernel tightly specialised. Input validation is
    delegated to :func:`np_apply_along_axis_2d`, which raises
    ``AssertionError`` for non-2-D arrays or invalid axis values.

    Parameters
    ----------
    arr
        Two-dimensional input whose entries are averaged. Must be
        exactly 2-D.
    axis
        Axis along which to compute the mean. ``0`` averages within
        each column and yields one value per column; ``1`` averages
        within each row and yields one value per row.

    Returns
    -------
        One-dimensional array of arithmetic means. Its length equals
        ``arr.shape[1]`` when ``axis == 0`` and ``arr.shape[0]`` when
        ``axis == 1``.

    See Also
    --------
    numba.njit : Decorator used to JIT-compile this wrapper in
        nopython mode with on-disk caching.
    numba.typed : Typed container utilities that complement compiled
        reductions.
    numba.cuda : GPU dispatch layer for per-axis averaging on device
        memory.
    mayutils.mathematics.numpy : Non-JIT NumPy counterparts for
        contexts that do not require Numba.
    np_apply_along_axis_2d : Underlying dispatch helper that this
        wrapper specialises.
    std2d : Sibling helper that computes standard deviations instead
        of means.

    Examples
    --------
    >>> import numpy as np
    >>> from mayutils.mathematics.numba import np_apply_along_axis_2d
    >>> data = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    >>> mean2d(data, axis=0)
    array([2.5, 3.5, 4.5])
    >>> mean2d(data, axis=1)
    array([2., 5.])
    """
    return np_apply_along_axis_2d(
        mean1d,
        arr=arr,
        axis=axis,
    )


@njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def std1d(
    arr: NDArray[np.float64],
) -> float:
    """
    Compute the standard deviation of a 1-D array inside Numba-compiled code.

    Wrap :func:`numpy.std` in an ``@njit`` kernel so that it can be
    passed as a callable argument to other compiled functions such as
    :func:`np_apply_along_axis_2d`. Numba requires any function passed
    at runtime to have a known compiled type; wrapping the NumPy
    dispatcher in this thin kernel satisfies that constraint without
    changing the statistical contract. The population standard
    deviation (``ddof=0``) is used, matching NumPy's default.

    Parameters
    ----------
    arr
        One-dimensional array whose dispersion is measured. The result
        is cast to ``float`` to produce a scalar compatible with the
        output buffer of :func:`np_apply_along_axis_2d`.

    Returns
    -------
        Population standard deviation of ``arr`` as a ``float``.

    See Also
    --------
    numba.njit : Decorator that compiles this helper in nopython mode
        so it can be passed as a first-class callable.
    mean1d : Sibling helper that computes the arithmetic mean of a
        1-D slice.
    std2d : Higher-level wrapper that applies this reducer along an
        axis of a 2-D array via :func:`np_apply_along_axis_2d`.
    np_apply_along_axis_2d : Dispatch helper that receives this
        function as its ``nb_func1d`` argument.

    Examples
    --------
    >>> import numpy as np
    >>> from mayutils.mathematics.numba import std1d
    >>> bool(np.isclose(std1d(np.array([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])), 2.0))
    True
    """
    return float(np.std(arr))


def std2d(
    arr: NDArray[np.float64],
    *,
    axis: int,
) -> NDArray[np.float64]:
    """
    Compute per-column or per-row standard deviations of a 2-D array.

    Wrap :func:`np_apply_along_axis_2d` with :func:`numpy.std` as the
    bound reducer. Like NumPy's default, the population standard
    deviation (``ddof=0``) is used for each slice. The ``cache=True``
    JIT decorator stores the compiled kernel so subsequent interpreter
    sessions skip the nopython-mode compilation step and reload the
    machine code directly. Input validation is delegated to
    :func:`np_apply_along_axis_2d`, which raises ``AssertionError``
    for non-2-D arrays or invalid axis values.

    Parameters
    ----------
    arr
        Two-dimensional input whose dispersion is measured. Must be
        exactly 2-D.
    axis
        Axis along which to compute the standard deviation. ``0``
        reduces each column to its standard deviation, yielding one
        value per column; ``1`` reduces each row, yielding one value
        per row.

    Returns
    -------
        One-dimensional array of standard deviations. Its length
        equals ``arr.shape[1]`` when ``axis == 0`` and
        ``arr.shape[0]`` when ``axis == 1``.

    See Also
    --------
    numba.njit : Decorator used to JIT-compile this wrapper in
        nopython mode with on-disk caching.
    numba.typed : Typed container utilities that complement compiled
        reductions.
    numba.cuda : GPU dispatch layer for computing dispersion on
        device memory.
    mayutils.mathematics.numpy : Non-JIT NumPy counterparts for
        contexts that do not require Numba.
    np_apply_along_axis_2d : Underlying dispatch helper that this
        wrapper specialises.
    mean2d : Sibling helper that computes arithmetic means instead of
        standard deviations.

    Examples
    --------
    >>> import numpy as np
    >>> from mayutils.mathematics.numba import np_apply_along_axis_2d
    >>> data = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    >>> std2d(data, axis=0)
    array([1.5, 1.5, 1.5])
    >>> bool(np.allclose(std2d(data, axis=1), np.std(data, axis=1)))
    True
    """
    return np_apply_along_axis_2d(
        std1d,
        arr=arr,
        axis=axis,
    )
