"""Tests for ``mayutils.environment.memoisation.decorators``.

Covers the function-decoration paths of :class:`lru_cache` and
:class:`cache`: memoisation, hit/miss accounting, clearing, per-call
deletion, key prefixing, backend selection (memory vs file), warm-start
persistence, and TTL expiry. The class-decoration path is left
unexercised (see module notes), and two pre-existing bugs are pinned with
``TypeError`` assertions rather than fixed.

Requires the ``datetime`` extra (pendulum) plus the DataFrame extras
pulled in by the file-backed store.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest

pytest.importorskip("pendulum")
pytest.importorskip("pandas")
pytest.importorskip("polars")

from mayutils.environment.memoisation.decorators import cache, lru_cache
from mayutils.environment.memoisation.files import FileStore
from mayutils.environment.memoisation.memory import MemoryStore
from mayutils.objects.datetime import Duration

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class _Counter:
    """Records how many times the wrapped computation actually ran.

    A tiny stand-in for an expensive function so tests can assert that
    memoisation collapses repeated calls into a single invocation.
    """

    def __init__(self) -> None:
        """Initialise the call count to zero."""
        self.calls = 0

    def double(self, value: int) -> int:
        """Double ``value`` and record the invocation.

        Parameters
        ----------
        value
            The integer to double.

        Returns
        -------
            ``value * 2``.
        """
        self.calls += 1
        return value * 2


class TestLruCacheMemoisation:
    """Tests for :class:`lru_cache` decorating a function."""

    def test_bare_form_memoises(self) -> None:
        """``@lru_cache`` serves a repeated call from the cache."""
        counter = _Counter()

        @lru_cache
        def double(value: int) -> int:
            return counter.double(value)

        assert double(3) == 6  # noqa: PLR2004
        assert double(3) == 6  # noqa: PLR2004
        assert counter.calls == 1

    def test_different_args_invoke_again(self) -> None:
        """Distinct arguments miss the cache and re-invoke the function."""
        counter = _Counter()

        @lru_cache
        def double(value: int) -> int:
            return counter.double(value)

        double(1)
        double(2)
        assert counter.calls == 2  # noqa: PLR2004

    def test_parameterised_form_memoises(self) -> None:
        """``@lru_cache(maxsize=..., typed=...)`` also memoises."""
        counter = _Counter()

        # The parameterised form's static return type is erased by flexwrap,
        # so cast to Any to keep the call type-clean.
        double = cast("Any", lru_cache(maxsize=8, typed=True)(counter.double))

        double(5)
        double(5)
        assert counter.calls == 1

    def test_cache_info_tracks_hits_and_misses(self) -> None:
        """``cache_info`` reports the underlying LRU hit/miss counts."""

        @lru_cache
        def square(value: int) -> int:
            return value * value

        square(2)  # miss
        square(2)  # hit
        info = square.cache_info()
        assert info.hits == 1
        assert info.misses == 1

    def test_cache_clear_resets_counters(self) -> None:
        """``cache_clear`` empties the cache and zeroes the counters."""

        @lru_cache
        def square(value: int) -> int:
            return value * value

        square(2)
        square.cache_clear()
        assert square.cache_info().hits == 0
        assert square.cache_info().currsize == 0

    def test_bypass_cache_invokes_directly(self) -> None:
        """``bypass_cache`` calls the wrapped function without touching the LRU."""
        counter = _Counter()

        @lru_cache
        def double(value: int) -> int:
            return counter.double(value)

        assert double.bypass_cache(4) == 8  # noqa: PLR2004
        assert double.cache_info().misses == 0  # cache was untouched

    def test_metadata_preserved(self) -> None:
        """The wrapped function keeps its ``__name__`` and docstring."""

        @lru_cache
        def labelled(value: int) -> int:
            """Return the value unchanged.

            Returns
            -------
                The input value.
            """
            return value

        # ``update_wrapper`` copies these at runtime; the decorator
        # instance type does not declare them, so inspect through Any.
        decorated = cast("Any", labelled)
        assert decorated.__name__ == "labelled"
        assert decorated.__doc__ is not None
        assert "Return the value unchanged." in decorated.__doc__


class TestLruCacheBypassKeywordBug:
    """Pins the broken ``cache=False`` bypass keyword on :class:`lru_cache`."""

    def test_cache_false_keyword_raises_typeerror(self) -> None:
        """KNOWN BUG: ``cache=False`` is forwarded to the wrapped function.

        The docstring (and its un-collected doctest) advertise
        ``f(..., cache=False)`` as a per-call bypass, but ``__call__``
        forwards the keyword straight into ``functools.lru_cache``'s
        wrapper, which passes it on to the wrapped function. Functions
        without a ``cache`` parameter therefore raise ``TypeError``. This
        test pins the current (buggy) behaviour rather than fixing it.
        """

        @lru_cache
        def double(value: int) -> int:
            return value * 2

        with pytest.raises(expected_exception=TypeError, match="cache"):
            double(3, cache=False)


class TestCacheMemoryBackend:
    """Tests for :class:`cache` defaulting to an in-memory store."""

    def test_default_store_is_memory(self) -> None:
        """Without ``suffix`` or ``persist`` the backend is a :class:`MemoryStore`."""

        @cache
        def square(value: int) -> int:
            return value * value

        assert isinstance(square.store, MemoryStore)

    def test_bare_form_memoises(self) -> None:
        """``@cache`` serves a repeated call from the in-memory store."""
        counter = _Counter()

        @cache
        def double(value: int) -> int:
            return counter.double(value)

        assert double(3) == 6  # noqa: PLR2004
        assert double(3) == 6  # noqa: PLR2004
        assert counter.calls == 1

    def test_different_args_invoke_again(self) -> None:
        """Distinct arguments miss and re-invoke the wrapped function."""
        counter = _Counter()

        @cache
        def double(value: int) -> int:
            return counter.double(value)

        double(1)
        double(2)
        assert counter.calls == 2  # noqa: PLR2004

    def test_cache_info_tracks_hits_and_misses(self) -> None:
        """``cache_info`` reports the store's hit/miss counts."""

        @cache
        def square(value: int) -> int:
            return value * value

        square(2)  # miss
        square(2)  # hit
        info = square.cache_info()
        assert info.hits == 1
        assert info.misses == 1

    def test_cache_clear_empties_store(self) -> None:
        """``cache_clear`` removes every entry."""

        @cache
        def square(value: int) -> int:
            return value * value

        square(2)
        square.cache_clear()
        assert square.cache_info().currsize == 0

    def test_delete_cache_removes_single_entry(self) -> None:
        """``delete_cache`` drops the entry for a specific call signature."""
        counter = _Counter()

        @cache
        def double(value: int) -> int:
            return counter.double(value)

        double(5)
        assert double.delete_cache(5) is True
        double(5)  # recomputed after deletion
        assert counter.calls == 2  # noqa: PLR2004

    def test_delete_cache_absent_returns_false(self) -> None:
        """Deleting an uncached signature returns ``False``."""

        @cache
        def square(value: int) -> int:
            return value * value

        assert square.delete_cache(99) is False

    def test_bypass_cache_skips_store(self) -> None:
        """``bypass_cache`` recomputes without consulting or updating the store."""
        counter = _Counter()

        @cache
        def double(value: int) -> int:
            return counter.double(value)

        double(2)  # cached
        assert double.bypass_cache(2) == 4  # noqa: PLR2004
        assert counter.calls == 2  # noqa: PLR2004

    def test_maxsize_bounds_memory_store(self) -> None:
        """``maxsize`` is forwarded to the in-memory store's LRU bound."""

        @cache(maxsize=2)
        def identity(value: int) -> int:
            return value

        identity(1)
        identity(2)
        identity(3)
        assert identity.cache_info().currsize == 2  # noqa: PLR2004


