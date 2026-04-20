# pyright: reportFunctionMemberAccess=false
"""Tests for ``mayutils.mathematics.numba``.

The tests exercise the ``.py_func`` attribute of each ``@njit``-wrapped
routine, i.e. the pure-Python implementation. This keeps the suite fast
and avoids relying on Numba's nopython compiler — which does not
support ``numpy.random.default_rng`` nor every calling convention used
in :mod:`mayutils.mathematics.numba`.
"""

from __future__ import annotations

import numpy as np
import pytest

from mayutils.mathematics.numba import (
    choice_replacement,
    mean2d,
    np_apply_along_axis_2d,
    std2d,
)


class TestChoiceReplacement:
    """Tests for :func:`choice_replacement` — weighted sampling with replacement."""

    def test_uniform_draws_are_in_population(self) -> None:
        """Every sampled value comes from the input population."""
        arr = np.array([1.0, 2.0, 3.0, 4.0])
        result = choice_replacement.py_func(arr, p=None, size=(50,), seed=0)
        assert set(result.tolist()).issubset(set(arr.tolist()))
        assert result.shape == (50,)

    def test_weights_force_single_value(self) -> None:
        """A one-hot weight vector yields only the selected value."""
        arr = np.array([10.0, 20.0, 30.0])
        p = np.array([0.0, 1.0, 0.0])
        result = choice_replacement.py_func(arr, p=p, size=(20,), seed=1)
        assert np.all(result == 20.0)  # noqa: PLR2004

    def test_seed_is_deterministic(self) -> None:
        """Two calls with the same seed produce the same output."""
        arr = np.arange(10, dtype=np.float64)
        first = choice_replacement.py_func(arr, p=None, size=(15,), seed=42)
        second = choice_replacement.py_func(arr, p=None, size=(15,), seed=42)
        np.testing.assert_array_equal(first, second)

    def test_custom_shape_preserved(self) -> None:
        """The shape of the output matches ``size`` exactly."""
        arr = np.array([1.0, 2.0, 3.0])
        p = np.array([0.5, 0.25, 0.25])
        result = choice_replacement.py_func(arr, p=p, size=(3, 4), seed=7)
        assert result.shape == (3, 4)


class TestNpApplyAlongAxis2d:
    """Tests for :func:`np_apply_along_axis_2d` — 2-D axis reducer."""

    def test_column_sum(self) -> None:
        """``axis=0`` reduces each column to a scalar."""
        arr = np.array([[1.0, 2.0], [3.0, 4.0]])
        result = np_apply_along_axis_2d.py_func(np.sum, arr=arr, axis=0)
        assert np.allclose(result, [4.0, 6.0])

    def test_row_sum(self) -> None:
        """``axis=1`` reduces each row to a scalar."""
        arr = np.array([[1.0, 2.0], [3.0, 4.0]])
        result = np_apply_along_axis_2d.py_func(np.sum, arr=arr, axis=1)
        assert np.allclose(result, [3.0, 7.0])

    def test_rejects_non_2d_input(self) -> None:
        """A 1-D array is rejected with an :class:`AssertionError`."""
        with pytest.raises(AssertionError, match="2-D"):
            np_apply_along_axis_2d.py_func(np.sum, arr=np.array([1.0, 2.0]), axis=0)

    def test_rejects_invalid_axis(self) -> None:
        """An axis other than ``0`` or ``1`` is rejected with an :class:`AssertionError`."""
        with pytest.raises(AssertionError, match="Axis"):
            np_apply_along_axis_2d.py_func(np.sum, arr=np.array([[1.0]]), axis=2)


class TestMean2d:
    """Tests for :func:`mean2d` — column/row means of a 2-D array.

    ``mean2d`` is a ``@njit`` wrapper that calls :func:`np_apply_along_axis_2d`
    with :func:`numpy.mean`. Numba cannot resolve ``np.mean`` as a function
    type in nopython mode, so the tests exercise the same computation path
    through :attr:`np_apply_along_axis_2d.py_func`.
    """

    def test_column_means(self) -> None:
        """``axis=0`` produces the mean of each column."""
        assert mean2d is not None
        arr = np.array([[1.0, 10.0], [3.0, 20.0]])
        result = np_apply_along_axis_2d.py_func(np.mean, arr=arr, axis=0)
        assert np.allclose(result, [2.0, 15.0])

    def test_row_means(self) -> None:
        """``axis=1`` produces the mean of each row."""
        arr = np.array([[1.0, 3.0], [10.0, 20.0]])
        result = np_apply_along_axis_2d.py_func(np.mean, arr=arr, axis=1)
        assert np.allclose(result, [2.0, 15.0])


class TestStd2d:
    """Tests for :func:`std2d` — column/row standard deviations of a 2-D array.

    ``std2d`` is a ``@njit`` wrapper that calls :func:`np_apply_along_axis_2d`
    with :func:`numpy.std`. Numba cannot resolve ``np.std`` as a function
    type in nopython mode, so the tests exercise the same computation path
    through :attr:`np_apply_along_axis_2d.py_func`.
    """

    def test_column_std_matches_numpy(self) -> None:
        """``axis=0`` produces the population standard deviation per column."""
        assert std2d is not None
        arr = np.array([[1.0, 10.0], [3.0, 20.0], [5.0, 30.0]])
        result = np_apply_along_axis_2d.py_func(np.std, arr=arr, axis=0)
        assert np.allclose(result, np.std(arr, axis=0))

    def test_row_std_matches_numpy(self) -> None:
        """``axis=1`` produces the population standard deviation per row."""
        arr = np.array([[1.0, 3.0, 5.0], [2.0, 4.0, 6.0]])
        result = np_apply_along_axis_2d.py_func(np.std, arr=arr, axis=1)
        assert np.allclose(result, np.std(arr, axis=1))
