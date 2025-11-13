from __future__ import annotations
from contextlib import _GeneratorContextManager
from sqlite3 import register_adapter
from typing import Any, Iterator, Mapping, Optional, Self, Literal, overload
import datetime as _datetime
import numpy as np
from pendulum import (
    DateTime as BaseDateTime,
    Date as BaseDate,
    Time as BaseTime,
    Duration,
    Interval as BaseInterval,
    Timezone as BaseTimezone,
    FixedTimezone,
    WeekDay as Weekdays,  # noqa: F401
    Formatter,
    local_timezone,
    DAYS_PER_WEEK,  # noqa: F401
    HOURS_PER_DAY,  # noqa: F401
    MINUTES_PER_HOUR,  # noqa: F401
    MONTHS_PER_YEAR,  # noqa: F401
    SECONDS_PER_DAY,  # noqa: F401
    SECONDS_PER_HOUR,  # noqa: F401
    SECONDS_PER_MINUTE,  # noqa: F401
    WEEKS_PER_YEAR,  # noqa: F401
    YEARS_PER_CENTURY,  # noqa: F401
    YEARS_PER_DECADE,  # noqa: F401
    set_local_timezone,
    set_locale,
    get_locale,
    locale,
    test_local_timezone,
    parse as pendulum_parse,
)
from pendulum.tz import fixed_timezone, timezones
from pendulum.formatting.difference_formatter import DifferenceFormatter
from pendulum.locales.locale import Locale
from pendulum.testing.traveller import Traveller as BaseTraveller

type NormalDurations = Literal["second", "minute", "hour", "day", "month", "year"]

FORMATTER = Formatter()
DIFFERENCE_FORMATTER = DifferenceFormatter()
DAY_SECONDS = 24 * 60 * 60


class Timezone(BaseTimezone):
    @classmethod
    def spawn(
        cls,
        name: str | int = "UTC",
    ) -> Self | FixedTimezone:
        if isinstance(name, int):
            return fixed_timezone(name)

        if name.lower() == "utc":
            return cls("UTC")

        return cls(name)

    @classmethod
    def list(
        cls,
    ) -> set[str]:
        return timezones()

    @staticmethod
    def local() -> BaseTimezone | FixedTimezone:
        return local_timezone()

    def set_local(
        self,
    ) -> None:
        return set_local_timezone(mock=self)

    def test_local(
        self,
    ) -> _GeneratorContextManager[None, None, None]:
        return test_local_timezone(mock=self)

    @staticmethod
    def locale() -> str:
        return get_locale()

    @staticmethod
    def set_locale(
        name: str,
    ) -> None:
        return set_locale(name=name)

    @staticmethod
    def load_locale(
        name: str,
    ) -> Locale:
        return locale(name=name)


UTC = Timezone(key="UTC")


class Date(BaseDate):
    @classmethod
    def from_base(
        cls,
        base: BaseDate,
    ) -> Self:
        return cls(
            year=base.year,
            month=base.month,
            day=base.day,
        )

    @classmethod
    def from_datetime(
        cls,
        date: _datetime.date,
    ) -> Self:
        return cls(
            year=date.year,
            month=date.month,
            day=date.day,
        )

    @property
    def simple(
        self,
    ) -> _datetime.date:
        return _datetime.date(
            year=self.year,
            month=self.month,
            day=self.day,
        )

    @classmethod
    def parse(
        cls,
        input,
    ) -> Self:
        output = parse(input=input)

        if not isinstance(output, cls):
            raise ValueError("Could not parse to date")

        return output

    def is_weekend(
        self,
    ) -> bool:
        return self.day_of_week in (5, 6)

    def to_datetime(
        self,
        tz: str | Timezone = UTC,
    ) -> DateTime:
        return DateTime.create(
            year=self.year,
            month=self.month,
            day=self.day,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
            tz=tz,
        )

    def to_numpy(
        self,
    ) -> np.datetime64:
        return np.datetime64(self)


class Time(BaseTime):
    @classmethod
    def from_base(
        cls,
        base: BaseTime,
    ) -> Self:
        return cls(
            hour=base.hour,
            minute=base.minute,
            second=base.second,
            microsecond=base.microsecond,
            tzinfo=base.tzinfo,
        )

    @classmethod
    def from_datetime(
        cls,
        time: _datetime.time,
        tz: str | Timezone | FixedTimezone | _datetime.tzinfo | None = UTC,
    ) -> Self:
        return cls.instance(
            t=time,
            tz=tz,
        )

    @property
    def simple(
        self,
    ) -> _datetime.time:
        return _datetime.time(
            hour=self.hour,
            minute=self.minute,
            second=self.second,
            microsecond=self.microsecond,
        )

    @classmethod
    def parse(
        cls,
        input,
    ) -> Self:
        output = parse(input=input)

        if not isinstance(output, cls):
            raise ValueError("Could not parse to time")

        return output

    def today(
        self,
    ) -> DateTime:
        return DateTime.now(
            tz=self.tzinfo,
        ).at(
            hour=self.hour,
            minute=self.minute,
            second=self.second,
            microsecond=self.microsecond,
        )

    def on(
        self,
        date: Date,
    ) -> DateTime:
        return DateTime(
            year=date.year,
            month=date.month,
            day=date.day,
            hour=self.hour,
            minute=self.minute,
            second=self.second,
            microsecond=self.microsecond,
            tzinfo=self.tzinfo,
        )

    @property
    def fractional_completion(
        self,
    ) -> float:
        return (
            self.hour * 3600 + self.minute * 60 + self.second + self.microsecond * 1e-6
        ) / DAY_SECONDS


