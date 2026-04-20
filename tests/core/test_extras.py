"""Tests for ``mayutils.core.extras``.

These tests cover dynamic extras resolution via installed distribution
metadata and the ``requires_extras`` context manager.
"""

from __future__ import annotations

import pytest

from mayutils.core.extras import (
    extras_for_module,
    format_missing_extra_hint,
    load_extras_map,
    may_require_extras,
    modules_for_distribution,
    parse_requires_dist_line,
    requires_extras,
)


class TestParseRequiresDist:
    """Tests for :func:`_parse_requires_dist_line` — extracts ``(dist, extra)`` from a ``Requires-Dist`` header."""

    @pytest.mark.parametrize(
        ("line", "expected_dist", "expected_extra"),
        [
            ("polars>=1.32.3 ; extra == 'dataframes'", "polars", "dataframes"),
            ("numpy>=2.3.2", "numpy", None),
            (
                "snowflake-connector-python[secure-local-storage]>=3.17.2 ; extra == 'snowflake'",
                "snowflake-connector-python",
                "snowflake",
            ),
            (
                'plotly>=6.3.0 ; python_version >= "3.12" and extra == "plotting"',
                "plotly",
                "plotting",
            ),
        ],
    )
    def test_parse(self, line: str, expected_dist: str, expected_extra: str | None) -> None:
        """Handles bare deps, quoted markers, sub-extras, and multi-marker lines."""
        dist, extra = parse_requires_dist_line(line)
        assert dist == expected_dist
        assert extra == expected_extra


class TestModulesForDistribution:
    """Tests for :func:`_modules_for_distribution` — resolves dist → top-level module names."""

    def test_installed_dist_via_top_level(self) -> None:
        """Installed distributions are resolved from their ``top_level.txt`` metadata."""
        assert "numpy" in modules_for_distribution("numpy")

    def test_naive_heuristic_for_unknown_dist(self) -> None:
        """Uninstalled distributions fall back to ``name.replace("-", "_")``."""
        assert modules_for_distribution("totally-made-up-xyz") == ("totally_made_up_xyz",)


class TestExtrasForModule:
    """Tests for :func:`extras_for_module` — maps module name → extras that provide it."""

    def test_single_extra(self) -> None:
        """A module belonging to exactly one extra resolves to a singleton set."""
        assert extras_for_module("plotly") == frozenset({"plotting"})

    def test_multi_extra_module(self) -> None:
        """``scipy`` lives under both ``plotting`` and ``stats`` — both are returned."""
        assert extras_for_module("scipy") == frozenset({"plotting", "stats"})

    def test_dotted_module_resolves_via_parent(self) -> None:
        """Dotted submodules fall back to their parent module's extras mapping."""
        assert extras_for_module("plotly.graph_objects") == frozenset({"plotting"})

    def test_unknown_module_returns_empty(self) -> None:
        """Modules not in any extra resolve to an empty set (no hint will be rendered)."""
        assert extras_for_module("completely-unknown") == frozenset()


class TestFormatMissingExtraHint:
    """Tests for :func:`format_missing_extra_hint` — renders an install-hint string."""

    def test_single_extra(self) -> None:
        """A single-extra hint names the module and the exact ``uv add`` command."""
        message = format_missing_extra_hint("plotly")
        assert "plotly" in message
        assert '"mayutils[plotting]"' in message
        assert "uv add" in message

    def test_multiple_extras(self) -> None:
        """When multiple extras provide a module, the hint lists all of them."""
        message = format_missing_extra_hint("scipy")
        assert '"mayutils[plotting]"' in message
        assert '"mayutils[stats]"' in message

    def test_unknown_module_falls_back(self) -> None:
        """Unknown modules produce a generic hint without a ``mayutils[...]`` reference."""
        message = format_missing_extra_hint("unknown-xyz")
        assert "unknown-xyz" in message
        assert "mayutils[" not in message

    def test_explicit_extras_override_auto(self) -> None:
        """Caller-supplied ``extras`` take precedence over automatic resolution."""
        message = format_missing_extra_hint(
            "something",
            extras=("notebook",),
        )
        assert '"mayutils[notebook]"' in message


