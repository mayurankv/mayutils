"""Tests for ``mayutils.objects.versions``."""

from __future__ import annotations

import pytest
from packaging.version import Version

from mayutils.objects.versions import bump_version_string


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
        with pytest.raises(ValueError, match="Unknown part to bump"):
            bump_version_string("1.0.0", bump="build")
