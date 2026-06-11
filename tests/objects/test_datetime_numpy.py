"""Tests for ``mayutils.objects.datetime.numpy``."""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pytest
from pydantic import BaseModel, ValidationError

from mayutils.objects.datetime.numpy import NpDatetime64, coerce_datetime64


class TestCoerceDatetime64:
    """Tests for :func:`coerce_datetime64`."""

    def test_datetime64_normalised_to_microseconds(self) -> None:
        """Existing ``datetime64`` values are cast to microsecond resolution."""
        value = np.datetime64("2026-01-01", "s")
        result = coerce_datetime64(value)
        assert result.dtype == np.dtype("datetime64[us]")

    def test_python_datetime_coerced(self) -> None:
        """Python ``datetime`` objects are coerced to microsecond ``datetime64``."""
        result = coerce_datetime64(datetime(2026, 1, 1, 12, 30))  # noqa: DTZ001
        assert result == np.datetime64("2026-01-01T12:30:00", "us")

    def test_python_date_coerced(self) -> None:
        """Python ``date`` objects are coerced to microsecond ``datetime64``."""
        result = coerce_datetime64(date(2026, 1, 1))
        assert result == np.datetime64("2026-01-01", "us")

    def test_iso_string_coerced(self) -> None:
        """ISO 8601 strings are coerced to microsecond ``datetime64``."""
        result = coerce_datetime64("2026-01-01T00:00:00")
        assert result == np.datetime64("2026-01-01", "us")

    def test_none_coerces_to_nat(self) -> None:
        """None silently becomes NaT — documented footgun, pinned here."""
        result = coerce_datetime64(None)  # type: ignore[arg-type]
        assert np.isnat(result)


class TestNpDatetime64:
    """Tests for the :data:`NpDatetime64` annotated type."""

    def test_pydantic_field_validates_from_string(self) -> None:
        """A string input is coerced to ``datetime64[us]`` on the model."""

        class Model(BaseModel):
            created: NpDatetime64

        model = Model(created="2026-01-01T09:00:00")
        assert model.created == np.datetime64("2026-01-01T09:00:00", "us")

    def test_pydantic_field_serialises_to_string(self) -> None:
        """``model_dump()`` returns the field as a string."""

        class Model(BaseModel):
            created: NpDatetime64

        model = Model(created="2026-01-01T09:00:00")
        dumped = model.model_dump()
        assert isinstance(dumped["created"], str)
        assert dumped["created"].startswith("2026-01-01T09:00:00")

    def test_validated_field_is_datetime64(self) -> None:
        """The validated field must be an actual np.datetime64, not a passthrough."""

        class Model(BaseModel):
            created: NpDatetime64

        model = Model(created="2026-01-01T09:00:00")
        assert isinstance(model.created, np.datetime64)

    def test_junk_input_raises_validation_error(self) -> None:
        """Unparseable input surfaces as pydantic ValidationError, not a numpy error."""

        class Model(BaseModel):
            created: NpDatetime64

        with pytest.raises(ValidationError):
            Model(created=object())

    def test_serialised_value_round_trips(self) -> None:
        """model_dump output feeds back in and compares equal."""

        class Model(BaseModel):
            created: NpDatetime64

        model = Model(created="2026-01-01T09:00:00.123456")
        rebuilt = Model(**model.model_dump())
        assert rebuilt.created == model.created
