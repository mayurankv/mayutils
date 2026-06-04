"""Tests for ``mayutils.objects.dataframes.pandas.dataframes``.

Covers the data-transforming methods on :class:`DataframeUtilsAccessor`
(``max_abs``, ``rename_index``, ``cutoff``, ``map_dtypes``, ``slice_interval``,
``ground`` and ``save``) across wide-normal, edge and error cases. The accessor
is constructed directly (rather than via the registered ``df.utils`` namespace)
so the tests are independent of global accessor registration.

The known dead-datetime branch in ``map_dtypes`` (``get_args`` returns ``()``
for the PEP 695 ``DatetimeKind`` alias, so any ``"datetime"``/``"date"``/
``"time"`` spec falls through to ``astype`` and raises) is pinned, not fixed.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import pytest

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping
    from pathlib import Path

    import pandas as pd
else:
    pd = pytest.importorskip("pandas")

from mayutils.objects.dataframes import setup_pandas
from mayutils.objects.dataframes.pandas.dataframes import (
    DataframeUtilsAccessor,
    DtypeSpec,
)
from mayutils.objects.dataframes.pandas.stylers import Styler
from mayutils.objects.datetime import Date, DateTime, Interval


def datetime_index(*days: int) -> pd.Index:
    """Return an object-dtype index of ``datetime.datetime`` values in Jan 2024.

    An object dtype is used so ``inferred_type`` reports ``"datetime"`` (a
    native ``DatetimeIndex`` would instead report ``"datetime64"``, which the
    accessor also dispatches on — see ``test_native_datetimeindex_slices``).

    Parameters
    ----------
    days
        Day-of-month values for the January-2024 timestamps to build.

    Returns
    -------
        An object-dtype index of timestamps.
    """
    return pd.Index([DateTime(2024, 1, day) for day in days], dtype=object)


def date_index(*days: int) -> pd.Index:
    """Return an object-dtype index of ``datetime.date`` values in Jan 2024.

    Parameters
    ----------
    days
        Day-of-month values for the January-2024 dates to build.

    Returns
    -------
        An object-dtype index whose ``inferred_type`` is ``"date"``.
    """
    return pd.Index([Date(2024, 1, day) for day in days], dtype=object)


def dtype_mapper(**specs: object) -> Mapping[Hashable, DtypeSpec]:
    """Build a typed ``map_dtypes`` mapper from loosely-typed column specs.

    The declared ``DtypeSpec`` alias only models numpy/extension dtypes and the
    documented literals, yet ``map_dtypes`` also forwards bare Python types
    (``float``) and arbitrary dtype strings (``"Int64"``) to ``astype`` at
    runtime. This helper localises the single cast that bridges that documented
    breadth so each call site stays a plain literal mapping.

    Parameters
    ----------
    specs
        Column-name to dtype-spec pairs, accepted as ``object`` so type and
        string specs can be mixed freely.

    Returns
    -------
        The same mapping typed as ``Mapping[Hashable, DtypeSpec]``.
    """
    return cast("Mapping[Hashable, DtypeSpec]", specs)


class TestRegistration:
    """Tests for the ``.utils`` accessor registration via ``setup_pandas``."""

    def test_setup_registers_accessors(self) -> None:
        """``setup_pandas`` attaches the dynamic ``.utils`` namespace to all three types.

        ``setup_pandas`` is idempotent and pandas emits a ``UserWarning`` when an
        accessor name is re-registered, so the (expected) override warning is
        suppressed here rather than treated as a failure.
        """
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="registration of accessor", category=UserWarning)
            setup_pandas()
        assert hasattr(pd.DataFrame({"a": [1]}), "utils")
        assert hasattr(pd.Series([1]), "utils")
        assert hasattr(pd.Index([1]), "utils")


class TestInit:
    """Tests for :meth:`DataframeUtilsAccessor.__init__`."""

    def test_binds_frame_by_reference(self) -> None:
        """The supplied frame is stored verbatim without copying."""
        frame = pd.DataFrame({"a": [1, 2, 3]})
        assert DataframeUtilsAccessor(df=frame).df is frame


class TestMaxAbs:
    """Tests for :meth:`DataframeUtilsAccessor.max_abs` — furthest deviation."""

    def test_two_sided(self) -> None:
        """The largest absolute deviation from zero is returned."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"a": [1.0, -2.0, 3.0]}))
        assert np.isclose(accessor.max_abs(0.0), 3.0)

    def test_default_reference_is_zero(self) -> None:
        """Omitting the reference value measures deviation from zero."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"a": [1.0, -4.0, 2.0]}))
        assert np.isclose(accessor.max_abs(), 4.0)

    def test_reference_shift(self) -> None:
        """A non-zero reference re-centres the deviation calculation."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"a": [5.0, 6.0, 7.0]}))
        assert np.isclose(accessor.max_abs(5.0), 2.0)

    def test_one_sided_positive(self) -> None:
        """All-positive deviations clip the negative side at zero."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"a": [1.0, 2.0, 3.0]}))
        assert np.isclose(accessor.max_abs(0.0), 3.0)

    def test_one_sided_negative(self) -> None:
        """All values below the reference yield the furthest negative gap."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"a": [1.0, 2.0, 3.0]}))
        assert np.isclose(accessor.max_abs(10.0), 9.0)

    def test_columns_subset(self) -> None:
        """Only the selected columns contribute to the maximum."""
        accessor = DataframeUtilsAccessor(
            df=pd.DataFrame({"a": [1.0, -2.0, 3.0], "b": [10.0, 0.0, 0.0]}),
        )
        assert np.isclose(accessor.max_abs(0.0, columns=["a"]), 3.0)

    def test_all_columns_when_none(self) -> None:
        """Passing ``None`` columns considers the whole frame."""
        accessor = DataframeUtilsAccessor(
            df=pd.DataFrame({"a": [1.0, -2.0, 3.0], "b": [10.0, 0.0, 0.0]}),
        )
        assert np.isclose(accessor.max_abs(0.0), 10.0)

    def test_single_row(self) -> None:
        """A single-row frame returns that row's absolute deviation."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"a": [-7.0]}))
        assert np.isclose(accessor.max_abs(0.0), 7.0)

    def test_constant_equals_reference_raises(self) -> None:
        """A frame constant at the reference value has no scale and raises."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"a": [2.0, 2.0, 2.0]}))
        with pytest.raises(expected_exception=ValueError, match=r"constant equal to 2\.0"):
            accessor.max_abs(2.0)


