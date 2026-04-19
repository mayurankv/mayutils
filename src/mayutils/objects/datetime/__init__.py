"""Datetime primitives, timezone utilities, intervals, and time-travel helpers.

This package aggregates the ``pendulum``-backed ``DateTime``, ``Date``,
``Time``, ``Interval`` and ``Traveller`` wrappers defined across the
sibling submodules together with a curated set of pendulum constants,
formatters, and timezone helpers. It also re-exports the corresponding
standard-library ``datetime`` types under ``Base*`` aliases so downstream
code can access both the enriched and the native implementations from a
single import surface.
"""

from __future__ import annotations

from datetime import date as BaseDate  # noqa: N812
from datetime import datetime as BaseDateTime  # noqa: N812
from datetime import time as BaseTime  # noqa: N812
from datetime import tzinfo as BaseTzinfo  # noqa: N812

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from pendulum import (
        DAYS_PER_WEEK,
        HOURS_PER_DAY,
        MINUTES_PER_HOUR,
        MONTHS_PER_YEAR,
        SECONDS_PER_DAY,
        SECONDS_PER_HOUR,
        SECONDS_PER_MINUTE,
        WEEKS_PER_YEAR,
        YEARS_PER_CENTURY,
        YEARS_PER_DECADE,
        Duration,
        FixedTimezone,
        Formatter,
        get_locale,
        local_timezone,
        locale,
        set_local_timezone,
        set_locale,
        test_local_timezone,
    )
    from pendulum import (
        Date as PendulumDate,
    )
    from pendulum import (
        DateTime as PendulumDateTime,
    )
    from pendulum import (
        Interval as PendulumInterval,
    )
    from pendulum import (
        Time as PendulumTime,
    )
    from pendulum import (
        Timezone as PendulumTimezone,
    )
    from pendulum import (
        WeekDay as Weekdays,
    )
    from pendulum import (
        parse as pendulum_parse,
    )
    from pendulum.formatting.difference_formatter import DifferenceFormatter
    from pendulum.testing.traveller import Traveller as PendulumTraveller
    from pendulum.tz import fixed_timezone, timezones

from mayutils.objects.datetime.constants import (
    DAY_SECONDS,
    DIFFERENCE_FORMATTER,
    FORMATTER,
    NormalDurations,
)
from mayutils.objects.datetime.datetime import Date, DateNumericMixin, DateTime, Time, parse
from mayutils.objects.datetime.interval import Interval, Intervals, get_intervals
from mayutils.objects.datetime.timezone import UTC, Tz
from mayutils.objects.datetime.traveller import Traveller, traveller

__all__ = [
    "DAYS_PER_WEEK",
    "DAY_SECONDS",
    "DIFFERENCE_FORMATTER",
    "FORMATTER",
    "HOURS_PER_DAY",
    "MINUTES_PER_HOUR",
    "MONTHS_PER_YEAR",
    "SECONDS_PER_DAY",
    "SECONDS_PER_HOUR",
    "SECONDS_PER_MINUTE",
    "UTC",
    "WEEKS_PER_YEAR",
    "YEARS_PER_CENTURY",
    "YEARS_PER_DECADE",
    "BaseDate",
    "BaseDateTime",
    "BaseTime",
    "BaseTzinfo",
    "Date",
    "DateNumericMixin",
    "DateTime",
    "DifferenceFormatter",
    "Duration",
    "FixedTimezone",
    "Formatter",
    "Interval",
    "Intervals",
    "NormalDurations",
    "PendulumDate",
    "PendulumDateTime",
    "PendulumInterval",
    "PendulumTime",
    "PendulumTimezone",
    "PendulumTraveller",
    "Time",
    "Traveller",
    "Tz",
    "Weekdays",
    "fixed_timezone",
    "get_intervals",
    "get_locale",
    "local_timezone",
    "locale",
    "parse",
    "pendulum_parse",
    "set_local_timezone",
    "set_locale",
    "test_local_timezone",
    "timezones",
    "traveller",
]
