from datetime import datetime
from typing import Optional
from dateutil.relativedelta import relativedelta

from mayutils.core.types import Interval, Periods


def subtract_month(
    date: datetime,
    months: int = 0,
    day: Optional[int] = None,
):
    dt = datetime(
        year=date.year - ((date.month - months) <= 0),
        month=(date.month - months) % 12 or 12,
        day=day if day is not None else date.day,
    )

    return dt


def get_periods(
    date: datetime = datetime.today(),
    num_periods: int = 13,
    format: str = "%Y-%m-%d %H:%M:%S",
) -> Periods:
    date_pairs: Periods = [
        {
            "start_timestamp": subtract_month(
                date=date,
                months=idx,
                day=1,
            ).strftime(format=format),
            "end_timestamp": subtract_month(
                date=date,
                months=idx - 1,
                day=1,
            ).strftime(format=format),
        }
        for idx in range(num_periods, 0, -1)
    ]

    return date_pairs


def parse_datetime(
    dt: datetime | str,
    format: str = "%Y-%m-%d %H:%M:%S",
) -> datetime:
    if isinstance(dt, str):
        dt = datetime.strptime(dt, format)

    return dt


def is_consecutive(
    dt1: datetime | str,
    dt2: datetime | str,
    interval: Interval = "month",
    format: str = "%Y-%m-%d %H:%M:%S",
) -> bool:
    dt1 = parse_datetime(dt=dt1, format=format)
    dt2 = parse_datetime(dt=dt2, format=format)

    if interval == "second":
        return abs((dt2 - dt1).total_seconds()) == 1
    elif interval == "minute":
        return abs((dt2 - dt1).total_seconds()) == 60
    elif interval == "hour":
        return abs((dt2 - dt1).total_seconds()) == 3600
    elif interval == "day":
        return abs((dt2 - dt1).days) == 1
    elif interval == "month":
        return dt2 == dt1 + relativedelta(months=1) or dt1 == dt2 + relativedelta(
            months=1
        )
    elif interval == "year":
        return dt2 == dt1 + relativedelta(years=1) or dt1 == dt2 + relativedelta(
            years=1
        )
    else:
        return False


def to_month(
    dt: datetime | str,
    format: str = "%Y-%m-%d %H:%M:%S",
) -> str:
    dt = parse_datetime(dt=dt, format=format)
    month = dt.strftime(format="%B").title()
    return month
