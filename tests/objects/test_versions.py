"""Tests for ``mayutils.objects.versions``.

``packaging`` is treated as an optional dependency by
:mod:`mayutils.objects.versions`, so the tests skip at collection time
when it is not importable.
"""

from __future__ import annotations

import importlib
import sys
import types
from typing import TYPE_CHECKING

import numpy as np
import pytest

if TYPE_CHECKING:
    from pathlib import Path

from mayutils.objects.versions import (
    VersionedModule,
    apply_func_to_versioned_value,
    discover_versioned_modules,
    resolve_module_version_index,
    resolve_version_indices,
    resolve_versions,
)

packaging_version = pytest.importorskip("packaging.version")
Version = packaging_version.Version

from mayutils.objects.versions import bump_version_string  # noqa: E402


class TestBumpVersionString:
    """Tests for :func:`bump_version_string` — advance a semantic version."""

    @pytest.mark.parametrize(
        ("version", "bump", "expected"),
        [
            ("1.2.3", "patch", "1.2.4"),
            ("1.2.3", "minor", "1.3.0"),
            ("1.2.3", "major", "2.0.0"),
            ("0.0.0", "patch", "0.0.1"),
            ("0.0.0", "minor", "0.1.0"),
            ("0.0.0", "major", "1.0.0"),
        ],
    )
    def test_bump_from_string(self, version: str, bump: str, expected: str) -> None:
        """Every component can be bumped from a string representation."""
        assert str(bump_version_string(version, bump=bump)) == expected

    def test_returns_version_instance(self) -> None:
        """The return value is a :class:`packaging.version.Version`."""
        assert isinstance(bump_version_string("1.0.0", bump="patch"), Version)

    def test_accepts_version_instance(self) -> None:
        """A pre-parsed :class:`Version` is used without re-parsing."""
        assert str(bump_version_string(Version("2.5.9"), bump="patch")) == "2.5.10"

    def test_minor_bump_resets_patch(self) -> None:
        """Bumping the minor component zeroes the patch."""
        assert str(bump_version_string("1.4.7", bump="minor")) == "1.5.0"

    def test_major_bump_resets_minor_and_patch(self) -> None:
        """Bumping the major component zeroes both minor and patch."""
        assert str(bump_version_string("3.4.5", bump="major")) == "4.0.0"

    def test_unknown_bump_raises(self) -> None:
        """An unrecognised bump component surfaces :class:`ValueError`."""
        with pytest.raises(expected_exception=ValueError, match="Unknown part to bump"):
            bump_version_string("1.0.0", bump="build")


class TestResolveModuleVersionIndex:
    """Tests for :func:`resolve_module_version_index` — per-element version index."""

    TIMESTAMPS = np.array(
        ["2026-01-01", "2026-02-01", "2026-03-01"],
        dtype="datetime64[us]",
    )

    def test_timestamp_before_all_versions_clips_to_first(self) -> None:
        """A timestamp before all versions clips to index 0."""
        indices = resolve_module_version_index(
            implemented_timestamps=self.TIMESTAMPS,
            timestamps=np.array(["2025-06-01"], dtype="datetime64[us]"),
        )
        assert indices[0] == 0

    def test_timestamp_after_all_versions_clips_to_last(self) -> None:
        """A timestamp after all versions clips to the last index."""
        last_index = len(self.TIMESTAMPS) - 1
        indices = resolve_module_version_index(
            implemented_timestamps=self.TIMESTAMPS,
            timestamps=np.array(["2027-01-01"], dtype="datetime64[us]"),
        )
        assert indices[0] == last_index

    def test_timestamp_exactly_on_boundary_picks_that_version(self) -> None:
        """A timestamp exactly on a boundary selects that version."""
        indices = resolve_module_version_index(
            implemented_timestamps=self.TIMESTAMPS,
            timestamps=np.array(["2026-02-01"], dtype="datetime64[us]"),
        )
        assert indices[0] == 1

    def test_timestamp_between_versions_picks_earlier(self) -> None:
        """A timestamp between two versions selects the earlier one."""
        indices = resolve_module_version_index(
            implemented_timestamps=self.TIMESTAMPS,
            timestamps=np.array(["2026-02-15"], dtype="datetime64[us]"),
        )
        assert indices[0] == 1

    def test_vectorised_over_mixed_timestamps(self) -> None:
        """Multiple timestamps are resolved in one vectorised call."""
        indices = resolve_module_version_index(
            implemented_timestamps=self.TIMESTAMPS,
            timestamps=np.array(
                ["2025-06-01", "2026-01-15", "2026-02-15", "2027-01-01"],
                dtype="datetime64[us]",
            ),
        )
        assert (indices == np.array([0, 0, 1, 2])).all()


