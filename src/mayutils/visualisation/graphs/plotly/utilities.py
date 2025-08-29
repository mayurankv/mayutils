from typing import Optional
from pandas import DataFrame
import numpy as np
from numpy.typing import ArrayLike, NDArray


def map_categorical_array(
    arr: NDArray,
    mapping: Optional[ArrayLike] = None,
) -> NDArray[np.int64]:
    if (mapping is not None) and (len(set(mapping)) != len(mapping)):  # type: ignore
        raise ValueError("Mapping is not unique")

    mapping_ = (
        np.asarray(mapping)
        if mapping is not None
        else arr[sorted(np.unique(arr, return_index=True)[1])]
    )
    mapping_dict = {value: idx for idx, value in enumerate(mapping_)}
    arr_numerical = np.asarray([mapping_dict.get(value, -1) for value in arr])
    if arr_numerical.min() != 0:
        raise ValueError("Mapping is not complete")

    return arr_numerical


def melt_dataframe(
    df: DataFrame,
) -> tuple[NDArray, NDArray, NDArray]:
    values = df.melt(ignore_index=False).reset_index().to_numpy().transpose()

    return (
        values[0],
        values[1],
        values[2],
    )
