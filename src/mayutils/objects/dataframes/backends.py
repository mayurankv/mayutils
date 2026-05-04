"""Provide the generic ``Backend`` type token and pre-built singletons."""

from __future__ import annotations

from typing import cast

from mayutils.core.extras import may_require_extras

with may_require_extras():
    import pandas as pd


with may_require_extras():
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
    return Backend(pd.DataFrame)


__all__ = [
    "Backend",
    "default_backend",
]