class TestResolveVersionIndices:
    """Tests for :func:`resolve_version_indices` — index into sorted config dates."""

    def test_resolves_against_sorted_config_dates(self) -> None:
        """Unsorted dict keys are sorted by date before resolving."""
        version_values = {
            np.datetime64("2026-02-01"): "second",
            np.datetime64("2026-01-01"): "first",
        }
        indices = resolve_version_indices(
            version_values=version_values,
            timestamps=np.array(
                ["2026-01-15", "2026-03-01"],
                dtype="datetime64[us]",
            ),
        )
        assert (indices == np.array([0, 1])).all()


class TestApplyFuncToVersionedValue:
    """Tests for :func:`apply_func_to_versioned_value` — versioned parameter dispatch."""

    def test_applies_time_appropriate_parameter(self) -> None:
        """Each element uses the parameter active at its timestamp."""
        versioned_value = {
            np.datetime64("2026-01-01"): 10,
            np.datetime64("2026-02-01"): 100,
        }
        result = apply_func_to_versioned_value(
            array=np.array([1, 2, 3]),
            timestamps=np.array(
                ["2026-01-15", "2026-01-20", "2026-02-15"],
                dtype="datetime64[us]",
            ),
            versioned_value=versioned_value,
            func=lambda array, version_value: array * version_value,
            dtype=np.int64,
        )
        assert (result == np.array([10, 20, 300])).all()

    def test_unsorted_config_dict_resolved_by_date(self) -> None:
        """Insertion-order of the config dict does not affect resolution."""
        versioned_value = {
            np.datetime64("2026-02-01"): 100,
            np.datetime64("2026-01-01"): 10,
        }
        result = apply_func_to_versioned_value(
            array=np.array([1, 2]),
            timestamps=np.array(
                ["2026-01-15", "2026-02-15"],
                dtype="datetime64[us]",
            ),
            versioned_value=versioned_value,
            func=lambda array, version_value: array * version_value,
            dtype=np.int64,
        )
        assert (result == np.array([10, 200])).all()


class TestDiscoverVersionedModules:
    """Tests for :func:`discover_versioned_modules` — scan v*/ directories."""

    @pytest.fixture
    def plugin_package(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
        """
        Create an importable package with v0/ and v1/ module dirs.

        Returns
        -------
        str
            The dotted module prefix of the temporary package.
        """
        package = tmp_path / "fake_plugins"
        for version, implemented in [("v0", "2026-01-01"), ("v1", "2026-03-01")]:
            version_dir = package / version
            version_dir.mkdir(parents=True)
            (version_dir / "__init__.py").write_text("")
            (version_dir / "plugin.py").write_text(
                f'__implemented__ = "{implemented} 00:00:00"\n',
            )
        (package / "__init__.py").write_text("")
        monkeypatch.setattr(sys, "path", [str(tmp_path), *sys.path])
        importlib.invalidate_caches()
        return "fake_plugins"

    def test_discovers_versions_sorted_by_timestamp(
        self,
        plugin_package: str,
        tmp_path: Path,
    ) -> None:
        """Discovered modules are returned sorted by implemented timestamp."""
        versions = discover_versioned_modules(
            directory=tmp_path / "fake_plugins",
            module_prefix=plugin_package,
            module_filename="plugin.py",
        )
        assert versions is not None
        assert [v.version for v in versions] == [0, 1]
        assert versions[0].implemented_timestamp == np.datetime64("2026-01-01 00:00:00")

    def test_missing_directory_returns_none(self, tmp_path: Path) -> None:
        """A non-existent directory returns ``None``."""
        result = discover_versioned_modules(
            directory=tmp_path / "does_not_exist",
            module_prefix="irrelevant",
            module_filename="plugin.py",
        )
        assert result is None


class TestResolveVersions:
    """Tests for :func:`resolve_versions` — map timestamps to version numbers."""

    def test_maps_timestamps_to_version_numbers(self) -> None:
        """Each timestamp is mapped to the active module version number."""
        fake_module = types.ModuleType("fake_module")
        versions = [
            VersionedModule(
                module=fake_module,
                version=0,
                implemented_timestamp=np.datetime64("2026-01-01"),
            ),
            VersionedModule(
                module=fake_module,
                version=1,
                implemented_timestamp=np.datetime64("2026-03-01"),
            ),
        ]
        resolved = resolve_versions(
            versions=versions,
            timestamps=np.array(
                ["2025-12-01", "2026-02-01", "2026-04-01"],
                dtype="datetime64[us]",
            ),
        )
        assert (resolved == np.array([0, 0, 1])).all()
