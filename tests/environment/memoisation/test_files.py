"""Tests for ``mayutils.environment.memoisation.files``.

Covers the serialiser registry (pickle, numpy, npz, DataFile-backed),
suffix inference, the human-readable cache-stem builder, and the
file-backed :class:`FileStore` (round-trips, deferred suffix resolution,
staleness/TTL, deletion, clearing, and path resolution). The module
serialises DataFrames and arrays, so pandas, polars, numpy and pyarrow
are required.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

pytest.importorskip("pandas")
pytest.importorskip("polars")
pytest.importorskip("numpy")
pytest.importorskip("pyarrow")
pytest.importorskip("pendulum")

if TYPE_CHECKING:
    from pathlib import Path

    import numpy as np
    import pandas as pd
    import polars as pl
else:
    np = pytest.importorskip("numpy")
    pd = pytest.importorskip("pandas")
    pl = pytest.importorskip("polars")

from mayutils.environment.memoisation.files import (
    DataFileSerialiser,
    FileStore,
    NpzSerialiser,
    NumpySerialiser,
    PickleSerialiser,
    Serialiser,
    get_serialiser,
    infer_suffix,
    make_cache_stem,
)
from mayutils.environment.memoisation.types import MISSING
from mayutils.objects.datetime import Duration
from mayutils.objects.types import SQL


class TestInferSuffix:
    """Tests for :func:`infer_suffix` — maps an object's type to a file suffix."""

    def test_pandas_dataframe_infers_parquet(self) -> None:
        """A pandas DataFrame is stored as parquet."""
        assert infer_suffix(pd.DataFrame({"a": [1]})) == ".parquet"

    def test_polars_dataframe_infers_parquet(self) -> None:
        """A polars DataFrame is stored as parquet."""
        assert infer_suffix(pl.DataFrame({"a": [1]})) == ".parquet"

    def test_ndarray_infers_npy(self) -> None:
        """A single ndarray is stored as ``.npy``."""
        assert infer_suffix(np.array([1, 2, 3])) == ".npy"

    def test_dict_of_arrays_infers_npz(self) -> None:
        """A mapping whose values are all arrays is stored as ``.npz``."""
        assert infer_suffix({"a": np.array([1]), "b": np.array([2])}) == ".npz"

    def test_plain_mapping_infers_pickle(self) -> None:
        """A mapping with non-array values falls back to pickle."""
        assert infer_suffix({"a": 1}) == ".pkl"

    def test_arbitrary_object_infers_pickle(self) -> None:
        """Anything else falls back to pickle."""
        assert infer_suffix("hello") == ".pkl"


class TestGetSerialiser:
    """Tests for :func:`get_serialiser` — resolves a serialiser from a suffix."""

    @pytest.mark.parametrize(
        ("suffix", "expected_type"),
        [
            (".pkl", PickleSerialiser),
            ("pkl", PickleSerialiser),
            (".npy", NumpySerialiser),
            (".npz", NpzSerialiser),
        ],
    )
    def test_builtin_suffixes(self, suffix: str, expected_type: type[object]) -> None:
        """Built-in non-tabular suffixes resolve to their dedicated serialisers."""
        assert isinstance(get_serialiser(suffix), expected_type)

    def test_tabular_suffix_falls_back_to_datafile(self) -> None:
        """An unrecognised tabular suffix resolves to the DataFile serialiser."""
        assert isinstance(get_serialiser("parquet"), DataFileSerialiser)

    def test_result_satisfies_protocol(self) -> None:
        """Every resolved serialiser satisfies the :class:`Serialiser` protocol."""
        assert isinstance(get_serialiser(".pkl"), Serialiser)


class TestPickleSerialiser:
    """Tests for :class:`PickleSerialiser` — round-trips arbitrary objects."""

    def test_round_trip(self, tmp_path: Path) -> None:
        """An object written then read back is equal to the original."""
        path = tmp_path / "obj.pkl"
        serialiser = PickleSerialiser()
        payload = {"a": [1, 2], "b": "x"}
        serialiser.write(path, obj=payload)
        assert serialiser.read(path) == payload


class TestNumpySerialisers:
    """Tests for :class:`NumpySerialiser` and :class:`NpzSerialiser`."""

    def test_npy_round_trip(self, tmp_path: Path) -> None:
        """A single array round-trips through ``.npy``."""
        path = tmp_path / "arr.npy"
        serialiser = NumpySerialiser()
        array = np.array([1, 2, 3])
        serialiser.write(path, obj=array)
        assert np.array_equal(serialiser.read(path), array)

    def test_npz_round_trip(self, tmp_path: Path) -> None:
        """A mapping of arrays round-trips through ``.npz``."""
        path = tmp_path / "arrs.npz"
        serialiser = NpzSerialiser()
        serialiser.write(path, obj={"x": np.array([1, 2]), "y": np.array([3, 4])})
        loaded = serialiser.read(path)
        assert np.array_equal(loaded["x"], np.array([1, 2]))
        assert np.array_equal(loaded["y"], np.array([3, 4]))


