"""
Provide datetime constants, formatters, and type aliases.

Centralise shared datetime primitives used across the
``mayutils.objects.datetime`` package. Expose pre-instantiated pendulum
formatter objects for parsing and rendering datetimes, a literal type alias
enumerating the canonical calendar and clock units recognised by pendulum,
and integer conversion factors that are awkward to recompute at call sites.
Consolidating these values keeps downstream modules free of repeated
construction overhead and avoids drift between independent definitions of
the same unit terminology.

See Also
--------
calendar : Standard library calendar-related helpers.
datetime : Standard library datetime types operating on these units.
pendulum : Timezone-aware datetime library that underpins the formatters.
mayutils.objects.datetime.conversions : Sibling helpers that consume these
    formatters and constants.

Examples
--------
>>> from mayutils.objects.datetime.constants import (
...     DAY_SECONDS,
...     FORMATTER,
...     NormalDurations,
... )
>>> DAY_SECONDS
86400
>>> unit: NormalDurations = "hour"
>>> unit
'hour'
>>> isinstance(FORMATTER.format, object)
True
"""

from __future__ import annotations

from typing import Literal

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from pendulum import Formatter
    from pendulum.formatting.difference_formatter import DifferenceFormatter


type NormalDurations = Literal["second", "minute", "hour", "day", "month", "year"]
"""
Enumerate the canonical calendar and clock duration units.

Restrict allowed values to the six singular unit names accepted by pendulum
duration arithmetic and by helper functions that dispatch on unit
granularity. The alias is intentionally restricted to units that map
cleanly to both wall-clock and calendar durations, excluding derived units
such as ``week`` or ``quarter``. Typing against this alias keeps unit
arguments self-documenting and catches typos at static-analysis time.

See Also
--------
calendar : Standard library calendar module using these unit names.
datetime : Standard library datetime components at each granularity.
pendulum : Duration-unit terminology this alias mirrors directly.
mayutils.objects.datetime.constants.DAY_SECONDS : Integer bridge between
    ``"day"`` and ``"second"`` granularity.

Examples
--------
>>> from mayutils.objects.datetime.constants import NormalDurations
>>> def label(unit: NormalDurations) -> str:
...     return f"1 {unit}"
>>> label("minute")
'1 minute'
>>> label("year")
'1 year'
"""


FORMATTER = Formatter()
"""
Expose a shared :class:`pendulum.Formatter` for token-based datetime I/O.

Reuse a single module-level instance to parse datetime strings against
pendulum format tokens and to render datetimes back into strings.
A single shared instance avoids the cost of repeated construction and
guarantees consistent behaviour across call sites in the
``mayutils.objects.datetime`` package. The formatter is stateless with
respect to parsing, so it is safe to share across threads and modules.

See Also
--------
pendulum.Formatter : Underlying formatter class being reused here.
datetime.datetime.strftime : Standard library analogue for rendering.
datetime.datetime.strptime : Standard library analogue for parsing.
mayutils.objects.datetime.constants.DIFFERENCE_FORMATTER : Companion
    formatter for humanised duration strings.

Examples
--------
>>> import pendulum
>>> from mayutils.objects.datetime.constants import FORMATTER
>>> dt = pendulum.datetime(2026, 4, 22, 9, 30)
>>> FORMATTER.format(dt, "YYYY-MM-DD HH:mm")
'2026-04-22 09:30'
"""


DIFFERENCE_FORMATTER = DifferenceFormatter()
"""
Expose a shared :class:`DifferenceFormatter` for humanised durations.

Reuse a single instance to produce locale-aware, human-readable descriptions
of the difference between two datetimes such as ``"3 hours ago"`` or
``"in 2 days"``. Sharing a single instance ensures uniform phrasing
across call sites and avoids per-call initialisation overhead. This
complements :data:`FORMATTER` by handling duration phrasing rather than
token-driven timestamp rendering.

See Also
--------
pendulum.formatting.difference_formatter.DifferenceFormatter : Underlying
    class that generates the humanised strings.
pendulum.duration : Duration primitive consumed by the formatter.
mayutils.objects.datetime.constants.FORMATTER : Sibling formatter for
    token-based datetime rendering.

Examples
--------
>>> import pendulum
>>> from mayutils.objects.datetime.constants import DIFFERENCE_FORMATTER
>>> now = pendulum.datetime(2026, 4, 22, 12, 0)
>>> past = pendulum.datetime(2026, 4, 22, 9, 0)
>>> DIFFERENCE_FORMATTER.format(past.diff(now), is_now=True)
'3 hours ago'
"""

DAY_SECONDS = 24 * 60 * 60
"""
Hold the number of seconds in a standard 24-hour civil day.

Resolve to the integer ``86400`` so that callers can convert between day
and second granularity without recomputing the product at each site.
Assume a fixed-length day, which means the constant ignores leap seconds
and daylight-saving transitions; callers that require calendar-aware
arithmetic should instead construct pendulum duration objects. Useful as
a scaling factor when aggregating per-second metrics into daily totals
or when converting between time-based rate units.

See Also
--------
calendar.SECONDS_IN_DAY : Standard library analogue when available.
datetime.timedelta : Duration primitive with a ``total_seconds`` helper.
pendulum.duration : Calendar-aware alternative honouring DST and leap
    seconds.
mayutils.objects.datetime.constants.NormalDurations : Alias naming the
    ``"day"`` and ``"second"`` units bridged by this constant.

Examples
--------
>>> from mayutils.objects.datetime.constants import DAY_SECONDS
>>> DAY_SECONDS
86400
>>> rate_per_second = 0.5
>>> rate_per_second * DAY_SECONDS
43200.0
"""
