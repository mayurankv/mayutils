"""Datetime constants, formatters, and type aliases.

This module centralises shared datetime primitives used across the
``mayutils.objects.datetime`` package. It exposes pre-instantiated pendulum
formatter objects for parsing and rendering datetimes, a literal type alias
enumerating the canonical calendar and clock units recognised by pendulum, and
integer conversion factors that are expensive or awkward to recompute at call
sites. Centralising these values keeps downstream modules free of repeated
construction overhead and avoids drift between independent definitions of the
same unit terminology.
"""

from __future__ import annotations

from typing import Literal

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from pendulum import Formatter
    from pendulum.formatting.difference_formatter import DifferenceFormatter


type NormalDurations = Literal["second", "minute", "hour", "day", "month", "year"]
"""Literal alias enumerating the canonical calendar and clock duration units.

Notes
-----
Values correspond to the singular unit names accepted by pendulum duration
arithmetic and by helper functions that dispatch on unit granularity. The
alias is intentionally restricted to the six units that map cleanly to both
wall-clock and calendar durations, excluding units such as ``week`` or
``quarter`` that are typically derived from these primitives.
"""

FORMATTER = Formatter()
"""Shared :class:`pendulum.Formatter` instance for token-based datetime I/O.

Notes
-----
Used to parse datetime strings against pendulum format tokens and to render
datetimes back into strings. A single module-level instance is reused to avoid
the cost of repeated construction and to guarantee consistent behaviour across
call sites in the ``mayutils.objects.datetime`` package.
"""

DIFFERENCE_FORMATTER = DifferenceFormatter()
"""Shared :class:`DifferenceFormatter` instance for humanised duration output.

Notes
-----
Produces locale-aware, human-readable descriptions of the difference between
two datetimes (for example, ``"3 hours ago"``). Reusing a single instance
ensures uniform phrasing and avoids per-call initialisation overhead.
"""

DAY_SECONDS = 24 * 60 * 60
"""Number of seconds in a standard 24-hour civil day.

Notes
-----
Expressed in seconds as an integer (``86400``). Assumes a fixed-length day and
therefore ignores leap seconds and daylight-saving transitions; callers that
require calendar-aware arithmetic should use pendulum duration objects rather
than this constant.
"""
