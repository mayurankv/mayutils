from numpy.typing import NDArray as NDArray
from typing import Callable

def choice_replacement(
    arr: NDArray,
    p: NDArray | None = None,
    size: tuple[int, ...] | None = None,
    seed: int | None = None,
) -> NDArray: ...
def np_apply_along_axis_2d(
    func1d: Callable[[NDArray], float], arr: NDArray, axis: int
) -> NDArray: ...
def mean2d(arr: NDArray, axis: int) -> NDArray: ...
def std2d(arr: NDArray, axis: int) -> NDArray: ...
