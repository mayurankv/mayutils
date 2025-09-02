from contextlib import _GeneratorContextManager
from sqlite3 import register_adapter
from typing import Any, Optional, Self, Literal
import datetime as _datetime
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

    @classmethod
    def parse(
        cls,
        input,
    ) -> Self:
        output = parse(input=input)

        if not isinstance(output, cls):
            raise ValueError("Could not parse to date")

        return output


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

    @classmethod
    def parse(
        cls,
        input,
    ) -> Self:
        output = parse(input=input)

        if not isinstance(output, cls):
            raise ValueError("Could not parse to time")

        return output


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
