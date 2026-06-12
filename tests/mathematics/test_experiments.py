"""Tests for ``mayutils.mathematics.experiments``."""

from __future__ import annotations

from typing import Any

import numpy as np

from mayutils.mathematics.experiments import (
    ExperimentConfig,
    assign_experiment,
    get_experiment_outcomes,
    hash_to_experiment_value,
    parse_experiments,
)

MAX_VALUE = 1_000_000

EXPERIMENTS: dict[str, dict[np.datetime64, ExperimentConfig]] = {
    "elasticity": {
        np.datetime64("1900-01-01"): (("no_change", 1.0),),
        np.datetime64("2026-01-01"): (
            ("down", 0.3),
            ("no_change", 0.4),
            ("up", 0.3),
        ),
    },
}


class TestHashToExperimentValue:
    """Tests for :func:`hash_to_experiment_value` — deterministic hash assignment."""

    def test_identical_ids_hash_identically(self) -> None:
        """The same id always maps to the same hash value."""
        ids = np.array([42, 42, 42])
        values = hash_to_experiment_value(
            ids=ids,
            experiment_name="exp",
            max_value=MAX_VALUE,
        )
        assert values[0] == values[1] == values[2]

    def test_values_within_range(self) -> None:
        """All hash values fall in [0, max_value)."""
        values = hash_to_experiment_value(
            ids=np.arange(1000),
            experiment_name="exp",
            max_value=MAX_VALUE,
        )
        assert (values >= 0).all()
        assert (values < MAX_VALUE).all()

    def test_different_experiment_names_decorrelate(self) -> None:
        """Different experiment names produce different hash values for the same ids."""
        ids = np.arange(1000)
        values_a = hash_to_experiment_value(ids=ids, experiment_name="a", max_value=MAX_VALUE)
        values_b = hash_to_experiment_value(ids=ids, experiment_name="b", max_value=MAX_VALUE)
        assert (values_a != values_b).any()

    def test_known_hash_value_pinned(self) -> None:
        """Pin the exact hash recipe — sha256 of '{name}_{id}' hex mod max."""
        import hashlib

        expected = int(hashlib.sha256(b"exp_7").hexdigest(), 16) % MAX_VALUE
        values = hash_to_experiment_value(
            ids=np.array([7]),
            experiment_name="exp",
            max_value=MAX_VALUE,
        )
        assert values[0] == expected


class TestGetExperimentOutcomes:
    """Tests for :func:`get_experiment_outcomes` — bucket-based outcome assignment."""

    def test_outcomes_respect_proportion_buckets(self) -> None:
        """Values at bucket boundaries map to the correct named arm."""
        array = np.array([0, 299_999, 300_000, 699_999, 700_000, 999_999])
        outcomes = get_experiment_outcomes(
            array=array,
            version_value=(("down", 0.3), ("no_change", 0.4), ("up", 0.3)),
            max_value=MAX_VALUE,
        )
        assert list(outcomes) == ["down", "down", "no_change", "no_change", "up", "up"]

    def test_unnormalised_proportions_are_normalised(self) -> None:
        """Proportions that do not sum to 1.0 are normalised before bucketing."""
        array = np.array([0, 999_999])
        outcomes = get_experiment_outcomes(
            array=array,
            version_value=(("a", 3.0), ("b", 1.0)),
            max_value=MAX_VALUE,
        )
        assert list(outcomes) == ["a", "b"]


class TestAssignExperiment:
    """Tests for :func:`assign_experiment` — timestamp-versioned experiment assignment."""

    def test_pre_config_timestamps_use_first_config(self) -> None:
        """Timestamps before the earliest config date use the first configured version."""
        outcomes = assign_experiment(
            experiment_name="elasticity",
            ids=np.arange(50),
            timestamps=np.full(50, np.datetime64("1990-06-01"), dtype="datetime64[us]"),
            max_value=MAX_VALUE,
            experiments=EXPERIMENTS,
        )
        assert (outcomes == "no_change").all()

    def test_post_config_timestamps_use_later_config(self) -> None:
        """Timestamps after the second config date use the three-arm version."""
        outcomes = assign_experiment(
            experiment_name="elasticity",
            ids=np.arange(2000),
            timestamps=np.full(2000, np.datetime64("2026-06-01"), dtype="datetime64[us]"),
            max_value=MAX_VALUE,
            experiments=EXPERIMENTS,
        )
        assert set(np.unique(outcomes)) == {"down", "no_change", "up"}

    def test_assignment_is_deterministic(self) -> None:
        """Running the same assignment twice produces identical results."""
        kwargs: dict[str, Any] = {
            "experiment_name": "elasticity",
            "ids": np.arange(100),
            "timestamps": np.full(100, np.datetime64("2026-06-01"), dtype="datetime64[us]"),
            "max_value": MAX_VALUE,
            "experiments": EXPERIMENTS,
        }
        first = assign_experiment(**kwargs)
        second = assign_experiment(**kwargs)
        assert (first == second).all()

    def test_proportions_approximately_match_config(self) -> None:
        """Arm proportions over a large population are close to the configured values."""
        expected_proportion_down = 0.3
        tolerance = 0.02
        outcomes = assign_experiment(
            experiment_name="elasticity",
            ids=np.arange(20_000),
            timestamps=np.full(20_000, np.datetime64("2026-06-01"), dtype="datetime64[us]"),
            max_value=MAX_VALUE,
            experiments=EXPERIMENTS,
        )
        proportion_down = float((outcomes == "down").mean())
        assert abs(proportion_down - expected_proportion_down) < tolerance


class TestParseExperiments:
    """Tests for :func:`parse_experiments` — multi-experiment batch assignment."""

    def test_returns_outcome_array_per_experiment(self) -> None:
        """Result contains one array per experiment key, each of the correct length."""
        outcomes = parse_experiments(
            ids=np.arange(10),
            timestamps=np.full(10, np.datetime64("2026-06-01"), dtype="datetime64[us]"),
            experiments=EXPERIMENTS,
            max_value=MAX_VALUE,
        )
        assert set(outcomes.keys()) == {"elasticity"}
        assert outcomes["elasticity"].shape == (10,)
