"""
Attribute changes in a metric between two scenarios to driving factors.

This module decomposes the difference in a metric evaluated at a
``baseline`` and a ``comparison`` set of factor values into per-factor
contributions. The :class:`Attribution` front end binds a metric and a
decomposition method at instantiation and accepts scenarios as plain
mappings (:meth:`Attribution.from_dict`) or as aligned dataframes
attributed row by row (:meth:`Attribution.from_dataframe`), with the
dataframe library selected by the repository-wide
:class:`~mayutils.objects.dataframes.backends.Backend` token. The
underlying decompositions are an exact Shapley allocation
(:func:`shapley_attribution`), which averages each factor's marginal
effect over every possible switching order and therefore allocates the
total change exactly, and a basic one-at-a-time allocation
(:func:`naive_attribution`), which switches each factor in isolation and
reports the unallocated remainder as a single interaction term. The
Shapley variant evaluates the metric at all ``2**n`` factor subsets, so
it suits the small factor counts typical of pricing waterfalls and
bridge analyses.

See Also
--------
itertools.combinations : Subset enumeration used by the Shapley sweep.
math.factorial : Combinatorial weights of the Shapley formula.
mayutils.mathematics.statistics : Sibling statistical helpers.
mayutils.mathematics : Parent package hosting numerical utilities.

Examples
--------
>>> from mayutils.mathematics.analytics.attribution import (
...     Attribution,
...     AttributionMethod,
... )
>>> def revenue(*, price: float, volume: float) -> float:
...     return price * volume
>>> attribution = Attribution(revenue, method=AttributionMethod.SHAPLEY)
>>> attribution.from_dict(
...     baseline={"price": 10.0, "volume": 100.0},
...     comparison={"price": 12.0, "volume": 110.0},
... ).contributions
{'price': 210.0, 'volume': 110.0}
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations
from math import factorial
from typing import TYPE_CHECKING, Any, cast

from mayutils.core.extras import may_require_extras

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    import pandas as pd
    import polars as pl

    from mayutils.objects.dataframes.backends import Backend, DataFrames


def shapley_attribution[T](
    metric: Callable[..., float],
    /,
    *,
    baseline: Mapping[str, T],
    comparison: Mapping[str, T],
) -> dict[str, float]:
    """
    Attribute a metric change to factors via exact Shapley values.

    Decompose ``metric(**comparison) - metric(**baseline)`` into one
    contribution per factor by averaging each factor's marginal effect
    over all orders in which the factors could be switched from their
    baseline to their comparison values. The metric is evaluated once at
    every subset of switched factors (``2**n`` evaluations for ``n``
    factors) and each marginal difference is weighted by the standard
    Shapley coefficient ``|S|! * (n - |S| - 1)! / n!``. By the
    efficiency property the contributions sum exactly to the total
    change, with interaction effects shared symmetrically between the
    factors involved.

    Parameters
    ----------
    metric
        Function computing the metric from factor values. It is called
        with one keyword argument per factor, so the keys of
        ``baseline`` must be valid keyword names of ``metric``.
    baseline
        Factor values describing the reference scenario. Keys name the
        factors and define the attribution targets.
    comparison
        Factor values describing the scenario being explained. Must
        have exactly the same keys as ``baseline``.

    Returns
    -------
        Mapping from factor name to its Shapley contribution, in the
        key order of ``baseline``. The values sum to
        ``metric(**comparison) - metric(**baseline)``.

    Raises
    ------
    ValueError
        If ``baseline`` and ``comparison`` do not share the same keys.

    See Also
    --------
    naive_attribution : Cheaper one-at-a-time decomposition with an
        explicit residual interaction term.
    Attribution : Class front end binding a metric and method once.
    itertools.combinations : Enumerates the switched-factor subsets.
    math.factorial : Supplies the Shapley weights.

    Examples
    --------
    >>> def revenue(*, price: float, volume: float) -> float:
    ...     return price * volume
    >>> contributions = shapley_attribution(
    ...     revenue,
    ...     baseline={"price": 10.0, "volume": 100.0},
    ...     comparison={"price": 12.0, "volume": 110.0},
    ... )
    >>> contributions
    {'price': 210.0, 'volume': 110.0}
    >>> sum(contributions.values())
    320.0
    """
    factors = tuple(baseline.keys())
    if set(comparison.keys()) != set(factors):
        msg = f"Baseline and comparison must share the same factor keys, got {sorted(baseline.keys())} and {sorted(comparison.keys())}"
        raise ValueError(msg)

    values: dict[frozenset[str], float] = {}
    for size in range(len(factors) + 1):
        for subset in combinations(factors, size):
            switched = frozenset(subset)
            values[switched] = metric(
                **{factor: comparison[factor] if factor in switched else baseline[factor] for factor in factors},
            )

    n = len(factors)
    weights = {size: factorial(size) * factorial(n - size - 1) / factorial(n) for size in range(n)}

    return {
        factor: sum(
            weights[size] * (values[frozenset(subset) | {factor}] - values[frozenset(subset)])
            for size in range(n)
            for subset in combinations(
                tuple(other for other in factors if other != factor),
                size,
            )
        )
        for factor in factors
    }


def naive_attribution[T](
    metric: Callable[..., float],
    /,
    *,
    baseline: Mapping[str, T],
    comparison: Mapping[str, T],
) -> tuple[dict[str, float], float]:
    """
    Attribute a metric change via one-at-a-time factor switches.

    Decompose ``metric(**comparison) - metric(**baseline)`` by moving
    each factor in isolation from its baseline to its comparison value
    while holding every other factor at baseline. Because each factor
    is switched on its own, joint effects between factors are not
    captured by the per-factor contributions; the gap between the total
    change and the sum of contributions is returned separately as a
    single interaction term. The metric is evaluated ``n + 2`` times
    for ``n`` factors, making this the cheap companion to
    :func:`shapley_attribution`.

    Parameters
    ----------
    metric
        Function computing the metric from factor values. It is called
        with one keyword argument per factor, so the keys of
        ``baseline`` must be valid keyword names of ``metric``.
    baseline
        Factor values describing the reference scenario. Keys name the
        factors and define the attribution targets.
    comparison
        Factor values describing the scenario being explained. Must
        have exactly the same keys as ``baseline``.

    Returns
    -------
        Pair of the per-factor contributions (in the key order of
        ``baseline``) and the interaction term, where the contributions
        plus the interaction equal
        ``metric(**comparison) - metric(**baseline)``.

    Raises
    ------
    ValueError
        If ``baseline`` and ``comparison`` do not share the same keys.

    See Also
    --------
    shapley_attribution : Exact decomposition that shares interaction
        effects between factors instead of reporting a residual.
    Attribution : Class front end binding a metric and method once.

    Examples
    --------
    >>> def revenue(*, price: float, volume: float) -> float:
    ...     return price * volume
    >>> contributions, interaction = naive_attribution(
    ...     revenue,
    ...     baseline={"price": 10.0, "volume": 100.0},
    ...     comparison={"price": 12.0, "volume": 110.0},
    ... )
    >>> contributions
    {'price': 200.0, 'volume': 100.0}
    >>> interaction
    20.0
    """
    factors = tuple(baseline.keys())
    if set(comparison.keys()) != set(factors):
        msg = f"Baseline and comparison must share the same factor keys, got {sorted(baseline.keys())} and {sorted(comparison.keys())}"
        raise ValueError(msg)

    baseline_value = metric(**baseline)
    total = metric(**comparison) - baseline_value
    contributions = {factor: metric(**{**baseline, factor: comparison[factor]}) - baseline_value for factor in factors}
    interaction = total - sum(contributions.values())

    return contributions, interaction


def reduce_total(
    value: object,
    /,
) -> float:
    """
    Reduce a scalar or per-segment factor value to a float total.

    Sum the value across segments when it exposes a ``sum`` method (a
    pandas or polars Series, or a numpy array) and pass a plain scalar
    through unchanged, so the segmented and single-value cases share one
    reduction without importing a dataframe library at module load.

    Parameters
    ----------
    value
        A scalar factor value, or a Series-like of per-segment values
        exposing a ``sum`` method.

    Returns
    -------
        The value summed across segments as a float.

    See Also
    --------
    weighted_total_metric : Builds a metric that reduces with this helper.
    weighted_mean_metric : Builds a metric that reduces with this helper.

    Examples
    --------
    >>> reduce_total(5.0)
    5.0
    """
    summed = cast("Any", value).sum() if hasattr(value, "sum") else value

    return float(cast("Any", summed))


def product_metric(
    **factors: float,
) -> float:
    """
    Multiply factor values into a single product metric.

    Return the product of every supplied factor, the canonical
    multiplicative metric for an unweighted product of rates with no
    segmentation (for example a funnel rate built from per-stage
    conversion rates). Pass it straight to :class:`Attribution` as the
    bound metric.

    Parameters
    ----------
    **factors
        Factor values keyed by name; their product is the metric.

    Returns
    -------
        The product of all supplied factor values.

    See Also
    --------
    weighted_mean_metric : Builds a volume-weighted mean rate metric.
    weighted_total_metric : Builds a volume-weighted total metric.
    Attribution : Front end that binds a metric for decomposition.

    Examples
    --------
    >>> product_metric(quote_rate=0.5, click_rate=0.4)
    0.2
    """
    product = 1.0
    for value in factors.values():
        product = product * value

    return float(product)


def weighted_total_metric(
    *,
    weight: str,
    rates: Sequence[str],
) -> Callable[..., float]:
    """
    Build a volume-weighted total metric over segments.

    Return a metric evaluating ``sum_s w_s * prod_k r_{k,s}``: the
    ``weight`` factor multiplied by every factor named in ``rates`` per
    segment, then summed across segments. With scalar factors it reduces
    to a single-segment total such as the classic price-times-volume
    revenue, and the weight participates in the attribution as the volume
    effect.

    Parameters
    ----------
    weight
        Name of the factor holding per-segment volumes.
    rates
        Names of the rate factors multiplied into each segment's total.

    Returns
    -------
        A metric taking the named factors as keyword arguments and
        returning their volume-weighted total.

    See Also
    --------
    weighted_mean_metric : Volume-weighted mean rate counterpart.
    product_metric : Unweighted product of factor values.
    Attribution.from_segments : Decomposes a segmented metric change.

    Examples
    --------
    >>> metric = weighted_total_metric(weight="volume", rates=["price"])
    >>> metric(volume=100.0, price=10.0)
    1000.0
    """

    def metric(
        **factors: object,
    ) -> float:
        """
        Evaluate the volume-weighted total for one scenario.

        Multiply the bound weight factor by each bound rate factor per
        segment and sum the products across segments.

        Parameters
        ----------
        **factors
            Factor values keyed by name, supplied by the attribution
            engine for the baseline or comparison scenario.

        Returns
        -------
            The volume-weighted total across segments.

        See Also
        --------
        weighted_total_metric : Builder that produces this metric.

        Examples
        --------
        >>> weighted_total_metric(weight="volume", rates=["price"])(volume=100.0, price=10.0)
        1000.0
        """
        product = factors[weight]
        for rate in rates:
            product = cast("Any", product) * factors[rate]

        return reduce_total(product)

    return metric


def weighted_mean_metric(
    *,
    weight: str,
    rates: Sequence[str],
) -> Callable[..., float]:
    """
    Build a volume-weighted mean rate metric over segments.

    Return a metric evaluating ``sum_s w_s * prod_k r_{k,s} / sum_s w_s``:
    the ``weight`` factor multiplied by every factor named in ``rates``
    per segment, summed across segments, then divided by the total
    weight. The weight enters the attribution as the mix effect, since
    uniform scaling of the weights cancels in the ratio and only their
    relative distribution moves the metric. With scalar factors it
    reduces to the unweighted product of rates.

    Parameters
    ----------
    weight
        Name of the factor holding per-segment volumes.
    rates
        Names of the rate factors multiplied into each segment's value.

    Returns
    -------
        A metric taking the named factors as keyword arguments and
        returning their volume-weighted mean rate.

    See Also
    --------
    weighted_total_metric : Volume-weighted total counterpart.
    product_metric : Unweighted product of factor values.
    Attribution.from_segments : Decomposes a segmented metric change.

    Examples
    --------
    >>> metric = weighted_mean_metric(weight="volume", rates=["rate"])
    >>> metric(volume=100.0, rate=0.2)
    0.2
    """

    def metric(
        **factors: object,
    ) -> float:
        """
        Evaluate the volume-weighted mean rate for one scenario.

        Multiply the bound weight factor by each bound rate factor per
        segment, sum across segments, and divide by the total weight.

        Parameters
        ----------
        **factors
            Factor values keyed by name, supplied by the attribution
            engine for the baseline or comparison scenario.

        Returns
        -------
            The volume-weighted mean rate across segments.

        See Also
        --------
        weighted_mean_metric : Builder that produces this metric.

        Examples
        --------
        >>> weighted_mean_metric(weight="volume", rates=["rate"])(volume=100.0, rate=0.2)
        0.2
        """
        weights = factors[weight]
        product = weights
        for rate in rates:
            product = cast("Any", product) * factors[rate]

        return reduce_total(product) / reduce_total(weights)

    return metric


class AttributionMethod(StrEnum):
    """
    Supported attribution decomposition methods.

    A string enumeration whose members select how :class:`Attribution`
    splits a metric change across factors. Each member's value is the
    lower-case slug accepted by the :class:`Attribution` constructor.

    Attributes
    ----------
    SHAPLEY
        Exact Shapley decomposition via :func:`shapley_attribution`;
        interaction effects are shared between factors and the
        residual interaction term is structurally zero.
    BASIC
        One-at-a-time decomposition via :func:`naive_attribution`;
        joint effects are reported separately as a residual
        interaction term.

    See Also
    --------
    Attribution : Consumer that dispatches on this enumeration.
    shapley_attribution : Decomposition behind ``SHAPLEY``.
    naive_attribution : Decomposition behind ``BASIC``.

    Examples
    --------
    >>> AttributionMethod.SHAPLEY
    <AttributionMethod.SHAPLEY: 'shapley'>
    >>> AttributionMethod("basic")
    <AttributionMethod.BASIC: 'basic'>
    """

    SHAPLEY = "shapley"
    BASIC = "basic"


@dataclass(frozen=True)
class AttributionResult:
    """
    Hold the per-factor contributions and interaction of one attribution.

    Bundle the two outputs of a decomposition into a single immutable
    record so Shapley and basic attributions share one return shape.
    Under the Shapley method the interaction term is structurally zero
    because joint effects are already shared between the factor
    contributions; under the basic method it carries the change left
    unexplained by the one-at-a-time switches.

    Attributes
    ----------
    contributions
        Mapping from factor name to its attributed share of the metric
        change, in the key order of the baseline scenario.
    interaction
        Residual change not allocated to any single factor. Zero for
        Shapley attributions.

    See Also
    --------
    Attribution : Produces instances of this record.
    shapley_attribution : Decomposition with zero interaction term.
    naive_attribution : Decomposition with an explicit interaction term.

    Examples
    --------
    >>> result = AttributionResult(
    ...     contributions={"price": 200.0, "volume": 100.0},
    ...     interaction=20.0,
    ... )
    >>> result.total
    320.0
    """

    contributions: dict[str, float]
    interaction: float

    @property
    def total(self) -> float:
        """
        Total metric change recovered by the decomposition.

        Sum the per-factor contributions and the interaction term,
        which reconstructs ``metric(**comparison) - metric(**baseline)``
        for both decomposition methods.

        Returns
        -------
            Sum of all contributions plus the interaction term.

        See Also
        --------
        AttributionResult.contributions : Per-factor shares being summed.

        Examples
        --------
        >>> AttributionResult(
        ...     contributions={"price": 210.0, "volume": 110.0},
        ...     interaction=0.0,
        ... ).total
        320.0
        """
        return sum(self.contributions.values()) + self.interaction


class Attribution:
    """
    Attribute metric changes to factors with a fixed metric and method.

    Bind a metric function and a decomposition method once, then apply
    the attribution to scenarios supplied in different shapes: plain
    factor mappings via :meth:`from_dict` or aligned dataframes via
    :meth:`from_dataframe`, which decomposes each row (for example one
    segment per row) independently and dispatches on a
    :class:`~mayutils.objects.dataframes.backends.Backend` token so
    pandas and polars frames are handled alike. Both entry points
    return the same contribution-plus-interaction structure so callers
    can switch between Shapley and basic decompositions without
    changing call sites.

    Parameters
    ----------
    metric
        Function computing the metric from factor values. It is called
        with one keyword argument per factor, so factor names must be
        valid keyword names of ``metric``.
    method
        Decomposition to apply: ``"shapley"`` for the exact Shapley
        allocation or ``"basic"`` for the one-at-a-time allocation with
        a residual interaction term.

    Attributes
    ----------
    metric
        Bound metric function used for every attribution.
    method
        Resolved :class:`AttributionMethod` member controlling
        dispatch.

    See Also
    --------
    AttributionMethod : Enumeration of the supported decompositions.
    AttributionResult : Record returned by :meth:`from_dict`.
    shapley_attribution : Functional core behind ``"shapley"``.
    naive_attribution : Functional core behind ``"basic"``.

    Examples
    --------
    >>> def revenue(*, price: float, volume: float) -> float:
    ...     return price * volume
    >>> attribution = Attribution(revenue, method=AttributionMethod.BASIC)
    >>> result = attribution.from_dict(
    ...     baseline={"price": 10.0, "volume": 100.0},
    ...     comparison={"price": 12.0, "volume": 110.0},
    ... )
    >>> result.contributions
    {'price': 200.0, 'volume': 100.0}
    >>> result.interaction
    20.0
    """

    def __init__(
        self,
        metric: Callable[..., float],
        /,
        *,
        method: AttributionMethod = AttributionMethod.SHAPLEY,
    ) -> None:
        """
        Bind the metric and decomposition method for later attributions.

        Store the metric callable and the :class:`AttributionMethod`
        member unchanged for use by every subsequent attribution call.

        Parameters
        ----------
        metric
            Function computing the metric from factor values. It is
            called with one keyword argument per factor.
        method
            Decomposition to apply, as an :class:`AttributionMethod`
            member.

        See Also
        --------
        AttributionMethod : Accepted decomposition identifiers.

        Examples
        --------
        >>> def margin(*, income: float, cost: float) -> float:
        ...     return income - cost
        >>> Attribution(margin, method=AttributionMethod.SHAPLEY).method
        <AttributionMethod.SHAPLEY: 'shapley'>
        """
        self.metric = metric
        self.method = method

    def from_dict[T](
        self,
        *,
        baseline: Mapping[str, T],
        comparison: Mapping[str, T],
    ) -> AttributionResult:
        """
        Attribute the change between two scenarios given as mappings.

        Evaluate the bound metric on the ``baseline`` and
        ``comparison`` factor mappings and decompose the difference
        with the bound method. Shapley attributions place all joint
        effects inside the per-factor contributions and report a zero
        interaction term; basic attributions report one-at-a-time
        contributions and the unallocated remainder as the interaction.

        Parameters
        ----------
        baseline
            Factor values describing the reference scenario. Keys name
            the factors and define the attribution targets.
        comparison
            Factor values describing the scenario being explained.
            Must have exactly the same keys as ``baseline``.

        Returns
        -------
            Record holding the per-factor contributions and the
            interaction term; their sum equals the total metric change.

        See Also
        --------
        Attribution.from_dataframe : Row-wise variant for aligned
            dataframes.
        AttributionResult : Structure of the returned record.

        Examples
        --------
        >>> def revenue(*, price: float, volume: float) -> float:
        ...     return price * volume
        >>> Attribution(revenue, method=AttributionMethod.SHAPLEY).from_dict(
        ...     baseline={"price": 10.0, "volume": 100.0},
        ...     comparison={"price": 12.0, "volume": 110.0},
        ... ).contributions
        {'price': 210.0, 'volume': 110.0}
        """
        if self.method is AttributionMethod.SHAPLEY:
            return AttributionResult(
                contributions=shapley_attribution(
                    self.metric,
                    baseline=baseline,
                    comparison=comparison,
                ),
                interaction=0.0,
            )

        contributions, interaction = naive_attribution(
            self.metric,
            baseline=baseline,
            comparison=comparison,
        )

        return AttributionResult(
            contributions=contributions,
            interaction=interaction,
        )

    def from_dataframe[DataFrameType: DataFrames = pd.DataFrame](
        self,
        *,
        baseline: DataFrameType,
        comparison: DataFrameType,
        backend: Backend[DataFrameType] | None = None,
    ) -> DataFrameType:
        """
        Attribute each row of two aligned scenario frames independently.

        Treat every row (for example a customer segment) as a separate
        attribution problem: the row's columns supply the factor
        values, the bound metric is decomposed per row, and the results
        are stacked into a frame of the same backend with one column
        per factor plus an ``"interaction"`` column, which is
        identically zero under the Shapley method. The dataframe
        library is dispatched on the
        :class:`~mayutils.objects.dataframes.backends.Backend` token,
        inferred from ``baseline`` when not supplied: pandas frames are
        matched on their index (which the output shares) while polars
        frames, having no index, are matched positionally. Because each
        row is decomposed against its own baseline, the cells of a row
        sum to that row's metric change and the whole frame sums to the
        total change of a metric that is additive over rows.

        Parameters
        ----------
        baseline
            Reference scenario with one row per attribution unit and
            one column per factor. Column names must be valid keyword
            names of the bound metric.
        comparison
            Scenario being explained. Must share the index (pandas) or
            height (polars) and the columns of ``baseline`` exactly.
        backend
            Backend token selecting the dataframe library. When
            ``None``, the backend is inferred from the concrete type
            of ``baseline``.

        Returns
        -------
            Frame of the input backend with one contribution column
            per factor and a final ``"interaction"`` column, sharing
            the input index under pandas and the input row order under
            polars.

        Raises
        ------
        ValueError
            If the two frames are not aligned or the backend is not
            supported.

        See Also
        --------
        Attribution.from_dict : Single-scenario variant for plain
            mappings.
        mayutils.objects.dataframes.backends.Backend : Token selecting
            the dataframe library.

        Examples
        --------
        >>> import pandas as pd
        >>> def revenue(*, price: float, volume: float) -> float:
        ...     return price * volume
        >>> baseline = pd.DataFrame(
        ...     {"price": [10.0, 8.0], "volume": [100.0, 50.0]},
        ...     index=["A", "B"],
        ... )
        >>> comparison = pd.DataFrame(
        ...     {"price": [12.0, 9.0], "volume": [110.0, 55.0]},
        ...     index=["A", "B"],
        ... )
        >>> Attribution(revenue, method=AttributionMethod.BASIC).from_dataframe(
        ...     baseline=baseline,
        ...     comparison=comparison,
        ... )
           price  volume  interaction
        A  200.0   100.0         20.0
        B   50.0    40.0          5.0
        >>> import polars as pl
        >>> Attribution(revenue, method=AttributionMethod.BASIC).from_dataframe(
        ...     baseline=pl.DataFrame({"price": [10.0], "volume": [100.0]}),
        ...     comparison=pl.DataFrame({"price": [12.0], "volume": [110.0]}),
        ... ).to_dicts()
        [{'price': 200.0, 'volume': 100.0, 'interaction': 20.0}]
        """
        with may_require_extras():
            from mayutils.objects.dataframes.backends import Backend

        resolved_backend = Backend.infer(baseline) if backend is None else backend

        if resolved_backend.name == "pandas":
            with may_require_extras():
                import pandas as pd

            baseline_pd = cast("pd.DataFrame", baseline)
            comparison_pd = cast("pd.DataFrame", comparison)
            if not (baseline_pd.index.equals(comparison_pd.index) and baseline_pd.columns.equals(comparison_pd.columns)):
                msg = "Baseline and comparison frames must share the same index and columns"
                raise ValueError(msg)

            pandas_rows: list[dict[str, float]] = []
            for label in baseline_pd.index:
                result = self.from_dict(
                    baseline={str(column): baseline_pd.loc[label, column] for column in baseline_pd.columns},
                    comparison={str(column): comparison_pd.loc[label, column] for column in comparison_pd.columns},
                )
                pandas_rows.append({**result.contributions, "interaction": result.interaction})

            return cast("DataFrameType", pd.DataFrame(data=pandas_rows, index=baseline_pd.index))

        if resolved_backend.name == "polars":
            with may_require_extras():
                import polars as pl

            baseline_pl = cast("pl.DataFrame", baseline)
            comparison_pl = cast("pl.DataFrame", comparison)
            if baseline_pl.columns != comparison_pl.columns or baseline_pl.height != comparison_pl.height:
                msg = "Baseline and comparison frames must share the same columns and height"
                raise ValueError(msg)

            polars_rows: list[dict[str, float]] = []
            for baseline_row, comparison_row in zip(
                baseline_pl.iter_rows(named=True),
                comparison_pl.iter_rows(named=True),
                strict=True,
            ):
                result = self.from_dict(baseline=baseline_row, comparison=comparison_row)
                polars_rows.append({**result.contributions, "interaction": result.interaction})

            return cast("DataFrameType", pl.DataFrame(data=polars_rows))

        msg = f"Unsupported backend: {resolved_backend.name}"
        raise ValueError(msg)

    def from_segments[DataFrameType: DataFrames = pd.DataFrame](
        self,
        *,
        baseline: DataFrameType,
        comparison: DataFrameType,
        backend: Backend[DataFrameType] | None = None,
    ) -> AttributionResult:
        """
        Attribute the change in an aggregate metric across segments.

        Treat each column as a single factor whose value is the whole
        column, a vector of per-segment values, and decompose the bound
        metric once over all segments at once rather than row by row as
        :meth:`from_dataframe` does. The metric must reduce its
        per-segment factor vectors to a scalar, as the builders
        :func:`weighted_total_metric` and :func:`weighted_mean_metric` do.
        Baseline and comparison are aligned on the union of their segment
        labels with missing entries filled with zero, so the Shapley
        sweep's mixed scenarios never align mismatched segments into NaNs.
        The dataframe library is dispatched on the
        :class:`~mayutils.objects.dataframes.backends.Backend` token,
        inferred from ``baseline`` when not supplied.

        Parameters
        ----------
        baseline
            Reference scenario with one row per segment and one column per
            factor. Column names must be valid keyword names of the bound
            metric.
        comparison
            Scenario being explained. Must share the columns of
            ``baseline``; under pandas its segment labels need not match,
            as both frames are aligned on the union of segments.
        backend
            Backend token selecting the dataframe library. When ``None``,
            the backend is inferred from the concrete type of ``baseline``.

        Returns
        -------
            Record holding the per-factor contributions and the
            interaction term; their sum equals the total metric change.

        Raises
        ------
        ValueError
            If the frames do not share their columns, if a polars pair
            differs in height, or if the backend is not supported.

        See Also
        --------
        Attribution.from_dataframe : Row-wise per-segment variant.
        Attribution.from_dict : Single-scenario mapping variant.
        weighted_mean_metric : Builds a metric suited to this method.

        Examples
        --------
        >>> import pandas as pd
        >>> from mayutils.mathematics.analytics.attribution import (
        ...     Attribution,
        ...     weighted_total_metric,
        ... )
        >>> segments = ["A", "B"]
        >>> baseline = pd.DataFrame(
        ...     {"volume": [100.0, 50.0], "rate": [0.2, 0.4]},
        ...     index=segments,
        ... )
        >>> comparison = pd.DataFrame(
        ...     {"volume": [110.0, 60.0], "rate": [0.25, 0.45]},
        ...     index=segments,
        ... )
        >>> result = Attribution(
        ...     weighted_total_metric(weight="volume", rates=["rate"]),
        ... ).from_segments(baseline=baseline, comparison=comparison)
        >>> round(result.total, 4)
        14.5
        """
        with may_require_extras():
            from mayutils.objects.dataframes.backends import Backend

        resolved_backend = Backend.infer(baseline) if backend is None else backend

        if resolved_backend.name == "pandas":
            baseline_pd = cast("pd.DataFrame", baseline)
            comparison_pd = cast("pd.DataFrame", comparison)
            if not baseline_pd.columns.equals(comparison_pd.columns):
                msg = "Baseline and comparison frames must share the same columns"
                raise ValueError(msg)

            segments = baseline_pd.index.union(comparison_pd.index)
            aligned_baseline = baseline_pd.reindex(index=segments).fillna(value=0)
            aligned_comparison = comparison_pd.reindex(index=segments).fillna(value=0)

            return self.from_dict(
                baseline={str(column): aligned_baseline[column] for column in aligned_baseline.columns},
                comparison={str(column): aligned_comparison[column] for column in aligned_comparison.columns},
            )

        if resolved_backend.name == "polars":
            baseline_pl = cast("pl.DataFrame", baseline)
            comparison_pl = cast("pl.DataFrame", comparison)
            if baseline_pl.columns != comparison_pl.columns or baseline_pl.height != comparison_pl.height:
                msg = "Baseline and comparison frames must share the same columns and height"
                raise ValueError(msg)

            return self.from_dict(
                baseline={column: baseline_pl[column] for column in baseline_pl.columns},
                comparison={column: comparison_pl[column] for column in comparison_pl.columns},
            )

        msg = f"Unsupported backend: {resolved_backend.name}"
        raise ValueError(msg)