class TestRenameIndex:
    """Tests for :meth:`DataframeUtilsAccessor.rename_index`."""

    def test_sets_index_name(self) -> None:
        """The index name is updated to the supplied label."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"x": [1, 2]}))
        assert accessor.rename_index("row_id").index.name == "row_id"

    def test_returns_same_frame(self) -> None:
        """The bound frame itself is returned for chaining."""
        frame = pd.DataFrame({"x": [1, 2]})
        accessor = DataframeUtilsAccessor(df=frame)
        assert accessor.rename_index("row_id") is frame

    def test_overwrites_existing_name(self) -> None:
        """An existing index name is replaced."""
        frame = pd.DataFrame({"x": [1, 2]})
        frame.index.name = "old"
        assert DataframeUtilsAccessor(df=frame).rename_index("new").index.name == "new"


class TestCutoff:
    """Tests for :meth:`DataframeUtilsAccessor.cutoff` — tail bucketing."""

    def test_default_sum_aggregation(self) -> None:
        """Rows at/above the cutoff are summed into a single ``<cutoff>+`` bucket."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"n": [1, 2, 3, 4]}, index=[0, 1, 2, 3]))
        result = accessor.cutoff(2)
        assert result.index.tolist() == ["0", "1", "2+"]
        assert result["n"].tolist() == [1.0, 2.0, 7.0]

    def test_mean_aggregation(self) -> None:
        """A custom aggregation replaces the default sum for the tail bucket."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"n": [1, 2, 3, 4]}, index=[0, 1, 2, 3]))
        result = accessor.cutoff(2, aggregation=lambda frame: frame.mean())
        assert result["n"].tolist() == [1.0, 2.0, 3.5]

    def test_none_aggregation_truncates(self) -> None:
        """``aggregation=None`` drops the tail entirely and keeps the int index."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"n": [1, 2, 3, 4]}, index=[0, 1, 2, 3]))
        result = accessor.cutoff(2, aggregation=None)
        assert result.index.tolist() == [0, 1]
        assert result["n"].tolist() == [1, 2]

    def test_does_not_mutate_source(self) -> None:
        """The head slice is copied, leaving the caller's frame untouched."""
        frame = pd.DataFrame({"n": [1, 2, 3, 4]}, index=[0, 1, 2, 3])
        DataframeUtilsAccessor(df=frame).cutoff(2)
        assert frame.index.tolist() == [0, 1, 2, 3]

    def test_bucket_sorts_after_higher_singletons(self) -> None:
        """The aggregated bucket sorts numerically after two-digit singletons."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"n": list(range(12))}, index=list(range(12))))
        result = accessor.cutoff(10)
        assert result.index.tolist() == ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10+"]
        assert result["n"].tolist()[-1] == sum(range(10, 12))

    def test_cutoff_above_all_keeps_everything(self) -> None:
        """A cutoff above every index value sums an empty tail to a zero bucket."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"n": [1, 2, 3]}, index=[0, 1, 2]))
        result = accessor.cutoff(10)
        assert result.index.tolist() == ["0", "1", "2", "10+"]
        assert result["n"].tolist()[-1] == 0.0


