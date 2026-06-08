"""Tests for ``mayutils.environment.benchmarking``."""

from __future__ import annotations

import pytest

from mayutils.environment import benchmarking
from mayutils.environment.benchmarking import timing


@pytest.fixture
def captured_logs(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Capture messages passed to the module logger's ``info`` method.

    Patching ``logger.info`` directly (rather than relying on ``caplog``)
    sidesteps the module's custom Rich / rotating-file handlers and gives a
    deterministic record of exactly what :func:`timing` emits.

    Returns
    -------
        The list that accumulates messages logged during the test.
    """
    messages: list[str] = []
    monkeypatch.setattr(benchmarking.logger, "info", messages.append)
    return messages


@pytest.fixture
def fake_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make :func:`time.perf_counter` return a fixed 1.5s elapsed interval.

    The clock yields ``10.0`` on the first read (start) and ``11.5`` on the
    second (end), so any wrapped call records exactly ``1.5`` seconds.
    """
    samples = iter([10.0, 11.5])
    monkeypatch.setattr(benchmarking.time, "perf_counter", lambda: next(samples))


class TestTimingReturnValue:
    """Tests for :func:`timing` — the wrapper must be transparent to the result."""

    def test_bare_form_returns_value(self) -> None:
        """The bare ``@timing`` form returns the wrapped callable's result unchanged."""

        @timing
        def add(a: int, b: int) -> int:
            return a + b

        assert add(2, 3) == 2 + 3

    def test_parenthesised_form_returns_value(self) -> None:
        """The parenthesised ``@timing()`` form returns the result unchanged."""

        @timing()
        def greet(name: str) -> str:
            return f"hello {name}"

        assert greet("world") == "hello world"

    def test_forwards_args_and_kwargs(self) -> None:
        """Positional and keyword arguments are forwarded verbatim to the callable."""

        @timing
        def combine(a: int, /, b: int, *, c: int) -> tuple[int, int, int]:
            return (a, b, c)

        assert combine(1, 2, c=3) == (1, 2, 3)

    def test_preserves_metadata(self) -> None:
        """:func:`functools.update_wrapper` copies ``__name__`` and ``__doc__`` across."""
        docstring = "A trivial documented callable."

        def original() -> int:
            return 42

        original.__doc__ = docstring
        wrapped = timing(original)

        assert getattr(wrapped, "__name__") == "original"
        assert getattr(wrapped, "__doc__") == docstring


class TestTimingMeasurement:
    """Tests for :func:`timing` — the logged elapsed duration."""

    @pytest.mark.usefixtures("fake_clock")
    def test_logs_elapsed_duration(self, captured_logs: list[str]) -> None:
        """A deterministic 1.5s interval is reported to four decimal places."""

        @timing
        def work() -> int:
            return 1

        result = work()
        assert result == 1
        assert captured_logs == ["work took 1.5000 seconds"]

    @pytest.mark.usefixtures("fake_clock")
    def test_logs_once_per_call(self, captured_logs: list[str]) -> None:
        """Exactly one observation is recorded per invocation."""

        @timing
        def noop() -> None:
            return None

        noop()
        assert len(captured_logs) == 1

    def test_duration_is_non_negative(
        self,
        monkeypatch: pytest.MonkeyPatch,
        captured_logs: list[str],
    ) -> None:
        """A monotonic clock yields a non-negative recorded duration."""
        samples = iter([100.0, 100.5])
        monkeypatch.setattr(benchmarking.time, "perf_counter", lambda: next(samples))

        sentinel = object()

        @timing
        def work() -> object:
            return sentinel

        assert work() is sentinel
        assert len(captured_logs) == 1
        recorded = float(captured_logs[0].removeprefix("work took ").removesuffix(" seconds"))
        assert recorded >= 0.0

    def test_message_uses_wrapped_function_name(
        self,
        monkeypatch: pytest.MonkeyPatch,
        captured_logs: list[str],
    ) -> None:
        """The log line is keyed by the wrapped function's ``__name__``."""
        samples = iter([0.0, 0.0])
        monkeypatch.setattr(benchmarking.time, "perf_counter", lambda: next(samples))

        @timing
        def distinctive_name() -> None:
            return None

        distinctive_name()
        assert captured_logs[0].startswith("distinctive_name took ")