class DateTime(BaseDateTime):
    @classmethod
    def from_base(
        cls,
        base: BaseDateTime,
    ) -> Self:
        return cls(
            year=base.year,
            month=base.month,
            day=base.day,
            hour=base.hour,
            minute=base.minute,
            second=base.second,
            microsecond=base.microsecond,
            tzinfo=base.tzinfo,
        )

    @classmethod
    def parse(
        cls,
        input,
        format: Optional[str] = None,
        tz: Timezone = UTC,
        locale: Optional[str] = None,
    ) -> Self:
        output = (
            parse(
                input=input,
            )
            if format is None
            else DateTime.from_format(
                string=input,
                fmt=format,
                tz=tz,
                locale=locale,
            )
        )

        if not isinstance(output, cls):
            raise ValueError("Could not parse to datetime")

        return output

    @classmethod
    def today(
        cls,
        tz: str | Timezone = "local",
    ) -> Self:
        return cls.now(
            tz=tz,
        ).start_of(
            unit="day",
        )

    @classmethod
    def tomorrow(
        cls,
        tz: str | Timezone = "local",
    ) -> Self:
        return cls.today(
            tz=tz,
        ).add(
            days=1,
        )

    @classmethod
    def yesterday(
        cls,
        tz: str | Timezone = "local",
    ) -> Self:
        return cls.today(
            tz=tz,
        ).subtract(
            days=1,
        )

    @classmethod
    def local(
        cls,
        year: int,
        month: int,
        day: int,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
        microsecond: int = 0,
    ) -> Self:
        return cls.create(
            year,
            month,
            day,
            hour,
            minute,
            second,
            microsecond,
            tz=local_timezone(),
        )

    @classmethod
    def as_naive(
        cls,
        year: int,
        month: int,
        day: int,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
        microsecond: int = 0,
        fold: int = 1,
    ) -> Self:
        return cls(
            year,
            month,
            day,
            hour,
            minute,
            second,
            microsecond,
            fold=fold,
        )

    @classmethod
    def from_format(
        cls,
        string: str,
        fmt: str,
        tz: str | Timezone = UTC,
        locale: str | None = None,
    ) -> Self:
        parts = FORMATTER.parse(
            time=string,
            fmt=fmt,
            now=cls.now(tz=tz),
            locale=locale,
        )

        if parts["tz"] is None:
            parts["tz"] = tz

        return cls.create(**parts)

    @classmethod
    def from_timestamp(
        cls,
        timestamp: int | float,
        tz: str | Timezone = UTC,
    ) -> Self:
        dt = _datetime.datetime.fromtimestamp(
            timestamp,
            tz=UTC,
        )

        dt = cls.create(
            dt.year,
            dt.month,
            dt.day,
            dt.hour,
            dt.minute,
            dt.second,
            dt.microsecond,
        )

        if tz is not UTC or tz != "UTC":
            dt = dt.in_timezone(tz)

        return dt

    @property
    def simple(
        self,
    ) -> _datetime.datetime:
        return _datetime.datetime(
            year=self.year,
            month=self.month,
            day=self.day,
            hour=self.hour,
            minute=self.minute,
            second=self.second,
            microsecond=self.microsecond,
        )

    def date(
        self,
    ) -> Date:
        return Date(
            year=self.year,
            month=self.month,
            day=self.day,
        )

    def time(
        self,
    ) -> Time:
        return Time(
            hour=self.hour,
            minute=self.minute,
            second=self.second,
            microsecond=self.microsecond,
        )

    def is_weekend(
        self,
    ) -> bool:
        return self.day_of_week in (5, 6)

    def to_numpy(
        self,
    ) -> np.datetime64:
        return np.datetime64(self)


