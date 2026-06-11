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
