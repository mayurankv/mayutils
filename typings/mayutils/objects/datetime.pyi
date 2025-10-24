import datetime as _datetime
import numpy as np
from _typeshed import Incomplete
from contextlib import _GeneratorContextManager
from pendulum import (
    DAYS_PER_WEEK as DAYS_PER_WEEK,
    Date as BaseDate,
    DateTime as BaseDateTime,
    Duration as Duration,
    FixedTimezone as FixedTimezone,
    HOURS_PER_DAY as HOURS_PER_DAY,
    Interval as BaseInterval,
    MINUTES_PER_HOUR as MINUTES_PER_HOUR,
    MONTHS_PER_YEAR as MONTHS_PER_YEAR,
    SECONDS_PER_DAY as SECONDS_PER_DAY,
    SECONDS_PER_HOUR as SECONDS_PER_HOUR,
    SECONDS_PER_MINUTE as SECONDS_PER_MINUTE,
    Time as BaseTime,
    Timezone as BaseTimezone,
    WEEKS_PER_YEAR as WEEKS_PER_YEAR,
    YEARS_PER_CENTURY as YEARS_PER_CENTURY,
    YEARS_PER_DECADE as YEARS_PER_DECADE,
)
from pendulum.locales.locale import Locale as Locale
from pendulum.testing.traveller import Traveller as BaseTraveller
from typing import Any, Iterator, Literal, Mapping, Self, overload

type NormalDurations = Literal["second", "minute", "hour", "day", "month", "year"]
FORMATTER: Incomplete
DIFFERENCE_FORMATTER: Incomplete
DAY_SECONDS: Incomplete

class Timezone(BaseTimezone):
    @classmethod
    def spawn(cls, name: str | int = "UTC") -> Self | FixedTimezone: ...
    @classmethod
    def list(cls) -> set[str]: ...
    @staticmethod
    def local() -> BaseTimezone | FixedTimezone: ...
    def set_local(self) -> None: ...
    def test_local(self) -> _GeneratorContextManager[None, None, None]: ...
    @staticmethod
    def locale() -> str: ...
    @staticmethod
    def set_locale(name: str) -> None: ...
    @staticmethod
    def load_locale(name: str) -> Locale: ...

UTC: Incomplete

class Date(BaseDate):
    @classmethod
    def from_base(cls, base: BaseDate) -> Self: ...
    @classmethod
    def from_datetime(cls, date: _datetime.date) -> Self: ...
    @classmethod
    def parse(cls, input) -> Self: ...
    def is_weekend(self) -> bool: ...
    def to_datetime(self, tz: str | Timezone = ...) -> DateTime: ...
    def to_numpy(self) -> np.datetime64: ...

class Time(BaseTime):
    @classmethod
    def from_base(cls, base: BaseTime) -> Self: ...
    @classmethod
    def from_datetime(
        cls,
        time: _datetime.time,
        tz: str | Timezone | FixedTimezone | _datetime.tzinfo | None = ...,
    ) -> Self: ...
    @classmethod
    def parse(cls, input) -> Self: ...
    def today(self) -> DateTime: ...
    def on(self, date: Date) -> DateTime: ...
    @property
    def fractional_completion(self) -> float: ...

class DateTime(BaseDateTime):
    @classmethod
    def from_base(cls, base: BaseDateTime) -> Self: ...
    @classmethod
    def parse(
        cls,
        input,
        format: str | None = None,
        tz: Timezone = ...,
        locale: str | None = None,
    ) -> Self: ...
    @classmethod
    def today(cls, tz: str | Timezone = "local") -> Self: ...
    @classmethod
    def tomorrow(cls, tz: str | Timezone = "local") -> Self: ...
    @classmethod
    def yesterday(cls, tz: str | Timezone = "local") -> Self: ...
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
    ) -> Self: ...
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
    ) -> Self: ...
    @classmethod
    def from_format(
        cls, string: str, fmt: str, tz: str | Timezone = ..., locale: str | None = None
    ) -> Self: ...
    @classmethod
    def from_timestamp(
        cls, timestamp: int | float, tz: str | Timezone = ...
    ) -> Self: ...
    @property
    def simple(self) -> _datetime.datetime: ...
    def date(self) -> Date: ...
    def time(self) -> Time: ...
    def is_weekend(self) -> bool: ...
    def to_numpy(self) -> np.datetime64: ...

class Interval(BaseInterval):
    def __new__(
        cls,
        start: DateTime | str,
        end: DateTime | str,
        absolute: bool = False,
        format: str | None = None,
    ) -> Self: ...
    def __init__(
        self,
        start: DateTime | str,
        end: DateTime | str,
        absolute: bool = False,
        format: str | None = None,
    ) -> None: ...
    def __deepcopy__(self, _memo: Mapping) -> Self: ...
    @property
    def start(self) -> DateTime: ...
    @property
    def end(self) -> DateTime: ...
    def count_weekdays(self) -> tuple[int, int]: ...
    @property
    def weekends(self) -> int | None: ...
    @property
    def weekdays(self) -> int | None: ...
    @classmethod
    def from_base(cls, base: BaseInterval) -> Self: ...
    @property
    def as_slice(self) -> slice: ...

class Intervals:
    intervals: Incomplete
    def __init__(self, *intervals: Interval) -> None: ...
    def sort(self) -> Self: ...
    def __iter__(self) -> Iterator[Interval]: ...
    def __len__(self) -> int: ...
    @overload
    def __getitem__(self, key: int) -> Interval: ...
    @overload
    def __getitem__(self, key: slice) -> Intervals: ...

class Traveller(BaseTraveller):
    def __init__(self, datetime_class: type[DateTime] = ...) -> None: ...

traveller: Incomplete

def parse(input: str | Date | DateTime | Time | Duration | Interval) -> Any: ...
def get_intervals(
    date: DateTime = ...,
    num_periods: int = 13,
    day: int | None = 1,
    absolute_interval: bool = False,
) -> Intervals: ...
