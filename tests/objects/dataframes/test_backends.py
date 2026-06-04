"""Tests for ``mayutils.objects.dataframes.backends``.

These tests cover the lean ``Backend`` type token (construction, inference and
casting) and the engine-agnostic ``BackendOperations`` helpers (concat,
filter_ge, max, tail, deduplicate) across the pandas and polars backends,
including edge and unsupported-backend error cases.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

from mayutils.objects.dataframes.backends import (
    Backend,
    BackendOperations,
    default_backend,
)

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl
else:
    pd = pytest.importorskip("pandas")
    pl = pytest.importorskip("polars")


def pandas_backend() -> Backend[pd.DataFrame]:
    """Return a pandas-bound backend token.

    Returns
    -------
        A backend token wrapping ``pd.DataFrame``.
    """
    return Backend(pd.DataFrame)


def polars_backend() -> Backend[pl.DataFrame]:
    """Return a polars-bound backend token.

    Returns
    -------
        A backend token wrapping ``pl.DataFrame``.
    """
    return Backend(pl.DataFrame)


def unsupported_backend() -> Backend[pd.DataFrame]:
    """Return a backend token whose ``name`` is neither pandas nor polars.

    The frame type stays a real DataFrame class (keeping ``Backend`` a lean
    token) while the public ``name`` attribute is set to an unsupported engine
    so the dispatch ``ValueError`` paths can be exercised.

    Returns
    -------
        A backend token reporting an unsupported engine name.
    """
    backend = Backend(pd.DataFrame)
    backend.name = "duckdb"
    return backend


class TestBackendConstruction:
    """Tests for :class:`Backend` construction and attributes."""

    def test_pandas_name(self) -> None:
        """A pandas frame type yields the ``pandas`` library name."""
        assert Backend(pd.DataFrame).name == "pandas"

    def test_polars_name(self) -> None:
        """A polars frame type yields the ``polars`` library name."""
        assert Backend(pl.DataFrame).name == "polars"

    def test_frame_type_retained(self) -> None:
        """The supplied concrete frame type is stored verbatim."""
        assert Backend(pd.DataFrame).frame_type is pd.DataFrame

    def test_name_is_top_level_module(self) -> None:
        """The name is the first dotted segment of the frame type's module."""
        assert Backend(pd.DataFrame).name == pd.DataFrame.__module__.split(".", maxsplit=1)[0]


class TestBackendRepr:
    """Tests for :meth:`Backend.__repr__`."""

    def test_pandas_repr(self) -> None:
        """The repr embeds the quoted name and the frame type."""
        assert repr(Backend(pd.DataFrame)) == "Backend('pandas', <class 'pandas.core.frame.DataFrame'>)"

    def test_polars_repr_contains_name(self) -> None:
        """The polars repr leads with the quoted library name."""
        assert repr(Backend(pl.DataFrame)).startswith("Backend('polars', ")


class TestBackendInfer:
    """Tests for :meth:`Backend.infer` — construct a token from an instance."""

    def test_infer_from_pandas_instance(self) -> None:
        """A pandas instance infers the pandas backend."""
        assert Backend.infer(pd.DataFrame({"a": [1]})).name == "pandas"

    def test_infer_from_polars_instance(self) -> None:
        """A polars instance infers the polars backend."""
        assert Backend.infer(pl.DataFrame({"a": [1]})).name == "polars"

    def test_infer_from_empty_pandas(self) -> None:
        """Inference works on an empty pandas frame."""
        assert Backend.infer(pd.DataFrame()).name == "pandas"

    def test_infer_from_empty_polars(self) -> None:
        """Inference works on an empty polars frame."""
        assert Backend.infer(pl.DataFrame()).name == "polars"

    def test_infer_frame_type_matches_instance(self) -> None:
        """The inferred frame type is the exact type of the instance."""
        assert Backend.infer(pd.DataFrame()).frame_type is pd.DataFrame


class TestBackendCast:
    """Tests for :meth:`Backend.cast` — a runtime no-op typing narrowing."""

    def test_cast_returns_same_object(self) -> None:
        """Casting returns the very same object (no copy or conversion)."""
        frame = pd.DataFrame({"a": [1, 2]})
        assert Backend(pd.DataFrame).cast(frame) is frame

    def test_cast_does_not_convert_engine(self) -> None:
        """Casting does not coerce a polars frame into a pandas frame at runtime."""
        frame = pl.DataFrame({"a": [1]})
        assert Backend(pd.DataFrame).cast(frame) is frame


class TestDefaultBackend:
    """Tests for :func:`default_backend`."""

    def test_name(self) -> None:
        """The default backend is pandas."""
        assert default_backend().name == "pandas"

    def test_frame_type(self) -> None:
        """The default backend wraps ``pd.DataFrame``."""
        assert default_backend().frame_type is pd.DataFrame


