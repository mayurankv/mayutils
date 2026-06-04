"""Icicle chart trace built from nested dictionaries."""

from collections.abc import Mapping
from typing import Any, Self

from mayutils.core.extras import may_require_extras
from mayutils.objects.types import RecursiveMapping

with may_require_extras():
    import plotly.graph_objects as go


def build_icicle(
    icicle_dict: RecursiveMapping[str, float],
    /,
) -> tuple[list[str], list[str], list[str], list[float]]:
    """
    Flatten a nested mapping into parallel lists for :class:`go.Icicle`.

    Walks *icicle_dict* recursively, aggregating leaf values upward so
    that each parent node's value equals the sum of its children.

    Parameters
    ----------
    icicle_dict
        Nested mapping where leaves are numeric values and intermediate
        nodes are sub-mappings.

    Returns
    -------
        ``(ids, labels, parents, values)`` lists ready for
        :class:`go.Icicle`.

    See Also
    --------
    Icicle.from_dict : Convenience constructor wrapping this function.

    Examples
    --------
    >>> icicle_dict = build_icicle({"a": {"b": 1, "c": 2}})
    """
    node_values: dict[str, float] = {}

    def calculate_values(
        d: RecursiveMapping[str, float],
        /,
        *,
        path: str = "",
    ) -> float:
        """
        Recursively sum leaf values and populate *node_values*.

        Walks the nested mapping depth-first, storing each node's
        aggregate value in the outer ``node_values`` dict.

        Parameters
        ----------
        d
            Current sub-mapping to process.
        path
            Slash-delimited path from the root to *d*.

        Returns
        -------
            Aggregate value of *d* (sum of all descendant leaves).

        See Also
        --------
        build_lists : Companion that flattens computed values.

        Examples
        --------
        >>> output = calculate_values({"a": 1, "b": 2})
        """
        if path in node_values:
            return node_values[path]

        total = 0.0
        for key, value in d.items():
            new_path = f"{path}/{key}" if path else key
            if isinstance(value, Mapping):
                node_value = calculate_values(value, path=new_path)  # ty:ignore[invalid-argument-type]
                total += node_value

            else:
                total += value
                node_values[new_path] = value

        node_values[path] = total

        return total

    ids: list[str] = []
    labels: list[str] = []
    parents: list[str] = []
    values: list[float] = []

    def build_lists(
        d: RecursiveMapping[str, float],
        /,
        *,
        parent_path: str = "",
    ) -> None:
        """
        Recursively append ids, labels, parents, and values.

        Walks the nested mapping and appends one entry per node to the
        outer ``ids``, ``labels``, ``parents``, and ``values`` lists.

        Parameters
        ----------
        d
            Current sub-mapping to process.
        parent_path
            Slash-delimited path of the parent node.

        See Also
        --------
        calculate_values : Must be called first to populate node values.

        Examples
        --------
        >>> output = build_lists({"a": 1})
        """
        for key, value in d.items():
            current_path = f"{parent_path}/{key}" if parent_path else key

            ids.append(current_path)
            labels.append(key)
            parents.append(parent_path)
            values.append(node_values[current_path])

            if isinstance(value, dict):
                build_lists(
                    value,
                    parent_path=current_path,
                )

    calculate_values(icicle_dict)
    build_lists(icicle_dict)

    return (
        ids,
        labels,
        parents,
        values,
    )


class Icicle(go.Icicle):
    """
    Icicle chart trace constructed from a nested dictionary.

    Wraps :class:`plotly.graph_objects.Icicle` and provides a
    :meth:`from_dict` factory that flattens a recursive mapping into
    the parallel ``ids / labels / parents / values`` lists that Plotly
    expects.

    See Also
    --------
    build_icicle : Low-level flattening helper.

    Examples
    --------
    >>> from mayutils.visualisation.graphs.plotly.traces.icicle import Icicle
    >>> trace = Icicle.from_dict({"a": {"b": 1}})
    """

    @classmethod
    def from_dict(
        cls,
        icicle_dict: RecursiveMapping[str, float],
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        """
        Build an icicle trace from a nested dictionary.

        Delegates to :func:`build_icicle` to flatten the hierarchy and
        passes the result to the constructor.

        Parameters
        ----------
        icicle_dict
            Nested mapping where leaves are numeric values.
        **kwargs
            Forwarded to :class:`go.Icicle`.

        Returns
        -------
        Self
            A new ``Icicle`` trace.

        See Also
        --------
        build_icicle : Flattening helper.

        Examples
        --------
        >>> trace = Icicle.from_dict({"root": {"a": 1, "b": 2}})
        """
        ids, labels, parents, values = build_icicle(icicle_dict)

        return cls(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            **kwargs,
        )
