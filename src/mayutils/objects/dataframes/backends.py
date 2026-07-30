"""Provide the generic ``Backend`` type token and pre-built singletons."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from mayutils.core.extras import may_require_extras

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl


type DataFrames = pd.DataFrame | pl.DataFrame
"""Union of supported concrete DataFrame types."""


class Backend[DataFrameType: DataFrames = pd.DataFrame]:
    """
    Generic DataFrame backend token used to dispatch reads and writes.

    Wraps a concrete DataFrame class and exposes its library name for
    backend-aware dispatch throughout the IO layer.

    Parameters
    ----------
    frame_type
        Concrete DataFrame class (e.g. ``pd.DataFrame``).

    Attributes
    ----------
    frame_type
        Concrete DataFrame class (e.g. ``pd.DataFrame``).
    name
        Library name derived from the frame type's module.

    See Also
    --------
    mayutils.interfaces.filetypes.DataFile : Consumer that accepts a
        ``Backend`` to control read/write dispatch.

    Examples
    --------
    >>> import pandas as pd
    >>> from mayutils.objects.dataframes.backends import Backend
    >>> b = Backend(pd.DataFrame)
    >>> b.name
    'pandas'
    """

    def __init__(
        self,
        frame_type: type[DataFrameType],
        /,
    ) -> None:
        """
        Initialise the backend token from a concrete DataFrame class.

        Derives the library name from the first segment of the class's
        ``__module__`` attribute.

        Parameters
        ----------
        frame_type
            Concrete DataFrame class (e.g. ``pd.DataFrame``).

        See Also
        --------
        Backend.infer : Alternative constructor from a DataFrame instance.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.backends import Backend
        >>> Backend(pd.DataFrame).name
        'pandas'
        """
        self.frame_type = frame_type
        self.name = frame_type.__module__.split(sep=".", maxsplit=1)[0]

    def __repr__(
        self,
    ) -> str:
        """
        Return ``Backend(<name>, <frame_type>)``.

        Format the backend's name and frame type into a readable string
        suitable for debugging and logging output.

        Returns
        -------
            Human-readable representation of the backend.

        See Also
        --------
        Backend.infer : Alternative constructor from a DataFrame instance.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.backends import Backend
        >>> repr(Backend(pd.DataFrame))
        "Backend('pandas', <class 'pandas.core.frame.DataFrame'>)"
        """
        return f"Backend({self.name!r}, {self.frame_type!r})"

    @staticmethod
    def infer[AltDataFrameType: DataFrames](
        df: AltDataFrameType,
        /,
    ) -> Backend[AltDataFrameType]:
        """
        Infer the backend from a DataFrame instance.

        Constructs a new ``Backend`` token by extracting the concrete
        type of the supplied DataFrame.

        Parameters
        ----------
        df
            DataFrame whose type determines the backend.

        Returns
        -------
            A new ``Backend`` bound to the type of *df*.

        See Also
        --------
        Backend.__init__ : Direct constructor from a DataFrame class.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.backends import Backend
        >>> Backend.infer(pd.DataFrame()).name
        'pandas'
        """
        return Backend(type(df))

    def cast(
        self,
        df: DataFrames,
        /,
    ) -> DataFrameType:
        """
        Cast *df* to this backend's frame type.

        Performs a :func:`typing.cast` to narrow the union type to this
        backend's concrete ``frame_type``.

        Parameters
        ----------
        df
            DataFrame to cast.

        Returns
        -------
            *df* cast to this backend's ``frame_type``.

        See Also
        --------
        Backend.infer : Infer the backend from a DataFrame instance.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.backends import Backend
        >>> b = Backend(pd.DataFrame)
        >>> b.cast(pd.DataFrame({"a": [1]})).shape
        (1, 1)
        """
        return cast("DataFrameType", df)


def default_backend() -> Backend[pd.DataFrame]:
    """
    Return the default pandas backend token.

    Convenience constructor that avoids repeating ``Backend(pd.DataFrame)``
    at every call site that needs a fallback backend.

    Returns
    -------
        A ``Backend`` wrapping ``pd.DataFrame``.

    See Also
    --------
    Backend : Generic backend token type.

    Examples
    --------
    >>> from mayutils.objects.dataframes.backends import default_backend
    >>> default_backend().name
    'pandas'
    """
    with may_require_extras():
        import pandas as pd

    return Backend(pd.DataFrame)


class BackendOperations:
    """
    Backend-dispatched DataFrame operations.

    Provides static helpers that delegate to the correct library
    (pandas or polars) based on the supplied :class:`Backend` token.

    See Also
    --------
    Backend : Token that selects the concrete DataFrame library.

    Examples
    --------
    >>> import pandas as pd
    >>> from mayutils.objects.dataframes.backends import BackendOperations, Backend
    >>> b = Backend(pd.DataFrame)
    >>> BackendOperations.tail(pd.DataFrame({"x": [0, 1, 2, 3]}), 2, backend=b)
       x
    2  2
    3  3
    """

    @staticmethod
    def concat[DataFrameType: DataFrames](
        *frames: DataFrameType,
        backend: Backend[DataFrameType],
    ) -> DataFrameType:
        """
        Concatenate DataFrames using the appropriate backend library.

        Delegates to ``pd.concat`` or ``pl.concat`` depending on the
        *backend* token.

        Parameters
        ----------
        *frames
            DataFrames to concatenate.
        backend
            Backend token selecting the concat implementation.

        Returns
        -------
            Single concatenated DataFrame.

        Raises
        ------
        ValueError
            If *backend* is not supported.

        See Also
        --------
        BackendOperations.tail : Keep only the last *n* rows.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.backends import Backend, BackendOperations
        >>> b = Backend(pd.DataFrame)
        >>> df1 = pd.DataFrame({"x": [1, 2]})
        >>> df2 = pd.DataFrame({"x": [3]})
        >>> BackendOperations.concat(df1, df2, backend=b)
           x
        0  1
        1  2
        2  3
        """
        if backend.name == "pandas":
            with may_require_extras():
                import pandas as pd

            return cast("DataFrameType", pd.concat(cast("list[pd.DataFrame]", frames), ignore_index=True))
        if backend.name == "polars":
            with may_require_extras():
                import polars as pl

            return cast("DataFrameType", pl.concat(items=cast("list[pl.DataFrame]", frames)))

        msg = f"Unsupported backend: {backend.name}"
        raise ValueError(msg)

    @staticmethod
    def filter_ge[DataFrameType: DataFrames](
        frame: DataFrameType,
        column: str,
        value: Any,  # noqa: ANN401
        /,
        *,
        backend: Backend[DataFrameType],
    ) -> DataFrameType:
        """
        Keep rows where *column* >= *value*.

        Applies a greater-than-or-equal filter using the pandas or polars
        API according to the *backend* token.

        Parameters
        ----------
        frame
            Source DataFrame.
        column
            Column name to compare.
        value
            Inclusive lower bound.
        backend
            Backend token selecting the filter implementation.

        Returns
        -------
            Filtered DataFrame.

        Raises
        ------
        ValueError
            If *backend* is not supported.

        See Also
        --------
        BackendOperations.max : Compute the column maximum.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.backends import Backend, BackendOperations
        >>> b = Backend(pd.DataFrame)
        >>> df = pd.DataFrame({"v": [1, 5, 3]})
        >>> BackendOperations.filter_ge(df, "v", 3, backend=b)
           v
        1  5
        2  3
        """
        if backend.name == "pandas":
            pandas_frame = cast("pd.DataFrame", frame)
            return cast("DataFrameType", pandas_frame.loc[pandas_frame[column] >= value])
        if backend.name == "polars":
            with may_require_extras():
                import polars as pl

            return cast("DataFrameType", cast("pl.DataFrame", frame).filter(pl.col(name=column) >= value))

        msg = f"Unsupported backend: {backend.name}"
        raise ValueError(msg)

    @staticmethod
    def max[DataFrameType: DataFrames](
        frame: DataFrameType,
        column: str,
        /,
        *,
        backend: Backend[DataFrameType],
    ) -> Any:  # noqa: ANN401
        """
        Return the maximum value in *column*.

        Extracts the scalar maximum using the pandas or polars API
        according to the *backend* token.

        Parameters
        ----------
        frame
            Source DataFrame.
        column
            Column whose maximum is computed.
        backend
            Backend token selecting the aggregation implementation.

        Returns
        -------
            Scalar maximum value.

        Raises
        ------
        ValueError
            If *backend* is not supported.

        See Also
        --------
        BackendOperations.filter_ge : Filter rows by column threshold.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.backends import Backend, BackendOperations
        >>> b = Backend(pd.DataFrame)
        >>> df = pd.DataFrame({"id": [1, 4, 2]})
        >>> int(BackendOperations.max(df, "id", backend=b))
        4
        """
        if backend.name == "pandas":
            return cast("pd.DataFrame", frame)[column].max()
        if backend.name == "polars":
            with may_require_extras():
                import polars as pl

            return cast("pl.DataFrame", frame).select(pl.col(name=column).max()).item()

        msg = f"Unsupported backend: {backend.name}"
        raise ValueError(msg)

    @staticmethod
    def tail[DataFrameType: DataFrames](
        frame: DataFrameType,
        n: int,
        /,
        *,
        backend: Backend[DataFrameType],
    ) -> DataFrameType:
        """
        Return the last *n* rows.

        Delegates to the ``tail`` method of the underlying pandas or polars
        DataFrame.

        Parameters
        ----------
        frame
            Source DataFrame.
        n
            Number of trailing rows to keep.
        backend
            Backend token selecting the tail implementation.

        Returns
        -------
            DataFrame containing the last *n* rows.

        Raises
        ------
        ValueError
            If *backend* is not supported.

        See Also
        --------
        BackendOperations.concat : Concatenate DataFrames.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.backends import Backend, BackendOperations
        >>> b = Backend(pd.DataFrame)
        >>> df = pd.DataFrame({"v": [0, 1, 2, 3]})
        >>> BackendOperations.tail(df, 2, backend=b)
           v
        2  2
        3  3
        """
        if backend.name == "pandas":
            return cast("DataFrameType", cast("pd.DataFrame", frame).tail(n))
        if backend.name == "polars":
            return cast("DataFrameType", cast("pl.DataFrame", frame).tail(n))

        msg = f"Unsupported backend: {backend.name}"
        raise ValueError(msg)

    @staticmethod
    def deduplicate[DataFrameType: DataFrames](
        frame: DataFrameType,
        column: str,
        /,
        *,
        backend: Backend[DataFrameType],
    ) -> DataFrameType:
        """
        Remove duplicate rows based on *column*, keeping the last occurrence.

        Uses ``drop_duplicates`` (pandas) or ``unique`` (polars) to retain
        only the last row for each distinct value in *column*.

        Parameters
        ----------
        frame
            Source DataFrame.
        column
            Column used to identify duplicates.
        backend
            Backend token selecting the dedup implementation.

        Returns
        -------
            Deduplicated DataFrame.

        Raises
        ------
        ValueError
            If *backend* is not supported.

        See Also
        --------
        BackendOperations.concat : Concatenate DataFrames.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.objects.dataframes.backends import Backend, BackendOperations
        >>> b = Backend(pd.DataFrame)
        >>> df = pd.DataFrame({"id": [1, 1, 2], "t": [10, 20, 30]})
        >>> BackendOperations.deduplicate(df, "id", backend=b)
           id   t
        1   1  20
        2   2  30
        """
        if backend.name == "pandas":
            return cast("DataFrameType", cast("pd.DataFrame", frame).drop_duplicates(subset=column, keep="last"))
        if backend.name == "polars":
            return cast("DataFrameType", cast("pl.DataFrame", frame).unique(subset=column, keep="last"))

        msg = f"Unsupported backend: {backend.name}"
        raise ValueError(msg)


__all__ = [
    "Backend",
    "BackendOperations",
    "default_backend",
]