class TestCacheKeys:
    """Tests for :class:`cache` key generation and prefixing."""

    def test_func_key_is_deterministic_hex(self) -> None:
        """``func_key`` returns a stable string for a given signature."""

        @cache
        def square(value: int) -> int:
            return value * value

        assert square.func_key(3) == square.func_key(3)

    def test_key_prefix_constructor_argument(self) -> None:
        """A ``key_prefix`` is exposed and prepended to the key with ``--``."""

        @cache(key_prefix="demo")
        def square(value: int) -> int:
            return value * value

        assert square.key_prefix == "demo"
        assert square.func_key(3).startswith("demo--")

    def test_key_prefix_setter(self) -> None:
        """The ``key_prefix`` setter updates subsequent key computation."""

        @cache
        def square(value: int) -> int:
            return value * value

        square.key_prefix = "v2"
        assert square.key_prefix == "v2"
        assert square.func_key(3).startswith("v2--")


class TestCacheFileBackend:
    """Tests for :class:`cache` selecting a file-backed store."""

    def test_suffix_selects_file_store(self, tmp_path: Path) -> None:
        """An explicit ``suffix`` routes to a :class:`FileStore`."""

        @cache(suffix="pkl", cache_folder=tmp_path)
        def square(value: int) -> int:
            return value * value

        assert isinstance(square.store, FileStore)

    def test_persist_selects_file_store(self, tmp_path: Path) -> None:
        """``persist=True`` (no suffix) also routes to a :class:`FileStore`."""

        @cache(persist=True, cache_folder=tmp_path)
        def square(value: int) -> int:
            return value * value

        assert isinstance(square.store, FileStore)

    def test_file_backed_memoises_and_persists(self, tmp_path: Path) -> None:
        """A file-backed cache serves repeats and writes a file to disk."""
        counter = _Counter()

        @cache(suffix="pkl", cache_folder=tmp_path)
        def double(value: int) -> int:
            return counter.double(value)

        assert double(3) == 6  # noqa: PLR2004
        assert double(3) == 6  # noqa: PLR2004
        assert counter.calls == 1
        assert double.get_path(3).is_file()

    def test_get_path_requires_file_backend(self) -> None:
        """``get_path`` on a memory-backed cache raises :class:`TypeError`."""

        @cache
        def square(value: int) -> int:
            return value * value

        with pytest.raises(expected_exception=TypeError, match="file-backed"):
            square.get_path(3)