class TestRequiresExtras:
    """Tests for :func:`requires_extras` — the context manager that decorates ``ImportError``."""

    def test_reraises_with_hint(self) -> None:
        """A failing real import inside the context manager is re-raised with the hint."""
        with pytest.raises(ImportError, match="mayutils\\[plotting\\]") as exc_info, requires_extras("plotting"):
            import nonexistent_module_abc  # pyright: ignore[reportUnusedImport, reportMissingImports] # ty:ignore[unresolved-import]  # noqa: F401, PLC0415
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, ImportError)

    def test_no_extras_uses_auto_resolution(self) -> None:
        """With no extras passed, the hint is derived from the ``ImportError.name`` module."""
        msg = "No module named 'plotly'"
        with pytest.raises(ImportError) as exc_info, requires_extras():
            raise ImportError(msg, name="plotly")
        assert "mayutils[plotting]" in str(exc_info.value)

    def test_preserves_module_name(self) -> None:
        """The re-raised ``ImportError.name`` still matches the originally-missing module."""
        msg = "No module named 'scipy'"
        with pytest.raises(ImportError) as exc_info, requires_extras("plotting"):
            raise ImportError(msg, name="scipy")
        assert exc_info.value.name == "scipy"

    def test_passthrough_when_no_error(self) -> None:
        """The context manager is a no-op when the wrapped block raises nothing."""
        expected = 42
        with requires_extras("plotting"):
            value = expected
        assert value == expected


class TestMayRequireExtras:
    """Tests for :func:`may_require_extras` — auto-resolving no-arg context manager."""

    def test_auto_resolves_single_extra(self) -> None:
        """A failing import inside the block is decorated with the extra inferred from pyproject."""
        msg = "No module named 'plotly'"
        with pytest.raises(ImportError) as exc_info, may_require_extras():
            raise ImportError(msg, name="plotly")
        assert "mayutils[plotting]" in str(exc_info.value)

    def test_auto_resolves_multi_extra(self) -> None:
        """Modules declared by multiple extras get a hint listing all of them."""
        msg = "No module named 'scipy'"
        with pytest.raises(ImportError) as exc_info, may_require_extras():
            raise ImportError(msg, name="scipy")
        rendered = str(exc_info.value)
        assert "mayutils[plotting]" in rendered
        assert "mayutils[stats]" in rendered

    def test_unknown_module_falls_back_to_generic(self) -> None:
        """A module not declared in any extra gets the generic 'not installed' hint."""
        msg = "No module named 'unknown_module_xyz'"
        with pytest.raises(ImportError) as exc_info, may_require_extras():
            raise ImportError(msg, name="unknown_module_xyz")
        rendered = str(exc_info.value)
        assert "unknown_module_xyz" in rendered
        assert "mayutils[" not in rendered

    def test_preserves_module_name(self) -> None:
        """The re-raised ``ImportError.name`` still matches the originally-missing module."""
        msg = "No module named 'polars'"
        with pytest.raises(ImportError) as exc_info, may_require_extras():
            raise ImportError(msg, name="polars")
        assert exc_info.value.name == "polars"

    def test_passthrough_when_no_error(self) -> None:
        """The context manager is a no-op when the wrapped block raises nothing."""
        expected = 42
        with may_require_extras():
            value = expected
        assert value == expected


class TestExtrasMap:
    """Tests for :func:`_load_extras_map` — the cached ``module → extras`` mapping."""

    def test_map_is_populated(self) -> None:
        """When the package is installed, the extras map is non-empty."""
        mapping = load_extras_map()
        assert mapping, "extras map should be populated when running from installed metadata"

    def test_covers_every_declared_extra(self) -> None:
        """Every extra declared in ``pyproject.toml`` appears in the computed mapping."""
        mapping = load_extras_map()
        all_extras = {extra for extras in mapping.values() for extra in extras}
        expected = {
            "plotting",
            "notebook",
            "dataframes",
            "stats",
            "google",
            "microsoft",
            "snowflake",
            "streamlit",
            "web",
            "pdf",
            "datetime",
            "cli",
            "filesystem",
            "keyring",
            "async",
        }
        missing = expected - all_extras
        assert not missing, f"extras not represented in mapping: {sorted(missing)}"