class TestConcat:
    """Tests for :meth:`BackendOperations.concat`."""

    def test_pandas_concat_values(self) -> None:
        """Concatenated pandas frames stack all rows in order."""
        result = BackendOperations.concat(
            pd.DataFrame({"x": [1, 2]}),
            pd.DataFrame({"x": [3]}),
            backend=pandas_backend(),
        )
        assert result["x"].tolist() == [1, 2, 3]

    def test_pandas_concat_resets_index(self) -> None:
        """Pandas concat ignores the source index and produces a fresh range index."""
        result = BackendOperations.concat(
            pd.DataFrame({"x": [1, 2]}, index=[10, 11]),
            pd.DataFrame({"x": [3]}, index=[99]),
            backend=pandas_backend(),
        )
        assert result.index.tolist() == [0, 1, 2]

    def test_polars_concat_values(self) -> None:
        """Concatenated polars frames stack all rows in order."""
        result = BackendOperations.concat(
            pl.DataFrame({"x": [1, 2]}),
            pl.DataFrame({"x": [3]}),
            backend=polars_backend(),
        )
        assert result["x"].to_list() == [1, 2, 3]

    def test_pandas_concat_single_frame(self) -> None:
        """Concatenating a single pandas frame returns its rows unchanged."""
        result = BackendOperations.concat(
            pd.DataFrame({"x": [1, 2]}),
            backend=pandas_backend(),
        )
        assert result["x"].tolist() == [1, 2]

    def test_unsupported_backend_raises(self) -> None:
        """An unsupported backend raises ``ValueError`` naming the engine."""
        with pytest.raises(expected_exception=ValueError, match="Unsupported backend: duckdb"):
            BackendOperations.concat(pd.DataFrame({"x": [1]}), backend=unsupported_backend())


class TestFilterGe:
    """Tests for :meth:`BackendOperations.filter_ge` — keep rows where column >= value."""

    def test_pandas_filter_values(self) -> None:
        """Only rows meeting the inclusive lower bound survive on pandas."""
        frame = pd.DataFrame({"v": [1, 5, 3, 5, 2]})
        result = BackendOperations.filter_ge(frame, "v", 5, backend=pandas_backend())
        assert result["v"].tolist() == [5, 5]

    def test_pandas_filter_is_inclusive(self) -> None:
        """The boundary value itself is retained (>=, not >)."""
        frame = pd.DataFrame({"v": [2, 3, 4]})
        result = BackendOperations.filter_ge(frame, "v", 3, backend=pandas_backend())
        assert result["v"].tolist() == [3, 4]

    def test_polars_filter_values(self) -> None:
        """Only rows meeting the inclusive lower bound survive on polars."""
        frame = pl.DataFrame({"v": [1, 5, 3, 5, 2]})
        result = BackendOperations.filter_ge(frame, "v", 5, backend=polars_backend())
        assert result["v"].to_list() == [5, 5]

    def test_pandas_filter_excludes_everything(self) -> None:
        """A bound above every value yields an empty frame, preserving columns."""
        frame = pd.DataFrame({"v": [1, 2, 3]})
        result = BackendOperations.filter_ge(frame, "v", 100, backend=pandas_backend())
        assert result.shape == (0, 1)

    def test_polars_filter_excludes_everything(self) -> None:
        """A bound above every value yields an empty polars frame."""
        frame = pl.DataFrame({"v": [1, 2, 3]})
        result = BackendOperations.filter_ge(frame, "v", 100, backend=polars_backend())
        assert result.height == 0

    def test_pandas_filter_keeps_everything(self) -> None:
        """A bound at or below the minimum keeps every row."""
        frame = pd.DataFrame({"v": [1, 2, 3]})
        result = BackendOperations.filter_ge(frame, "v", 0, backend=pandas_backend())
        assert result["v"].tolist() == [1, 2, 3]

    def test_unsupported_backend_raises(self) -> None:
        """An unsupported backend raises ``ValueError``."""
        with pytest.raises(expected_exception=ValueError, match="Unsupported backend: duckdb"):
            BackendOperations.filter_ge(pd.DataFrame({"v": [1]}), "v", 1, backend=unsupported_backend())


class TestMax:
    """Tests for :meth:`BackendOperations.max`."""

    def test_pandas_max(self) -> None:
        """The scalar maximum is returned for pandas."""
        frame = pd.DataFrame({"v": [1, 5, 3]})
        assert BackendOperations.max(frame, "v", backend=pandas_backend()) == 5  # noqa: PLR2004

    def test_polars_max(self) -> None:
        """The scalar maximum is returned for polars."""
        frame = pl.DataFrame({"v": [1, 5, 3]})
        assert BackendOperations.max(frame, "v", backend=polars_backend()) == 5  # noqa: PLR2004

    def test_pandas_max_float_close(self) -> None:
        """Floating-point maxima match within tolerance on pandas."""
        frame = pd.DataFrame({"v": [0.1, 0.2, 0.3]})
        assert np.isclose(BackendOperations.max(frame, "v", backend=pandas_backend()), 0.3)

    def test_max_single_row(self) -> None:
        """A single-row frame returns that row's value."""
        frame = pd.DataFrame({"v": [42]})
        assert BackendOperations.max(frame, "v", backend=pandas_backend()) == 42  # noqa: PLR2004

    def test_pandas_max_empty_is_nan(self) -> None:
        """Pandas returns NaN for the max of an empty column."""
        frame = pd.DataFrame({"v": pd.Series([], dtype="float64")})
        assert np.isnan(BackendOperations.max(frame, "v", backend=pandas_backend()))

    def test_polars_max_empty_is_none(self) -> None:
        """Polars returns ``None`` for the max of an empty column."""
        frame = pl.DataFrame({"v": pl.Series([], dtype=pl.Float64)})
        assert BackendOperations.max(frame, "v", backend=polars_backend()) is None

    def test_unsupported_backend_raises(self) -> None:
        """An unsupported backend raises ``ValueError``."""
        with pytest.raises(expected_exception=ValueError, match="Unsupported backend: duckdb"):
            BackendOperations.max(pd.DataFrame({"v": [1]}), "v", backend=unsupported_backend())


