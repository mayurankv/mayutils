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
from typing import TYPE_CHECKING, cast

from mayutils.core.extras import may_require_extras

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

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