class TestMapDtypes:
    """Tests for :meth:`DataframeUtilsAccessor.map_dtypes` — column dtype coercion."""

    def test_numeric_spec(self) -> None:
        """``"numeric"`` coerces a string column to an integer dtype."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"n": ["1", "2", "3"]}))
        accessor.map_dtypes(dtype_mapper(n="numeric"))
        assert accessor.df["n"].tolist() == [1, 2, 3]
        assert accessor.df["n"].dtype == np.dtype("int64")

    def test_float_type_spec(self) -> None:
        """A Python ``float`` type forwards to ``astype`` for float coercion."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"f": ["1.5", "2.5"]}))
        accessor.map_dtypes(dtype_mapper(f=float))
        assert accessor.df["f"].tolist() == [1.5, 2.5]
        assert accessor.df["f"].dtype == np.dtype("float64")

    def test_nullable_int_string_spec(self) -> None:
        """A pandas dtype string such as ``"Int64"`` is honoured."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"n": ["1", "2"]}))
        accessor.map_dtypes(dtype_mapper(n="Int64"))
        assert str(accessor.df["n"].dtype) == "Int64"
        assert accessor.df["n"].tolist() == [1, 2]

    def test_category_spec(self) -> None:
        """A ``"category"`` spec converts the column to a categorical dtype."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"c": ["a", "b", "a"]}))
        accessor.map_dtypes(dtype_mapper(c="category"))
        assert str(accessor.df["c"].dtype) == "category"

    def test_multiple_columns(self) -> None:
        """Several columns are coerced in a single call."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"n": ["1", "2"], "f": ["1.5", "2.5"]}))
        accessor.map_dtypes(dtype_mapper(n="numeric", f=float))
        assert accessor.df["n"].tolist() == [1, 2]
        assert accessor.df["f"].tolist() == [1.5, 2.5]

    def test_returns_bound_frame(self) -> None:
        """The bound frame is returned to permit chaining."""
        frame = pd.DataFrame({"n": ["1", "2"]})
        accessor = DataframeUtilsAccessor(df=frame)
        assert accessor.map_dtypes(dtype_mapper(n="numeric")) is frame

    def test_unparseable_numeric_raises(self) -> None:
        """A non-numeric value rewraps the underlying error as ``TypeError``."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"n": ["1", "x", "3"]}))
        with pytest.raises(expected_exception=TypeError, match="Error parsing dtype numeric for columns n"):
            accessor.map_dtypes(dtype_mapper(n="numeric"))

    def test_missing_column_raises(self) -> None:
        """A missing column lookup is rewrapped as ``TypeError``."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"a": [1]}))
        with pytest.raises(expected_exception=TypeError, match="Error parsing dtype numeric for columns missing"):
            accessor.map_dtypes(dtype_mapper(missing="numeric"))

    def test_invalid_dtype_string_raises(self) -> None:
        """An unrecognised dtype string is rewrapped as ``TypeError``."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"a": [1]}))
        with pytest.raises(expected_exception=TypeError, match="Error parsing dtype not_a_dtype for columns a"):
            accessor.map_dtypes(dtype_mapper(a="not_a_dtype"))

    def test_date_spec_converts_to_dates(self) -> None:
        """A ``"date"`` spec routes through the datetime branch and yields ``date`` values."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"d": ["2024-01-01", "2024-01-02"]}))
        result = accessor.map_dtypes(dtype_mapper(d="date"), date_format="%Y-%m-%d")
        assert [str(value) for value in result["d"].tolist()] == ["2024-01-01", "2024-01-02"]

    def test_datetime_spec_converts_to_timestamps(self) -> None:
        """A ``"datetime"`` spec parses to a ``datetime64`` column."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"d": ["2024-01-01", "2024-01-02"]}))
        result = accessor.map_dtypes(dtype_mapper(d="datetime"), datetime_format="%Y-%m-%d")
        assert result["d"].dtype.kind == "M"

    def test_time_spec_converts_to_times(self) -> None:
        """A ``"time"`` spec narrows to ``time`` values."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"d": ["2024-01-01 13:30:00", "2024-01-02 00:00:00"]}))
        result = accessor.map_dtypes(dtype_mapper(d="time"), time_format="%Y-%m-%d %H:%M:%S")
        assert str(result["d"].tolist()[0]) == "13:30:00"


class TestSliceInterval:
    """Tests for :meth:`DataframeUtilsAccessor.slice_interval` — index-window slicing."""

    def test_datetime_index(self) -> None:
        """A datetime-indexed frame is restricted to rows inside the window."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"v": [1, 2, 3]}, index=datetime_index(1, 2, 3)))
        window = Interval[DateTime](start=DateTime(2024, 1, 1), end=DateTime(2024, 1, 2))
        assert accessor.slice_interval(window)["v"].tolist() == [1, 2]

    def test_date_index(self) -> None:
        """A date-indexed frame slices via the date-narrowed interval."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"v": [1, 2, 3]}, index=date_index(1, 2, 3)))
        window = Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 2))
        assert accessor.slice_interval(window)["v"].tolist() == [1, 2]

    def test_full_window_keeps_all(self) -> None:
        """A window spanning the whole index keeps every row."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"v": [1, 2, 3]}, index=datetime_index(1, 2, 3)))
        window = Interval[DateTime](start=DateTime(2024, 1, 1), end=DateTime(2024, 1, 3))
        assert accessor.slice_interval(window)["v"].tolist() == [1, 2, 3]

    def test_native_datetimeindex_slices(self) -> None:
        """A native ``DatetimeIndex`` (``inferred_type`` ``datetime64``) slices like a datetime index."""
        frame = pd.DataFrame({"v": [1, 2, 3]}, index=pd.date_range("2024-01-01", periods=3, freq="D"))
        accessor = DataframeUtilsAccessor(df=frame)
        window = Interval[DateTime](start=DateTime(2024, 1, 1), end=DateTime(2024, 1, 2))
        assert accessor.slice_interval(window)["v"].tolist() == [1, 2]

    def test_non_temporal_index_raises(self) -> None:
        """An integer index cannot be interval-sliced and raises ``TypeError``."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"v": [1, 2, 3]}))
        window = Interval[DateTime](start=DateTime(2024, 1, 1), end=DateTime(2024, 1, 2))
        with pytest.raises(expected_exception=TypeError, match="must be datetime or date type"):
            accessor.slice_interval(window)


class TestGround:
    """Tests for :meth:`DataframeUtilsAccessor.ground` — interval grounding stub."""

    def test_none_returns_frame_unchanged(self) -> None:
        """A ``None`` interval is a no-op returning the bound frame."""
        frame = pd.DataFrame({"v": [1.0, 2.0, 3.0]})
        assert DataframeUtilsAccessor(df=frame).ground(None) is frame

    def test_concrete_interval_not_implemented(self) -> None:
        """A concrete interval raises until DataFrame grounding lands."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"v": [1.0, 2.0, 3.0]}))
        window = Interval(start=Date(2024, 1, 1), end=Date(2024, 1, 2))
        with pytest.raises(expected_exception=NotImplementedError, match="not implemented for DataFrames"):
            accessor.ground(window)


