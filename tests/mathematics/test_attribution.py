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
    product_metric,
    shapley_attribution,
    weighted_mean_metric,
    weighted_total_metric,
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


class TestSegmentedAttribution:
    """Tests for the segmented metric builders and :meth:`Attribution.from_segments`."""

    segments = ("A", "B", "C")
    baseline = pd.DataFrame(
        {"volume": [100.0, 50.0, 80.0], "rate": [0.20, 0.40, 0.30]},
        index=list(segments),
    )
    comparison = pd.DataFrame(
        {"volume": [110.0, 60.0, 70.0], "rate": [0.25, 0.45, 0.28]},
        index=list(segments),
    )

    def test_weighted_total_recovers_change(self) -> None:
        """Total-metric contributions plus interaction equal the aggregate total change."""
        metric = weighted_total_metric(weight="volume", rates=["rate"])
        expected = float(
            (self.comparison["volume"] * self.comparison["rate"]).sum() - (self.baseline["volume"] * self.baseline["rate"]).sum(),
        )
        for method in AttributionMethod:
            result = Attribution(metric, method=method).from_segments(
                baseline=self.baseline,
                comparison=self.comparison,
            )
            assert np.isclose(result.total, expected)

    def test_weighted_mean_recovers_change(self) -> None:
        """Mean-rate contributions plus interaction equal the aggregate rate change."""
        metric = weighted_mean_metric(weight="volume", rates=["rate"])
        baseline_value = float((self.baseline["volume"] * self.baseline["rate"]).sum() / self.baseline["volume"].sum())
        comparison_value = float((self.comparison["volume"] * self.comparison["rate"]).sum() / self.comparison["volume"].sum())
        expected = comparison_value - baseline_value
        for method in AttributionMethod:
            result = Attribution(metric, method=method).from_segments(
                baseline=self.baseline,
                comparison=self.comparison,
            )
            assert np.isclose(result.total, expected)

    def test_weighted_mean_mix_invariance(self) -> None:
        """Uniformly scaling volumes leaves the mean rate and its attribution unchanged."""
        metric = weighted_mean_metric(weight="volume", rates=["rate"])
        attribution = Attribution(metric)
        base = attribution.from_segments(baseline=self.baseline, comparison=self.comparison)
        scaled = attribution.from_segments(
            baseline=self.baseline.assign(volume=self.baseline["volume"] * 10),
            comparison=self.comparison.assign(volume=self.comparison["volume"] * 10),
        )
        assert np.allclose(
            list(base.contributions.values()),
            list(scaled.contributions.values()),
        )

    def test_single_segment_rate_has_zero_volume_effect(self) -> None:
        """With one segment the mean rate ignores volume, so its effect is zero."""
        baseline = pd.DataFrame({"volume": [100.0], "rate": [0.20]}, index=["A"])
        comparison = pd.DataFrame({"volume": [140.0], "rate": [0.25]}, index=["A"])
        result = Attribution(weighted_mean_metric(weight="volume", rates=["rate"])).from_segments(
            baseline=baseline,
            comparison=comparison,
        )
        assert np.isclose(result.contributions["volume"], 0.0)
        assert np.isclose(result.contributions["rate"], 0.05)

    def test_single_segment_total_matches_revenue(self) -> None:
        """A one-segment volume-weighted total reproduces the price-volume revenue split."""
        baseline = pd.DataFrame({"volume": [100.0], "price": [10.0]}, index=["A"])
        comparison = pd.DataFrame({"volume": [110.0], "price": [12.0]}, index=["A"])
        result = Attribution(
            weighted_total_metric(weight="volume", rates=["price"]),
            method=AttributionMethod.SHAPLEY,
        ).from_segments(baseline=baseline, comparison=comparison)
        assert np.isclose(result.contributions["price"], 210.0)
        assert np.isclose(result.contributions["volume"], 110.0)

    def test_product_metric_matches_shapley(self) -> None:
        """The product metric reproduces a manual multiplicative Shapley split."""
        baseline = {"r1": 0.5, "r2": 0.4}
        comparison = {"r1": 0.6, "r2": 0.5}
        result = Attribution(product_metric, method=AttributionMethod.SHAPLEY).from_dict(
            baseline=baseline,
            comparison=comparison,
        )
        expected = shapley_attribution(product_metric, baseline=baseline, comparison=comparison)
        assert np.allclose(list(result.contributions.values()), list(expected.values()))
        assert np.isclose(result.total, product_metric(**comparison) - product_metric(**baseline))

    def test_disjoint_segments_union_aligned(self) -> None:
        """A segment present in only one period is zero-filled rather than dropped to NaN."""
        baseline = pd.DataFrame({"volume": [100.0, 50.0], "rate": [0.20, 0.40]}, index=["A", "B"])
        comparison = pd.DataFrame({"volume": [110.0, 80.0], "rate": [0.25, 0.30]}, index=["A", "C"])
        result = Attribution(weighted_total_metric(weight="volume", rates=["rate"])).from_segments(
            baseline=baseline,
            comparison=comparison,
        )
        baseline_total = 100.0 * 0.20 + 50.0 * 0.40
        comparison_total = 110.0 * 0.25 + 80.0 * 0.30
        assert not np.isnan(list(result.contributions.values())).any()
        assert np.isclose(result.total, comparison_total - baseline_total)

    def test_from_segments_matches_from_dict(self) -> None:
        """``from_segments`` equals a manual ``from_dict`` over the shared columns."""
        attribution = Attribution(weighted_total_metric(weight="volume", rates=["rate"]))
        segments_result = attribution.from_segments(baseline=self.baseline, comparison=self.comparison)
        dict_result = attribution.from_dict(
            baseline={column: self.baseline[column] for column in self.baseline.columns},
            comparison={column: self.comparison[column] for column in self.comparison.columns},
        )
        assert np.allclose(
            list(segments_result.contributions.values()),
            list(dict_result.contributions.values()),
        )

    def test_from_segments_polars_matches_pandas(self) -> None:
        """Polars frames decompose to the same contributions as pandas."""
        attribution = Attribution(weighted_total_metric(weight="volume", rates=["rate"]))
        pandas_result = attribution.from_segments(baseline=self.baseline, comparison=self.comparison)
        polars_result = attribution.from_segments(
            baseline=pl.from_pandas(self.baseline),
            comparison=pl.from_pandas(self.comparison),
        )
        assert np.allclose(
            list(polars_result.contributions.values()),
            list(pandas_result.contributions.values()),
        )

    def test_mismatched_columns_rejected(self) -> None:
        """Frames with differing columns raise a :class:`ValueError`."""
        with pytest.raises(expected_exception=ValueError, match="same columns"):
            Attribution(weighted_total_metric(weight="volume", rates=["rate"])).from_segments(
                baseline=self.baseline,
                comparison=self.comparison.rename(columns={"rate": "other"}),
            )
