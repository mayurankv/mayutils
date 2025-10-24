import numpy as np
from numpy.typing import ArrayLike as ArrayLike, NDArray as NDArray
from pandas import DataFrame

def map_categorical_array(
    arr: NDArray, mapping: ArrayLike | None = None
) -> NDArray[np.int64]: ...
def melt_dataframe(df: DataFrame) -> tuple[NDArray, NDArray, NDArray]: ...