class TestSave:
    """Tests for :meth:`DataframeUtilsAccessor.save` — suffix-dispatched persistence."""

    def test_csv_roundtrip_with_index(self, tmp_path: Path) -> None:
        """A CSV write retains the index and round-trips the values."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"a": [1, 2], "b": [3, 4]}))
        out = accessor.save(tmp_path / "out.csv")
        assert out == tmp_path / "out.csv"
        assert out.exists()
        assert pd.read_csv(out, index_col=0)["a"].tolist() == [1, 2]

    def test_csv_index_false_override(self, tmp_path: Path) -> None:
        """A caller ``index=False`` kwarg overrides the index-retaining default."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"a": [1, 2], "b": [3, 4]}))
        accessor.save(tmp_path / "out.csv", index=False)
        assert pd.read_csv(tmp_path / "out.csv").columns.tolist() == ["a", "b"]

    def test_parquet_roundtrip_preserves_index(self, tmp_path: Path) -> None:
        """A parquet write preserves both values and the row index."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"a": [1, 2]}, index=[10, 11]))
        out = accessor.save(tmp_path / "out.parquet")
        restored = pd.read_parquet(out)
        assert restored["a"].tolist() == [1, 2]
        assert restored.index.tolist() == [10, 11]

    def test_xlsx_roundtrip(self, tmp_path: Path) -> None:
        """An xlsx write produces a readable workbook carrying the column data."""
        openpyxl = pytest.importorskip("openpyxl")
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"a": [1, 2]}))
        out = accessor.save(tmp_path / "out.xlsx")
        assert out.exists()
        worksheet = openpyxl.load_workbook(out).active
        assert worksheet is not None
        rows = list(worksheet.iter_rows(values_only=True))
        assert rows[0][-1] == "a"
        assert [row[-1] for row in rows[1:]] == [1, 2]

    def test_feather_not_implemented(self, tmp_path: Path) -> None:
        """The disabled ``.feather`` backend raises ``NotImplementedError``."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"a": [1, 2]}))
        with pytest.raises(expected_exception=NotImplementedError, match="Feather not implemented"):
            accessor.save(tmp_path / "out.feather")

    def test_unsupported_suffix_raises(self, tmp_path: Path) -> None:
        """An unknown suffix is rejected with ``NotImplementedError``."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"a": [1, 2]}))
        with pytest.raises(expected_exception=NotImplementedError, match="unsupported format"):
            accessor.save(tmp_path / "out.txt")

    def test_accepts_str_path(self, tmp_path: Path) -> None:
        """A string path is coerced to ``Path`` and returned as such."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"a": [1, 2]}))
        out = accessor.save(str(tmp_path / "out.csv"))
        assert out == tmp_path / "out.csv"