class TestDataFileSerialiser:
    """Tests for :class:`DataFileSerialiser` — DataFile-backed tabular formats."""

    def test_parquet_round_trip(self, tmp_path: Path) -> None:
        """A DataFrame round-trips through a parquet DataFile."""
        path = tmp_path / "frame.parquet"
        serialiser = DataFileSerialiser()
        frame = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        serialiser.write(path, obj=frame)
        assert serialiser.read(path).equals(frame)

    def test_get_datafile_dispatches_on_suffix(self, tmp_path: Path) -> None:
        """The handle resolved for a path matches the suffix's DataFile subclass."""
        serialiser = DataFileSerialiser()
        handle = serialiser.get_datafile(tmp_path / "frame.parquet")
        assert type(handle).__name__ == "Parquet"

    def test_backend_defaults_to_pandas(self) -> None:
        """With no backend supplied the serialiser uses the pandas backend."""
        assert DataFileSerialiser().backend.name == "pandas"


class TestMakeCacheStem:
    """Tests for :func:`make_cache_stem` — human-readable, parsable filename stems."""

    def test_minimal_sql_stem(self) -> None:
        """A bare SQL query yields ``<first-three-words-slug>--<hash>``."""
        stem = make_cache_stem(
            SQL("SELECT * FROM loans"),
            cache_description=None,
            ttl=None,
            jinja_kwargs={},
            cache_extra=None,
            key="abc123",
        )
        assert stem == "select_from--abc123"

    def test_path_query_uses_stem_without_suffix(self) -> None:
        """A Path query slugs its suffix-stripped path."""
        from pathlib import Path  # noqa: PLC0415

        stem = make_cache_stem(
            Path("queries/loans.sql"),
            cache_description=None,
            ttl=None,
            jinja_kwargs={},
            cache_extra=None,
            key="k",
        )
        assert stem == "queries_loans--k"

    def test_description_overrides_query(self) -> None:
        """An explicit description is slugged and used in place of the query."""
        stem = make_cache_stem(
            SQL("SELECT a FROM b"),
            cache_description="My Report",
            ttl=None,
            jinja_kwargs={},
            cache_extra=None,
            key="deadbeef",
        )
        assert stem.startswith("my_report--")
        assert stem.endswith("--deadbeef")

    def test_all_sections_present_and_ordered(self) -> None:
        """Description, kwargs, extras, TTL and hash appear in order, ``--``-joined."""
        stem = make_cache_stem(
            SQL("SELECT a FROM b"),
            cache_description="report",
            ttl=Duration(hours=6),
            jinja_kwargs={"region": "london"},
            cache_extra={"version": 2},
            key="deadbeef",
        )
        assert stem == "report--region_london--version_2--ttl_6h--deadbeef"

    def test_hash_is_always_last_section(self) -> None:
        """The hash digest is the trailing ``--`` section for uniqueness."""
        stem = make_cache_stem(
            SQL("SELECT 1"),
            cache_description=None,
            ttl=None,
            jinja_kwargs={},
            cache_extra=None,
            key="thehash",
        )
        assert stem.split("--")[-1] == "thehash"


class TestFileStoreRoundTrip:
    """Tests for :class:`FileStore` get/put round-trips with an explicit suffix."""

    def test_pickle_round_trip(self, tmp_path: Path) -> None:
        """A pickled object is written then read back unchanged."""
        store = FileStore[dict[str, int]]("fn", cache_folder=tmp_path, suffix=".pkl")
        store.put("k", value={"a": 1})
        assert store.get("k") == {"a": 1}

    def test_parquet_round_trip(self, tmp_path: Path) -> None:
        """A DataFrame is written to parquet then read back equal."""
        store = FileStore[pd.DataFrame]("fn", cache_folder=tmp_path, suffix="parquet")
        frame = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        store.put("k", value=frame)
        result = store.get("k")
        assert isinstance(result, pd.DataFrame)
        assert result.equals(frame)

    def test_npy_round_trip(self, tmp_path: Path) -> None:
        """An ndarray is written to ``.npy`` then read back equal."""
        store = FileStore[np.ndarray]("fn", cache_folder=tmp_path, suffix=".npy")
        array = np.array([1, 2, 3])
        store.put("k", value=array)
        result = store.get("k")
        assert isinstance(result, np.ndarray)
        assert np.array_equal(result, array)

    def test_miss_returns_missing(self, tmp_path: Path) -> None:
        """An absent key returns the :data:`MISSING` sentinel and counts a miss."""
        store = FileStore[dict[str, int]]("fn", cache_folder=tmp_path, suffix=".pkl")
        assert store.get("absent") is MISSING
        assert store.cache_info().misses == 1

    def test_hit_increments_counter(self, tmp_path: Path) -> None:
        """Reading a present key counts a hit."""
        store = FileStore[dict[str, int]]("fn", cache_folder=tmp_path, suffix=".pkl")
        store.put("k", value={"a": 1})
        store.get("k")
        assert store.cache_info().hits == 1