class TestCachePersistence:
    """Tests for warm-start persistence of memory-backed :class:`cache`."""

    def test_save_then_warm_start_from_path(self, tmp_path: Path) -> None:
        """A saved cache warm-starts a fresh decorator constructed with ``path``.

        The cache key embeds the wrapped function's ``__name__``, so the
        warm-started decorator must wrap an identically-named function for
        the persisted entry to be found — the realistic same-function,
        new-process scenario. The second definition deliberately reuses the
        name ``double``.
        """
        path = tmp_path / "cache.pkl"
        counter = _Counter()

        @cache
        def double(value: int) -> int:
            return counter.double(value)

        double(4)
        double.save(path)

        # The cache key embeds ``__name__``, so the warm-started decorator
        # must wrap an identically-named function to find the persisted
        # entry — the realistic same-function, new-process scenario.
        warm_counter = _Counter()

        def warm_double(value: int) -> int:
            return warm_counter.double(value)

        warm_double.__name__ = "double"
        warm_cache = cache(path=path)(warm_double)

        assert warm_cache(4) == 8  # noqa: PLR2004
        assert warm_counter.calls == 0  # served from the warm-started store

    def test_persist_path_writes_on_each_put(self, tmp_path: Path) -> None:
        """A memory cache configured with ``path`` flushes to disk on miss."""
        path = tmp_path / "cache.pkl"

        @cache(path=path)
        def square(value: int) -> int:
            return value * value

        square(3)
        assert path.is_file()
        assert square.persist_path == path

    def test_persist_path_none_for_plain_memory_cache(self) -> None:
        """A plain in-memory cache reports ``None`` for its persist path."""

        @cache
        def square(value: int) -> int:
            return value * value

        assert square.persist_path is None

    def test_save_requires_memory_backend(self, tmp_path: Path) -> None:
        """``save`` on a file-backed cache raises :class:`TypeError`."""

        @cache(suffix="pkl", cache_folder=tmp_path)
        def square(value: int) -> int:
            return value * value

        with pytest.raises(expected_exception=TypeError, match="in-memory"):
            square.save(tmp_path / "out.pkl")

    def test_load_store_merges_entries(self, tmp_path: Path) -> None:
        """``load_store`` merges a saved pickle into a live memory cache.

        As with warm-start, the merged entry is only found when the
        receiving cache wraps an identically-named function, so the
        receiving function's ``__name__`` is set to match.
        """
        path = tmp_path / "cache.pkl"
        counter = _Counter()

        @cache
        def double(value: int) -> int:
            return counter.double(value)

        double(7)
        double.save(path)

        fresh_counter = _Counter()

        def fresh_double(value: int) -> int:
            return fresh_counter.double(value)

        fresh_double.__name__ = "double"
        fresh_cache = cache(fresh_double)

        fresh_cache.load_store(path)
        assert fresh_cache(7) == 14  # noqa: PLR2004
        assert fresh_counter.calls == 0


class TestCacheTTL:
    """Tests for TTL expiry on a memory-backed :class:`cache`."""

    def test_expired_entry_recomputes(self) -> None:
        """An entry past its TTL is recomputed on the next call."""
        counter = _Counter()

        @cache(ttl=Duration(seconds=-1))
        def double(value: int) -> int:
            return counter.double(value)

        double(2)
        double(2)
        assert counter.calls == 2  # noqa: PLR2004

    def test_live_entry_served_within_ttl(self) -> None:
        """An entry within its TTL is served from the cache."""
        counter = _Counter()

        @cache(ttl=Duration(hours=1))
        def double(value: int) -> int:
            return counter.double(value)

        double(2)
        double(2)
        assert counter.calls == 1


class TestCacheRefreshBug:
    """Pins the broken ``refresh`` method on :class:`cache`."""

    def test_refresh_raises_typeerror(self) -> None:
        """KNOWN BUG: ``refresh`` forwards ``refresh=True`` to the wrapped function.

        ``refresh`` calls ``self.bypass_cache(*args, refresh=True, **kwargs)``,
        which passes the ``refresh`` keyword straight to the wrapped
        callable. Functions without a ``refresh`` parameter raise
        ``TypeError``. This test pins the current behaviour; the
        accompanying doctest is never collected because ``flexwrap`` turns
        ``cache`` into a plain function, hiding the method docstrings from
        the doctest finder.
        """

        @cache
        def square(value: int) -> int:
            return value * value

        with pytest.raises(expected_exception=TypeError, match="refresh"):
            square.refresh(3)


class TestDecoratorFactories:
    """Confirms the module exports usable decorator factories."""

    @pytest.mark.parametrize("factory", [cache, lru_cache])
    def test_factories_are_callable(self, factory: Callable[..., object]) -> None:
        """Both ``cache`` and ``lru_cache`` are callable decorator factories."""
        assert callable(factory)