# TODO: NewInterval for working with pandas? nah add to pandas accessor? Or maybe to convert to pandas indexable thing
class Interval(BaseInterval):
    def __new__(
        cls,
        start: DateTime | str,
        end: DateTime | str,
        absolute: bool = False,
        format: Optional[str] = None,
    ) -> Self:
        start = DateTime.parse(input=start, format=format)
        end = DateTime.parse(input=end, format=format)

        return super().__new__(
            cls=cls,
            start=start,
            end=end,
            absolute=absolute,
        )

    def __init__(
        self,
        start: DateTime | str,
        end: DateTime | str,
        absolute: bool = False,
        format: Optional[str] = None,
    ) -> None:
        self._start = DateTime.parse(input=start, format=format)
        self._end = DateTime.parse(input=end, format=format)

        super().__init__(
            start=self._start,
            end=self._end,
            absolute=absolute,
        )

        self._weekends: Optional[int] = None
        self._weekdays: Optional[int] = None

    def __deepcopy__(
        self,
        _memo: Mapping,
    ) -> Self:
        return self.__class__(
            start=self._start,
            end=self._end,
            absolute=self._absolute,
        )

    @property
    def start(
        self,
    ) -> DateTime:
        return DateTime.from_base(super().start)
        # return self._start if not (self._invert and self._absolute) else self._end

    @property
    def end(
        self,
    ) -> DateTime:
        return DateTime.from_base(super().end)
        # return self._end if not (self._invert and self._absolute) else self._start

    def count_weekdays(
        self,
    ) -> tuple[int, int]:
        weekends = 0
        weekdays = 0

        for datetime in self.range(unit="days"):
            if datetime.is_weekend():
                weekends += 1
            else:
                weekdays += 1

        self._weekdays = weekdays
        self._weekends = weekends

        return weekdays, weekends

    @property
    def weekends(
        self,
    ) -> Optional[int]:
        if self._weekends is None:
            self.count_weekdays()

        return self._weekends

    @property
    def weekdays(
        self,
    ) -> Optional[int]:
        if self._weekdays is None:
            self.count_weekdays()

        return self._weekdays

    @classmethod
    def from_base(
        cls,
        base: BaseInterval,
    ) -> Self:
        start = DateTime.from_base(base=base.start)
        end = DateTime.from_base(base=base.end)

        return cls(
            start=start if not base._invert else end,
            end=end if not base._invert else start,
            absolute=base._absolute,
        )

    @property
    def as_slice(
        self,
    ) -> slice:
        return (
            slice(
                self.start.simple,
                self.end.simple,
            )
            if not self._invert
            else slice(
                self.end.simple,
                self.start.simple,
            )
        )

    @property
    def as_date_slice(
        self,
    ) -> slice:
        return (
            slice(
                self.start.date().simple,
                self.end.date().simple,
            )
            if not self._invert
            else slice(
                self.end.date().simple,
                self.start.date().simple,
            )
        )

    def to_interval_string(
        self,
        datetime: bool = False,
    ) -> str:
        return (
            f"{self.start.to_datetime_string()} to {self.end.to_datetime_string()}"
            if datetime
            else f"{self.start.to_date_string()} to {self.end.to_date_string()}"
        )


class Intervals(object):
    def __init__(
        self,
        *intervals: Interval,
    ) -> None:
        self.intervals = intervals
        self.sort()

    def sort(
        self,
    ) -> Self:
        self.intervals = tuple(
            sorted(self.intervals, key=lambda interval: (interval.start, interval.end))
        )

        return self

    def __repr__(
        self,
    ) -> str:
        return f"Intervals(\n\t{'\n\t'.join([repr(interval) for interval in self.intervals])}\n)"

    def __iter__(
        self,
    ) -> Iterator[Interval]:
        return iter(self.intervals)

    def __len__(
        self,
    ) -> int:
        return len(self.intervals)

    @overload
    def __getitem__(
        self,
        key: int,
    ) -> Interval: ...

    @overload
    def __getitem__(
        self,
        key: slice,
    ) -> Intervals: ...

    def __getitem__(
        self,
        key: int | slice,
    ) -> Intervals | Interval:
        if isinstance(key, slice):
            return Intervals(*self.intervals[key])

        elif isinstance(key, int):
            return self.intervals[key]

        else:
            raise TypeError("Invalid key type")


class Traveller(BaseTraveller):
    def __init__(
        self,
        datetime_class: type[DateTime] = DateTime,
    ) -> None:
        super().__init__(datetime_class)


traveller = Traveller()

register_adapter(DateTime, lambda val: val.isoformat(sep=" "))


def parse(
    input: str | Date | DateTime | Time | Duration | Interval,
) -> Any:
    output = pendulum_parse(text=input) if isinstance(input, str) else input

    if isinstance(output, BaseDateTime):
        return DateTime.from_base(output)

    if isinstance(output, BaseTime):
        return Time.from_base(output)

    if isinstance(output, BaseDate):
        return Date.from_base(output)

    return input


def get_intervals(
    date: DateTime = DateTime.today(),
    num_periods: int = 13,
    day: Optional[int] = 1,
    absolute_interval: bool = False,
) -> Intervals:
    return Intervals(
        *[
            Interval(
                start=date.subtract(
                    months=idx,
                ).set(
                    day=day if day is not None else date.day,
                ),
                end=date.subtract(
                    months=idx - 1,
                ).set(
                    day=day if day is not None else date.day,
                ),
                absolute=absolute_interval,
            )
            for idx in range(num_periods, 0, -1)
        ]
    )


# is_consecutive: (obj1 - obj2).in_frequency() == 1
# subtract_month: dt.subtract(months=months).set(day=day)
# to_month: dt.format("MMM")