class TestFileStoreDeferredResolution:
    """Tests for :class:`FileStore` suffix inference on first :meth:`put`."""

    def test_get_before_put_is_missing(self, tmp_path: Path) -> None:
        """A lookup before any put (unresolved suffix) returns :data:`MISSING`."""
        store = FileStore[dict[str, int]]("fn", cache_folder=tmp_path)
        assert store.get("k") is MISSING

    def test_suffix_inferred_from_first_value(self, tmp_path: Path) -> None:
        """The suffix is inferred from the first stored object."""
        store = FileStore[dict[str, int]]("fn", cache_folder=tmp_path)
        store.put("k", value={"a": 1})
        assert store.suffix == ".pkl"
        assert store.get("k") == {"a": 1}

    def test_dataframe_value_infers_parquet(self, tmp_path: Path) -> None:
        """A DataFrame value defers to a parquet suffix on first put."""
        store = FileStore[pd.DataFrame]("fn", cache_folder=tmp_path)
        store.put("k", value=pd.DataFrame({"a": [1]}))
        assert store.suffix == ".parquet"

    def test_get_path_before_resolution_raises(self, tmp_path: Path) -> None:
        """Requesting a path before the suffix resolves raises :class:`RuntimeError`."""
        store = FileStore[dict[str, int]]("fn", cache_folder=tmp_path)
        with pytest.raises(expected_exception=RuntimeError, match="Suffix not resolved"):
            store.get_path("k")


class TestFileStorePaths:
    """Tests for :class:`FileStore` path layout."""

    def test_function_folder_is_named_after_function(self, tmp_path: Path) -> None:
        """The per-function folder is the function name under the cache root."""
        store = FileStore[dict[str, int]]("myfunc", cache_folder=tmp_path, suffix=".pkl")
        assert store.function_folder == tmp_path / "myfunc"

    def test_get_path_joins_key_and_suffix(self, tmp_path: Path) -> None:
        """The cache path is ``<folder>/<func>/<key><suffix>``."""
        store = FileStore[dict[str, int]]("fn", cache_folder=tmp_path, suffix=".pkl")
        assert store.get_path("abc") == tmp_path / "fn" / "abc.pkl"


class TestFileStoreStaleness:
    """Tests for mtime-based TTL staleness on :meth:`FileStore.get`."""

    def test_stale_file_is_a_miss(self, tmp_path: Path) -> None:
        """A file older than the TTL is treated as a miss."""
        store = FileStore[dict[str, int]]("fn", cache_folder=tmp_path, suffix=".pkl", ttl=Duration(seconds=-1))
        store.put("k", value={"a": 1})
        assert store.get("k") is MISSING

    def test_fresh_file_is_a_hit(self, tmp_path: Path) -> None:
        """A file within the TTL is served as a hit."""
        store = FileStore[dict[str, int]]("fn", cache_folder=tmp_path, suffix=".pkl", ttl=Duration(hours=1))
        store.put("k", value={"a": 1})
        assert store.get("k") == {"a": 1}

    def test_no_ttl_never_stale(self, tmp_path: Path) -> None:
        """With no TTL the file is always served regardless of age."""
        store = FileStore[dict[str, int]]("fn", cache_folder=tmp_path, suffix=".pkl")
        store.put("k", value={"a": 1})
        assert store.get("k") == {"a": 1}


class TestFileStoreDeleteClear:
    """Tests for :meth:`FileStore.delete` and :meth:`FileStore.clear`."""

    def test_delete_present_removes_file(self, tmp_path: Path) -> None:
        """Deleting a present key removes its file and returns ``True``."""
        store = FileStore[dict[str, int]]("fn", cache_folder=tmp_path, suffix=".pkl")
        store.put("k", value={"a": 1})
        path = store.get_path("k")
        assert store.delete("k") is True
        assert not path.is_file()

    def test_delete_absent_returns_false(self, tmp_path: Path) -> None:
        """Deleting an absent key returns ``False``."""
        store = FileStore[dict[str, int]]("fn", cache_folder=tmp_path, suffix=".pkl")
        assert store.delete("absent") is False

    def test_delete_before_resolution_returns_false(self, tmp_path: Path) -> None:
        """Deleting before the suffix resolves is a safe no-op returning ``False``."""
        store = FileStore[dict[str, int]]("fn", cache_folder=tmp_path)
        assert store.delete("k") is False

    def test_clear_removes_all_files_and_resets_counters(self, tmp_path: Path) -> None:
        """Clearing removes every cache file for the function and zeroes counters."""
        store = FileStore[dict[str, int]]("fn", cache_folder=tmp_path, suffix=".pkl")
        store.put("a", value={"v": 1})
        store.put("b", value={"v": 2})
        store.get("a")  # a hit, so counters are non-zero
        store.clear()
        info = store.cache_info()
        assert info.currsize == 0
        assert info.hits == 0
        assert info.misses == 0
        assert not list(store.function_folder.glob("*.pkl"))

    def test_cache_info_counts_files_on_disk(self, tmp_path: Path) -> None:
        """``currsize`` counts the on-disk files matching the suffix."""
        store = FileStore[dict[str, int]]("fn", cache_folder=tmp_path, suffix=".pkl")
        store.put("a", value={"v": 1})
        store.put("b", value={"v": 2})
        assert store.cache_info().currsize == 2  # noqa: PLR2004
