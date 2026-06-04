"""Tests for ``mayutils.objects.paths``."""

from __future__ import annotations

from pathlib import Path

import pytest

from mayutils.objects.paths import is_pathlike, resolve_save_path


class TestIsPathlike:
    """Tests for :func:`is_pathlike` — classifies a string as a path vs. a bare name."""

    @pytest.mark.parametrize(
        "path",
        [
            "/data/output.csv",  # absolute
            "/etc",  # absolute, no suffix
            "sub/file",  # relative with separator
            "a/b/c",  # multi-part relative
            "data.csv",  # bare name with suffix
            "report.json",  # bare name with suffix
            ".",  # special token
            "..",  # special token
        ],
    )
    def test_pathlike(self, path: str) -> None:
        """Absolute paths, multi-part paths, suffixed names, and ``.``/``..`` are path-like."""
        assert is_pathlike(path) is True

    @pytest.mark.parametrize(
        "path",
        [
            "report",  # bare stem, no suffix
            "",  # empty string
            "myfile",  # bare stem, no suffix
        ],
    )
    def test_not_pathlike(self, path: str) -> None:
        """Bare filename stems (and the empty string) are not path-like."""
        assert is_pathlike(path) is False


class TestResolveSavePath:
    """Tests for :func:`resolve_save_path` — resolves a save location into a stem and suffix set."""

    def test_none_uses_defaults(self, tmp_path: Path) -> None:
        """``None`` resolves to ``default_directory / default_name`` with the default suffix."""
        stem, suffixes = resolve_save_path(
            None,
            default_directory=tmp_path,
            default_name="out",
            default_suffix="csv",
        )
        assert stem == tmp_path / "out"
        assert suffixes == {"csv"}

    def test_bare_name_joined_to_default_directory(self, tmp_path: Path) -> None:
        """A bare-name string is placed under ``default_directory``."""
        stem, suffixes = resolve_save_path(
            "myfile",
            default_directory=tmp_path,
            default_name="out",
            default_suffix="csv",
        )
        assert stem == tmp_path / "myfile"
        assert suffixes == {"csv"}

    def test_pathlike_string_used_as_is(self, tmp_path: Path) -> None:
        """A path-like string is used as-is and ignores ``default_directory``.

        The suffix is stripped from the stem and folded into the suffix set.
        """
        stem, suffixes = resolve_save_path(
            "sub/file.txt",
            default_directory=tmp_path,
            default_name="out",
            default_suffix="csv",
        )
        assert stem == Path("sub/file")
        assert suffixes == {"txt"}

    def test_path_object_used_as_is(self, tmp_path: Path) -> None:
        """A ``Path`` input is used directly regardless of whether it looks path-like."""
        stem, suffixes = resolve_save_path(
            tmp_path / "report.json",
            default_directory=tmp_path,
            default_name="out",
            default_suffix="csv",
        )
        assert stem == tmp_path / "report"
        assert suffixes == {"json"}

    def test_bare_name_path_object_not_joined(self, tmp_path: Path) -> None:
        """A bare-name ``Path`` is *not* joined to ``default_directory`` (unlike a bare string)."""
        stem, suffixes = resolve_save_path(
            Path("report"),
            default_directory=tmp_path,
            default_name="out",
            default_suffix="csv",
        )
        assert stem == Path("report")
        assert suffixes == {"csv"}

    def test_suffix_inferred_from_path(self, tmp_path: Path) -> None:
        """An explicit suffix on the input is inferred and added to the suffix set."""
        stem, suffixes = resolve_save_path(
            tmp_path / "data.parquet",
            default_directory=tmp_path,
            default_name="out",
            default_suffix="csv",
        )
        assert stem == tmp_path / "data"
        assert suffixes == {"parquet"}

    def test_suffixes_normalised(self, tmp_path: Path) -> None:
        """Provided ``suffixes`` are lower-cased and stripped of a leading dot."""
        _, suffixes = resolve_save_path(
            "bare",
            suffixes=(".CSV", "Json", "PARQUET"),
            default_directory=tmp_path,
            default_name="out",
            default_suffix="csv",
        )
        assert suffixes == {"csv", "json", "parquet"}

    def test_suffixes_merged_with_inferred(self, tmp_path: Path) -> None:
        """An inferred suffix is unioned with the normalised ``suffixes`` set."""
        _, suffixes = resolve_save_path(
            tmp_path / "foo.PARQUET",
            suffixes=(".CSV", "Json"),
            default_directory=tmp_path,
            default_name="out",
            default_suffix="csv",
        )
        assert suffixes == {"csv", "json", "parquet"}

    def test_default_suffix_fallback(self, tmp_path: Path) -> None:
        """``default_suffix`` is used (normalised) when no other suffix is available."""
        _, suffixes = resolve_save_path(
            "bare",
            default_directory=tmp_path,
            default_name="out",
            default_suffix=".PnG",
        )
        assert suffixes == {"png"}

    def test_provided_suffixes_take_priority_over_default(self, tmp_path: Path) -> None:
        """When ``suffixes`` is non-empty, ``default_suffix`` is not added."""
        _, suffixes = resolve_save_path(
            "bare",
            suffixes=("json",),
            default_directory=tmp_path,
            default_name="out",
            default_suffix="csv",
        )
        assert suffixes == {"json"}

    def test_directory_input_appends_default_name(self, tmp_path: Path) -> None:
        """An existing-directory ``Path`` input gets ``default_name`` appended."""
        subdir = tmp_path / "adir"
        subdir.mkdir()
        stem, suffixes = resolve_save_path(
            subdir,
            default_directory=tmp_path,
            default_name="out",
            default_suffix="csv",
        )
        assert stem == subdir / "out"
        assert suffixes == {"csv"}

    def test_directory_input_as_string_appends_default_name(self, tmp_path: Path) -> None:
        """An existing-directory absolute string is treated the same as a directory ``Path``."""
        subdir = tmp_path / "adir"
        subdir.mkdir()
        stem, suffixes = resolve_save_path(
            str(subdir),
            default_directory=tmp_path,
            default_name="out",
            default_suffix="csv",
        )
        assert stem == subdir / "out"
        assert suffixes == {"csv"}

    def test_returned_suffix_set_contents(self, tmp_path: Path) -> None:
        """The returned object is a ``set`` and the stem is a ``Path``."""
        stem, suffixes = resolve_save_path(
            None,
            default_directory=tmp_path,
            default_name="out",
            default_suffix="csv",
        )
        assert isinstance(stem, Path)
        assert isinstance(suffixes, set)

    def test_overwrite_false_existing_raises(self, tmp_path: Path) -> None:
        """With ``overwrite=False`` an existing candidate file raises ``FileExistsError``."""
        (tmp_path / "report.csv").write_text("data", encoding="utf-8")
        with pytest.raises(FileExistsError, match=r"report\.csv"):
            resolve_save_path(
                "report",
                overwrite=False,
                default_directory=tmp_path,
                default_name="out",
                default_suffix="csv",
            )

    def test_overwrite_false_existing_absolute_path_raises(self, tmp_path: Path) -> None:
        """An absolute ``Path`` to an existing file raises when ``overwrite=False``."""
        (tmp_path / "data.csv").write_text("data", encoding="utf-8")
        with pytest.raises(FileExistsError):
            resolve_save_path(
                tmp_path / "data.csv",
                overwrite=False,
                default_directory=tmp_path,
                default_name="out",
                default_suffix="csv",
            )

    def test_overwrite_false_missing_file_ok(self, tmp_path: Path) -> None:
        """With ``overwrite=False`` a non-existent candidate resolves without raising."""
        stem, suffixes = resolve_save_path(
            "report",
            overwrite=False,
            default_directory=tmp_path,
            default_name="out",
            default_suffix="csv",
        )
        assert stem == tmp_path / "report"
        assert suffixes == {"csv"}

    def test_overwrite_true_existing_ok(self, tmp_path: Path) -> None:
        """With ``overwrite=True`` (the default) an existing file does not raise."""
        (tmp_path / "report.csv").write_text("data", encoding="utf-8")
        stem, suffixes = resolve_save_path(
            "report",
            overwrite=True,
            default_directory=tmp_path,
            default_name="out",
            default_suffix="csv",
        )
        assert stem == tmp_path / "report"
        assert suffixes == {"csv"}

    def test_overwrite_false_checks_every_suffix(self, tmp_path: Path) -> None:
        """``overwrite=False`` raises if *any* candidate suffix already exists on disk."""
        (tmp_path / "report.json").write_text("data", encoding="utf-8")
        with pytest.raises(FileExistsError, match=r"report\.json"):
            resolve_save_path(
                "report",
                suffixes=("csv", "json"),
                overwrite=False,
                default_directory=tmp_path,
                default_name="out",
                default_suffix="csv",
            )