class TestTail:
    """Tests for :meth:`BackendOperations.tail`."""

    def test_pandas_tail(self) -> None:
        """The last ``n`` rows are returned for pandas."""
        frame = pd.DataFrame({"v": [0, 1, 2, 3, 4]})
        assert BackendOperations.tail(frame, 2, backend=pandas_backend())["v"].tolist() == [3, 4]

    def test_polars_tail(self) -> None:
        """The last ``n`` rows are returned for polars."""
        frame = pl.DataFrame({"v": [0, 1, 2, 3, 4]})
        assert BackendOperations.tail(frame, 2, backend=polars_backend())["v"].to_list() == [3, 4]

    def test_pandas_tail_zero_is_empty(self) -> None:
        """Requesting zero trailing rows yields an empty frame."""
        frame = pd.DataFrame({"v": [0, 1, 2]})
        assert BackendOperations.tail(frame, 0, backend=pandas_backend())["v"].tolist() == []

    def test_pandas_tail_larger_than_frame(self) -> None:
        """Requesting more rows than exist returns the whole frame."""
        frame = pd.DataFrame({"v": [0, 1, 2]})
        assert BackendOperations.tail(frame, 99, backend=pandas_backend())["v"].tolist() == [0, 1, 2]

    def test_polars_tail_larger_than_frame(self) -> None:
        """Oversized ``n`` returns the whole polars frame."""
        frame = pl.DataFrame({"v": [0, 1, 2]})
        assert BackendOperations.tail(frame, 99, backend=polars_backend())["v"].to_list() == [0, 1, 2]

    def test_unsupported_backend_raises(self) -> None:
        """An unsupported backend raises ``ValueError``."""
        with pytest.raises(expected_exception=ValueError, match="Unsupported backend: duckdb"):
            BackendOperations.tail(pd.DataFrame({"v": [1]}), 1, backend=unsupported_backend())


class TestDeduplicate:
    """Tests for :meth:`BackendOperations.deduplicate` — keep the last per key."""

    def test_pandas_keeps_last_occurrence(self) -> None:
        """Pandas dedup keeps the last row for each key and preserves order."""
        frame = pd.DataFrame({"id": [1, 2, 1, 2, 3], "t": [10, 20, 30, 40, 50]})
        result = BackendOperations.deduplicate(frame, "id", backend=pandas_backend())
        assert result.to_dict(orient="records") == [
            {"id": 1, "t": 30},
            {"id": 2, "t": 40},
            {"id": 3, "t": 50},
        ]

    def test_polars_keeps_last_occurrence(self) -> None:
        """Polars dedup keeps the last row per key (order not guaranteed, so sort first)."""
        frame = pl.DataFrame({"id": [1, 2, 1, 2, 3], "t": [10, 20, 30, 40, 50]})
        result = BackendOperations.deduplicate(frame, "id", backend=polars_backend())
        assert result.sort("id").to_dicts() == [
            {"id": 1, "t": 30},
            {"id": 2, "t": 40},
            {"id": 3, "t": 50},
        ]

    def test_pandas_no_duplicates_unchanged(self) -> None:
        """With no duplicate keys, every row is retained on pandas."""
        frame = pd.DataFrame({"id": [1, 2, 3], "t": [10, 20, 30]})
        result = BackendOperations.deduplicate(frame, "id", backend=pandas_backend())
        assert result["id"].tolist() == [1, 2, 3]

    def test_pandas_all_duplicates_keeps_last(self) -> None:
        """When every row shares a key, only the final row survives."""
        frame = pd.DataFrame({"id": [7, 7, 7], "t": [1, 2, 3]})
        result = BackendOperations.deduplicate(frame, "id", backend=pandas_backend())
        assert result.to_dict(orient="records") == [{"id": 7, "t": 3}]

    def test_pandas_single_row(self) -> None:
        """A single-row frame is returned unchanged."""
        frame = pd.DataFrame({"id": [1], "t": [10]})
        result = BackendOperations.deduplicate(frame, "id", backend=pandas_backend())
        assert result.to_dict(orient="records") == [{"id": 1, "t": 10}]

    def test_unsupported_backend_raises(self) -> None:
        """An unsupported backend raises ``ValueError``."""
        with pytest.raises(expected_exception=ValueError, match="Unsupported backend: duckdb"):
            BackendOperations.deduplicate(pd.DataFrame({"id": [1]}), "id", backend=unsupported_backend())
