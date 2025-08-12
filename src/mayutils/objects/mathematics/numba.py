from typing import Callable, Optional
from numba import njit
import numpy as np
from numpy.typing import NDArray


@njit(cache=True)
def choice_replacement(
    arr: NDArray,
    p: Optional[NDArray] = None,
    size: Optional[tuple[int, ...]] = None,
    seed: Optional[int] = None,
) -> NDArray:
    if seed is not None:
        np.random.seed(seed=seed)

    if p is None:
        return np.random.choice(a=arr, size=size)

    indices = np.searchsorted(
        np.cumsum(p),
        np.random.random(size=size),
        side="right",
    )

    return arr[indices.ravel()].reshape(indices.shape)


@njit(cache=True)
def np_apply_along_axis_2d(
    func1d: Callable[[NDArray], float],
    arr: NDArray,
    axis: int,
) -> NDArray:
    assert arr.ndim == 2
    assert axis in [0, 1]

    if axis == 0:
        result = np.empty(arr.shape[1])
        for i in range(len(result)):
            result[i] = func1d(arr[:, i])
    else:
        result = np.empty(arr.shape[0])
        for i in range(len(result)):
            result[i] = func1d(arr[i, :])

    return result


@njit(cache=True)
def mean2d(
    arr: NDArray,
    axis: int,
) -> NDArray:
    return np_apply_along_axis_2d(
        func1d=np.mean,
        arr=arr,
        axis=axis,
    )


@njit(cache=True)
def std2d(
    arr: NDArray,
    axis: int,
) -> NDArray:
    return np_apply_along_axis_2d(
        func1d=np.std,
        arr=arr,
        axis=axis,
    )
