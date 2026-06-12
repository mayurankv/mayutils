"""
Provide deterministic experiment assignment from stable identifiers.

Hash stable subject identifiers into experiment buckets so the same
subject always receives the same experiment arm with no stored state,
database lookups, or query-time randomness. Each experiment salts the
hash with its own name, making assignments pseudo-independent across
experiments. Arm configurations are versioned by effective date and
resolved per subject timestamp via
:func:`mayutils.objects.versions.apply_func_to_versioned_value`.

See Also
--------
hashlib.sha256 : Hash primitive behind the deterministic assignment.
mayutils.objects.versions : Time-effective configuration resolution.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from mayutils.core.extras import may_require_extras
from mayutils.objects.versions import apply_func_to_versioned_value

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import ArrayLike, NDArray

type ExperimentConfig = tuple[tuple[str, float], ...]
type ExperimentsOutcomes = dict[str, NDArray[np.str_]]


def hash_to_experiment_value(
    *,
    ids: ArrayLike | NDArray[np.int64],
    experiment_name: str,
    max_value: int,
) -> NDArray[np.int64]:
    """
    Deterministically map identifiers to integers in ``[0, max_value)``.

    Uses SHA-256 of ``"{experiment_name}_{id}"`` to produce a
    reproducible hash that is independent across experiments.

    The SHA-256 digest is converted to an integer and taken modulo
    *max_value*, guaranteeing a stable, pseudo-random integer for each
    (experiment_name, id) pair regardless of execution environment.

    Parameters
    ----------
    ids : ArrayLike | NDArray[np.int64]
        Stable subject identifiers.
    experiment_name : str
        Name of the experiment (used as a hash salt).
    max_value : int
        Upper bound of the output range (exclusive).

    Returns
    -------
    NDArray[np.int64]
        Hash value per identifier in ``[0, max_value)``.

    See Also
    --------
    get_experiment_outcomes : Maps hash values to named experiment arms.
    assign_experiment : End-to-end assignment combining hashing and outcome resolution.

    Examples
    --------
    >>> import numpy as np
    >>> from mayutils.mathematics.experiments import hash_to_experiment_value
    >>> hash_to_experiment_value(ids=[1, 2, 3], experiment_name="test", max_value=100)
    array([59, 63,  9])
    """
    with may_require_extras():
        import numpy as np

    ids = np.asarray(ids, dtype=np.int64)

    return np.fromiter(
        (
            int(
                hashlib.sha256(f"{experiment_name}_{id_value}".encode()).hexdigest(),
                16,
            )
            % max_value
            for id_value in ids
        ),
        dtype=np.int64,
        count=ids.size,
    )


def get_experiment_outcomes(
    *,
    array: NDArray[np.int64],
    version_value: tuple[tuple[str, float], ...],
    max_value: int,
) -> NDArray[np.str_]:
    """
    Map hashed experiment values to named outcome buckets by proportion.

    Normalises the proportions in *version_value*, computes cumulative
    thresholds scaled to *max_value*, and uses ``np.searchsorted`` to
    assign each hash value to the appropriate arm name.

    Parameters
    ----------
    array : NDArray[np.int64]
        Integer hash values in [0, max_value) for each subject.
    version_value : tuple[tuple[str, float], ...]
        Experiment arms as (name, proportion) pairs. Proportions are
        normalised, so they need not sum to 1.
    max_value : int
        Upper bound of the hash space used to define bucket thresholds.

    Returns
    -------
    NDArray[np.str_]
        Experiment outcome name assigned to each subject.

    See Also
    --------
    hash_to_experiment_value : Produces the integer hash array consumed by this function.
    assign_experiment : Combines hashing and outcome resolution into a single call.
    mayutils.objects.versions.apply_func_to_versioned_value : Applies versioned functions over timestamped arrays.

    Examples
    --------
    >>> import numpy as np
    >>> from mayutils.mathematics.experiments import get_experiment_outcomes
    >>> config = (("control", 0.5), ("treatment", 0.5))
    >>> get_experiment_outcomes(array=np.array([0, 25, 50, 75], dtype=np.int64), version_value=config, max_value=100)
    array(['control', 'control', 'treatment', 'treatment'], dtype='<U9')
    """
    with may_require_extras():
        import numpy as np

    names, proportions = zip(*version_value, strict=False)
    proportions_normalised = np.asarray(proportions, dtype=np.float64)
    proportions_normalised = proportions_normalised / proportions_normalised.sum()

    thresholds = np.cumsum(proportions_normalised) * max_value
    thresholds[-1] = max_value  # avoid floating-point edge case

    bucket_indices = np.searchsorted(thresholds, array, side="right")
    bucket_indices = np.clip(bucket_indices, 0, len(names) - 1)

    return np.array(names)[bucket_indices]


def assign_experiment(
    *,
    experiment_name: str,
    ids: ArrayLike | NDArray[np.int64],
    timestamps: ArrayLike | NDArray[np.datetime64],
    max_value: int,
    experiments: dict[str, dict[np.datetime64, ExperimentConfig]],
) -> NDArray[np.str_]:
    """
    Assign experiment outcomes vectorised, selecting config by timestamp.

    Hashes each identifier, resolves the time-appropriate experiment
    config, and maps hash values to named outcome buckets.

    Combines :func:`hash_to_experiment_value` with
    :func:`mayutils.objects.versions.apply_func_to_versioned_value` so
    that arm configurations can change over time without altering
    existing subject assignments for dates already covered.

    Parameters
    ----------
    experiment_name : str
        Key into *experiments* and salt for the hash function.
    ids : ArrayLike | NDArray[np.int64]
        Stable subject identifiers.
    timestamps : ArrayLike | NDArray[np.datetime64]
        Timestamp per subject, used to select the active config version.
    max_value : int
        Upper bound of the hash space.
    experiments : dict[str, dict[np.datetime64, ExperimentConfig]]
        Full experiment registry keyed by experiment name, then
        effective date.

    Returns
    -------
    NDArray[np.str_]
        Experiment arm name assigned to each subject.

    See Also
    --------
    parse_experiments : Assign outcomes for all experiments in the registry at once.
    hash_to_experiment_value : Produces the per-subject hash values used internally.
    get_experiment_outcomes : Maps hash values to arm names for a single version config.

    Examples
    --------
    >>> import numpy as np
    >>> from mayutils.mathematics.experiments import assign_experiment
    >>> experiments = {
    ...     "my_exp": {
    ...         np.datetime64("2026-01-01"): (("control", 0.5), ("treatment", 0.5)),
    ...     }
    ... }
    >>> assign_experiment(
    ...     experiment_name="my_exp",
    ...     ids=np.array([1, 2], dtype=np.int64),
    ...     timestamps=np.array(["2026-02-01", "2026-02-01"], dtype="datetime64[us]"),
    ...     max_value=100,
    ...     experiments=experiments,
    ... )
    array(['treatment', 'treatment'], dtype='<U9')
    """
    with may_require_extras():
        import numpy as np

    ids = np.asarray(ids, dtype=np.int64)
    timestamps = np.asarray(timestamps, dtype="datetime64[us]")

    experiment_rv = hash_to_experiment_value(
        ids=ids,
        experiment_name=experiment_name,
        max_value=max_value,
    )

    versioned_experiment = experiments[experiment_name]

    max_outcome_len = max(len(name) for config in versioned_experiment.values() for name, _ in config)

    return apply_func_to_versioned_value(
        array=experiment_rv,
        timestamps=timestamps,
        versioned_value=versioned_experiment,
        func=lambda array, version_value: get_experiment_outcomes(
            array=array,
            version_value=version_value,
            max_value=max_value,
        ),
        dtype=f"<U{max_outcome_len}",
    )


def parse_experiments(
    *,
    ids: ArrayLike | NDArray[np.int64],
    timestamps: ArrayLike | NDArray[np.datetime64],
    experiments: dict[str, dict[np.datetime64, ExperimentConfig]],
    max_value: int,
) -> ExperimentsOutcomes:
    """
    Derive pseudo-independent experiment outcomes from identifiers.

    Each experiment is hashed independently from the same identifier.
    The experiment config is selected based on the most recent
    effective date <= the subject timestamp.

    Iterates over all experiments in the registry and delegates to
    :func:`assign_experiment` for each, returning a dict keyed by
    experiment name.

    Parameters
    ----------
    ids : ArrayLike | NDArray[np.int64]
        Stable subject identifiers.
    timestamps : ArrayLike | NDArray[np.datetime64]
        Timestamp per subject for version resolution.
    experiments : dict[str, dict[np.datetime64, ExperimentConfig]]
        Full experiment registry keyed by experiment name, then
        effective date.
    max_value : int
        Upper bound of the hash space.

    Returns
    -------
    ExperimentsOutcomes
        Mapping from experiment name to an array of assigned arm names.

    See Also
    --------
    assign_experiment : Assigns outcomes for a single named experiment.
    hash_to_experiment_value : Underlying hash function providing per-experiment isolation.

    Examples
    --------
    >>> import numpy as np
    >>> from mayutils.mathematics.experiments import parse_experiments
    >>> experiments = {
    ...     "my_exp": {
    ...         np.datetime64("2026-01-01"): (("control", 0.5), ("treatment", 0.5)),
    ...     }
    ... }
    >>> result = parse_experiments(
    ...     ids=np.array([1, 2], dtype=np.int64),
    ...     timestamps=np.array(["2026-02-01", "2026-02-01"], dtype="datetime64[us]"),
    ...     experiments=experiments,
    ...     max_value=100,
    ... )
    >>> result["my_exp"]
    array(['treatment', 'treatment'], dtype='<U9')
    """
    with may_require_extras():
        import numpy as np

    ids = np.asarray(ids, dtype=np.int64)
    timestamps = np.asarray(timestamps, dtype="datetime64[us]")

    return {
        experiment_name: assign_experiment(
            experiment_name=experiment_name,
            ids=ids,
            timestamps=timestamps,
            experiments=experiments,
            max_value=max_value,
        )
        for experiment_name in experiments
    }
