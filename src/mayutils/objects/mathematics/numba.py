from typing import Optional
from numba import njit
import numpy as np
from numpy.typing import NDArray


@njit
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

    return arr[
        np.searchsorted(
            np.cumsum(p),
            np.random.random(size=size),
            side="right",
        )
    ]
