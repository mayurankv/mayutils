"""Utilities for everyday Python objects and widely used data structures.

Groups the small, self-contained helpers that operate on generic Python
values rather than on infrastructure or I/O. Each submodule focuses on a
single conceptual kind of object — colours, dataframes, datetimes,
decorators, dictionaries, hash inputs, numbers, strings, version
identifiers — so callers can import narrowly and only pay the cost of
the optional extras they actually need. Heavy third-party backends
(pandas, polars, pendulum, packaging, matplotlib) are gated behind the
relevant extras via :func:`mayutils.core.extras.may_require_extras`.

Submodules
----------
classes
    Metaclass-level helpers, descriptors (``classonlyproperty``,
    ``readonlyclassonlyproperty``), chained-method support, and
    super-method adoption utilities.
colours
    Dataclass-based RGBA colour model with CSS parsing, HSV/HLS/CMYK
    conversion, blending, opacity control and python-pptx interop
    (requires the ``plotting`` / ``pdf`` extras for rich rendering).
dataframes
    pandas / polars / pyarrow / dask / modin / snowflake dataframe
    accessors and serialisation helpers (``dataframes`` extra for the
    full backend set).
datetime
    Pendulum-backed :class:`Date`, :class:`DateTime`, :class:`Interval`
    and timezone/locale helpers (``datetime`` extra).
decorators
    Reusable decorator patterns, including the ``flexwrap`` adapter that
    lets a decorator be invoked bare or parameterised.
dictionaries
    Mapping-level helpers (e.g. value-to-key inversion).
functions
    Function-level primitives: no-op callables, in-place setters and
    ``SupportsSetItem``-style protocols.
hashing
    Deterministic serialisation and hashing of arbitrary Python values
    for cache-key construction.
numbers
    Human-readable numeric formatting (SI-prefixed ``prettify``,
    ordinal suffixes).
strings
    Case conversion (snake / kebab / camel / pascal / title / sentence)
    and ``None``-coercion helpers via the :class:`String` façade.
types
    Shared typing aliases (``JsonString``, ``JsonParsed``,
    ``RecursiveDict``, ``SupportsStr``) used across the package.
versions
    Semantic version manipulation built on
    :class:`packaging.version.Version`, centralising the bump semantics
    used by the release scripts.
"""
