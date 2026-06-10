"""Tests for ``mayutils.mathematics.analytics.attribution``.

The multiplicative ``revenue`` metric exercises interaction effects
(price and volume changes reinforce each other), while the additive
``margin`` metric has none, so the Shapley and naive decompositions
must coincide on it and the naive interaction term must vanish.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl
import pytest

from mayutils.mathematics.analytics.attribution import (
    Attribution,
    AttributionMethod,
    naive_attribution,
    shapley_attribution,
)
from mayutils.objects.dataframes.backends import Backend


def revenue(
    *,
    price: float,
    volume: float,
) -> float:
    """Multiplicative metric with a price-volume interaction.

    Returns
    -------
    float
        The product of ``price`` and ``volume``.
    """
    return price * volume


def margin(
    *,
    income: float,
    cost: float,
) -> float:
    """Additive metric with no interaction between its factors.

    Returns
    -------
    float
        The difference between ``income`` and ``cost``.
    """
    return income - cost


class TestShapleyAttribution:
    """Tests for :func:`shapley_attribution` — exact Shapley decomposition."""

    def test_two_factor_contributions(self) -> None:
        """Contributions match the hand-computed Shapley values."""
        contributions = shapley_attribution(
            revenue,
            baseline={"price": 10.0, "volume": 100.0},
            comparison={"price": 12.0, "volume": 110.0},
        )
        assert np.isclose(contributions["price"], 210.0)
        assert np.isclose(contributions["volume"], 110.0)

    def test_efficiency_property(self) -> None:
        """Contributions sum exactly to the total metric change."""
        baseline = {"price": 10.0, "volume": 100.0}
        comparison = {"price": 12.0, "volume": 110.0}
        contributions = shapley_attribution(
            revenue,
            baseline=baseline,
            comparison=comparison,
        )
        total = revenue(**comparison) - revenue(**baseline)
        assert np.isclose(sum(contributions.values()), total)

    def test_symmetric_factors_split_equally(self) -> None:
        """Interchangeable factors receive identical contributions."""
        contributions = shapley_attribution(
            revenue,
            baseline={"price": 1.0, "volume": 1.0},
            comparison={"price": 2.0, "volume": 2.0},
        )
        assert np.isclose(contributions["price"], contributions["volume"])

    def test_additive_metric_matches_naive(self) -> None:
        """Without interactions the Shapley and naive results coincide."""
        baseline = {"income": 100.0, "cost": 40.0}
        comparison = {"income": 130.0, "cost": 55.0}
        shapley = shapley_attribution(
            margin,
            baseline=baseline,
            comparison=comparison,
        )
        naive, interaction = naive_attribution(
            margin,
            baseline=baseline,
            comparison=comparison,
        )
        assert np.allclose(
            [shapley["income"], shapley["cost"]],
            [naive["income"], naive["cost"]],
        )
        assert np.isclose(interaction, 0.0)

    def test_mismatched_keys_rejected(self) -> None:
        """Differing factor keys raise a :class:`ValueError`."""
        with pytest.raises(expected_exception=ValueError, match="same factor keys"):
            shapley_attribution(
                revenue,
                baseline={"price": 10.0, "volume": 100.0},
                comparison={"price": 12.0, "cost": 110.0},
            )


class TestNaiveAttribution:
    """Tests for :func:`naive_attribution` — one-at-a-time decomposition."""

    def test_two_factor_contributions(self) -> None:
        """Contributions match the one-at-a-time metric deltas."""
        contributions, interaction = naive_attribution(
            revenue,
            baseline={"price": 10.0, "volume": 100.0},
            comparison={"price": 12.0, "volume": 110.0},
        )
        assert np.isclose(contributions["price"], 200.0)
        assert np.isclose(contributions["volume"], 100.0)
        assert np.isclose(interaction, 20.0)

    def test_contributions_plus_interaction_recover_total(self) -> None:
        """Contributions plus the interaction equal the total change."""
        baseline = {"price": 5.0, "volume": 50.0}
        comparison = {"price": 8.0, "volume": 65.0}
        contributions, interaction = naive_attribution(
            revenue,
            baseline=baseline,
            comparison=comparison,
        )
        total = revenue(**comparison) - revenue(**baseline)
        assert np.isclose(sum(contributions.values()) + interaction, total)

    def test_mismatched_keys_rejected(self) -> None:
        """Differing factor keys raise a :class:`ValueError`."""
        with pytest.raises(expected_exception=ValueError, match="same factor keys"):
            naive_attribution(
                revenue,
                baseline={"price": 10.0, "volume": 100.0},
                comparison={"price": 12.0, "cost": 110.0},
            )


class TestAttribution:
    """Tests for :class:`Attribution` — class front end over both methods."""

    segments = ("A", "B", "C", "D", "E")
    baseline_frame = pd.DataFrame(
        {
            "price": [10.0, 8.0, 12.0, 9.0, 11.0],
            "volume": [100.0, 50.0, 80.0, 60.0, 40.0],
        },
        index=list(segments),
    )
    comparison_frame = pd.DataFrame(
        {
            "price": [12.0, 9.0, 11.0, 10.0, 11.0],
            "volume": [110.0, 55.0, 90.0, 50.0, 45.0],
        },
        index=list(segments),
    )

    def test_method_defaults_to_shapley(self) -> None:
        """The bound method is stored, defaulting to Shapley."""
        assert Attribution(revenue, method=AttributionMethod.BASIC).method is AttributionMethod.BASIC
        assert Attribution(revenue).method is AttributionMethod.SHAPLEY

    def test_from_dict_shapley_matches_function(self) -> None:
        """The class delegates to :func:`shapley_attribution` with zero interaction."""
        baseline = {"price": 10.0, "volume": 100.0}
        comparison = {"price": 12.0, "volume": 110.0}
        result = Attribution(revenue, method=AttributionMethod.SHAPLEY).from_dict(
            baseline=baseline,
            comparison=comparison,
        )
        expected = shapley_attribution(revenue, baseline=baseline, comparison=comparison)
        assert np.allclose(
            list(result.contributions.values()),
            list(expected.values()),
        )
        assert np.isclose(result.interaction, 0.0)
        assert np.isclose(result.total, 320.0)

    def test_from_dict_basic_matches_function(self) -> None:
        """The class delegates to :func:`naive_attribution` with its interaction."""
        baseline = {"price": 10.0, "volume": 100.0}
        comparison = {"price": 12.0, "volume": 110.0}
        result = Attribution(revenue, method=AttributionMethod.BASIC).from_dict(
            baseline=baseline,
            comparison=comparison,
        )
        contributions, interaction = naive_attribution(
            revenue,
            baseline=baseline,
            comparison=comparison,
        )
        assert np.allclose(
            list(result.contributions.values()),
            list(contributions.values()),
        )
        assert np.isclose(result.interaction, interaction)

    def test_from_dataframe_segments_shapley(self) -> None:
        """Five segments are decomposed row-wise with zero interaction."""
        result = Attribution(revenue, method=AttributionMethod.SHAPLEY).from_dataframe(
            baseline=self.baseline_frame,
            comparison=self.comparison_frame,
        )
        assert list(result.index) == list(self.segments)
        assert list(result.columns) == ["price", "volume", "interaction"]
        assert np.allclose(result["interaction"], 0.0)
        assert np.allclose(result.loc["A"], [210.0, 110.0, 0.0])

    def test_from_dataframe_explicit_backend(self) -> None:
        """Passing the pandas backend token matches the inferred result."""
        attribution = Attribution(revenue, method=AttributionMethod.SHAPLEY)
        explicit = attribution.from_dataframe(
            baseline=self.baseline_frame,
            comparison=self.comparison_frame,
            backend=Backend(pd.DataFrame),
        )
        inferred = attribution.from_dataframe(
            baseline=self.baseline_frame,
            comparison=self.comparison_frame,
        )
        assert np.allclose(explicit.to_numpy(), inferred.to_numpy())

    def test_from_dataframe_polars_matches_pandas(self) -> None:
        """Polars frames are attributed row-wise to the same values as pandas."""
        attribution = Attribution(revenue, method=AttributionMethod.BASIC)
        polars_result = attribution.from_dataframe(
            baseline=pl.from_pandas(self.baseline_frame),
            comparison=pl.from_pandas(self.comparison_frame),
        )
        pandas_result = attribution.from_dataframe(
            baseline=self.baseline_frame,
            comparison=self.comparison_frame,
        )
        assert isinstance(polars_result, pl.DataFrame)
        assert polars_result.columns == ["price", "volume", "interaction"]
        assert np.allclose(polars_result.to_numpy(), pandas_result.to_numpy())

    def test_from_dataframe_misaligned_polars_frames_rejected(self) -> None:
        """Polars frames with differing heights raise a :class:`ValueError`."""
        with pytest.raises(expected_exception=ValueError, match="same columns and height"):
            Attribution(revenue).from_dataframe(
                baseline=pl.from_pandas(self.baseline_frame),
                comparison=pl.from_pandas(self.comparison_frame).head(3),
            )

    def test_from_dataframe_recovers_total_change(self) -> None:
        """All cells sum to the total revenue change across segments."""
        total = float(
            (self.comparison_frame["price"] * self.comparison_frame["volume"]).sum()
            - (self.baseline_frame["price"] * self.baseline_frame["volume"]).sum(),
        )
        for method in AttributionMethod:
            result = Attribution(revenue, method=method).from_dataframe(
                baseline=self.baseline_frame,
                comparison=self.comparison_frame,
            )
            assert np.isclose(result.to_numpy().sum(), total)

    def test_from_dataframe_misaligned_frames_rejected(self) -> None:
        """Frames with differing indices raise a :class:`ValueError`."""
        with pytest.raises(expected_exception=ValueError, match="same index and columns"):
            Attribution(revenue).from_dataframe(
                baseline=self.baseline_frame,
                comparison=self.comparison_frame.iloc[:-1],
            )