class TestStylerProperty:
    """Tests for :attr:`DataframeUtilsAccessor.styler` — fresh styler per access."""

    def test_returns_styler(self) -> None:
        """The property returns a :class:`Styler` bound to the frame."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"a": [1, 2]}))
        assert isinstance(accessor.styler, Styler)

    def test_fresh_instance_per_access(self) -> None:
        """Each access constructs an independent styler."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"a": [1, 2]}))
        assert accessor.styler is not accessor.styler


class TestChangeMap:
    """Tests for :meth:`DataframeUtilsAccessor.change_map` — diverging heatmap."""

    def test_returns_styler(self) -> None:
        """A diverging-heatmap styler is produced for a two-sided frame."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"delta": [-0.4, 0.2, 0.5]}))
        assert isinstance(accessor.change_map(0.0), Styler)

    def test_constant_frame_raises_via_max_abs(self) -> None:
        """A constant frame has no symmetric bound, so ``max_abs`` raises."""
        accessor = DataframeUtilsAccessor(df=pd.DataFrame({"delta": [0.0, 0.0, 0.0]}))
        with pytest.raises(expected_exception=ValueError, match=r"constant equal to 0\.0"):
            accessor.change_map(0.0)


def test_dtype_spec_alias_accepts_documented_values() -> None:
    """``map_dtypes`` admits both literal and type specs in one mapper."""
    accessor = DataframeUtilsAccessor(df=pd.DataFrame({"n": ["1"], "f": ["1.5"]}))
    assert accessor.map_dtypes(dtype_mapper(n="numeric", f=float)) is accessor.df


def test_save_forwards_kwargs_to_writer(tmp_path: Path) -> None:
    """Extra ``**kwargs`` reach the underlying pandas writer."""
    accessor = DataframeUtilsAccessor(df=pd.DataFrame({"a": [1, 2], "b": [3, 4]}))
    extra: dict[str, Any] = {"index": False, "header": False}
    accessor.save(tmp_path / "out.csv", **extra)
    assert pd.read_csv(tmp_path / "out.csv", header=None).shape == (2, 2)
