"""Tests for ``mayutils.mathematics.numpy``."""

from __future__ import annotations

import numpy as np
import pytest

from mayutils.mathematics.numpy import (
    broadcast_to_array,
    check_lengths,
    dictionary_lookup,
    merge_detail,
)


class TestBroadcastToArray:
    """Tests for :func:`broadcast_to_array` — scalar/sequence to ndarray."""

    def test_scalar_broadcasts_to_length_n(self) -> None:
        """A scalar is tiled to fill an array of the requested length."""
        result = broadcast_to_array(value=5.0, n=4)
        assert result.shape == (4,)
        assert (result == 5.0).all()  # noqa: PLR2004

    def test_none_fills_object_array(self) -> None:
        """``None`` produces an object-dtype array where every element is ``None``."""
        result = broadcast_to_array(value=None, n=3)
        assert result.dtype == object
        assert all(v is None for v in result)

    def test_sequence_of_length_n_converted_directly(self) -> None:
        """A sequence whose length matches *n* is converted as-is."""
        result = broadcast_to_array(value=[1, 2, 3], n=3)
        assert (result == np.array([1, 2, 3])).all()

    def test_ndarray_passed_through_unchanged(self) -> None:
        """An ndarray is returned by identity without copying."""
        arr = np.array([1.5, 2.5])
        result = broadcast_to_array(value=arr, n=2)
        assert result is arr

    def test_string_broadcast_to_every_element(self) -> None:
        """A string (not a generic sequence) is broadcast to every slot."""
        result = broadcast_to_array(value="ab", n=3)
        assert result.shape == (3,)
        assert (result == "ab").all()


class TestMergeDetail:
    """Tests for :func:`merge_detail` — per-group detail accumulation."""

    def test_fills_masked_positions(self) -> None:
        """Values from *detail_out* are written into the masked positions."""
        template = np.zeros(4)
        detail: dict[str, np.ndarray] = {}
        mask = np.array([True, False, True, False])
        merge_detail(
            detail=detail,
            detail_out={"x": np.array([10.0, 30.0])},
            mask=mask,
            template=template,
        )
        assert (detail["x"][mask] == np.array([10.0, 30.0])).all()

    def test_accumulates_across_groups(self) -> None:
        """Two successive calls build the full array from non-overlapping masks."""
        template = np.zeros(4)
        detail: dict[str, np.ndarray] = {}
        mask_a = np.array([True, True, False, False])
        mask_b = np.array([False, False, True, True])
        merge_detail(
            detail=detail,
            detail_out={"x": np.array([1.0, 2.0])},
            mask=mask_a,
            template=template,
        )
        merge_detail(
            detail=detail,
            detail_out={"x": np.array([3.0, 4.0])},
            mask=mask_b,
            template=template,
        )
        assert (detail["x"] == np.array([1.0, 2.0, 3.0, 4.0])).all()

    def test_2d_values_use_template_shape(self) -> None:
        """2-D values create a full-shape accumulator matching the template."""
        template = np.zeros((3, 2))
        detail: dict[str, np.ndarray] = {}
        mask = np.array([True, False, True])
        merge_detail(
            detail=detail,
            detail_out={"m": np.array([[1.0, 2.0], [5.0, 6.0]])},
            mask=mask,
            template=template,
        )
        assert detail["m"].shape == (3, 2)
        assert (detail["m"][mask] == np.array([[1.0, 2.0], [5.0, 6.0]])).all()

    def test_mismatched_trailing_dimension_raises(self) -> None:
        """2-D values whose trailing dimension differs from the template raise ValueError."""
        template = np.zeros((3, 2))
        detail: dict[str, np.ndarray] = {}
        mask = np.array([True, False, True])
        with pytest.raises(ValueError, match="broadcast"):
            merge_detail(
                detail=detail,
                detail_out={"m": np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])},
                mask=mask,
                template=template,
            )


class TestDictionaryLookup:
    """Tests for :func:`dictionary_lookup` — vectorised dict mapping."""

    def test_maps_keys_through_dictionary(self) -> None:
        """Every element of the lookup array is replaced by its dict value."""
        result = dictionary_lookup(
            lookup=["a", "b", "a"],
            dictionary={"a": 1, "b": 2},
            default_value=0,
        )
        assert (result == np.array([1, 2, 1])).all()

    def test_missing_key_uses_default(self) -> None:
        """Keys absent from the dict are replaced by *default_value*."""
        result = dictionary_lookup(
            lookup=["a", "z"],
            dictionary={"a": 1},
            default_value=-1,
        )
        assert (result == np.array([1, -1])).all()


class TestCheckLengths:
    """Tests for :func:`check_lengths` — first-dimension length guard."""

    def test_matching_lengths_pass(self) -> None:
        """No exception is raised when all arrays share the same length."""
        check_lengths(a=np.zeros(3), b=np.ones(3))

    def test_mismatched_lengths_raise_with_names(self) -> None:
        """A ``ValueError`` naming each array and its length is raised on mismatch."""
        with pytest.raises(ValueError, match=r"a=3.*b=2"):
            check_lengths(a=np.zeros(3), b=np.ones(2))
