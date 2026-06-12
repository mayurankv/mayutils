"""
Provide shared typing primitives for structured data containers.

This module defines reusable typing constructs used across ``mayutils`` for
representing JSON payloads, SQL queries, recursively nested mappings and
lightweight structural protocols. ``JsonString``, ``JsonValue`` and
``JsonParsed`` distinguish the raw serialised form of JSON from its
parsed Python representation at the type level, ``SQL`` separates
inline query strings from filesystem paths, while :class:`RecursiveDict`
models tree-shaped data whose leaves share a common value type. The
:class:`SupportsStr` protocol is used to constrain inputs to anything
that can be coerced to ``str`` via ``__str__``.

See Also
--------
typing : Standard library module providing ``NewType`` and ``Protocol``.
collections.abc : Abstract base classes such as ``Mapping`` reused here.
mayutils.objects.dataframes : Consumers of structurally typed payloads.

Examples
--------
>>> from mayutils.objects.types import SQL, JsonString, RecursiveMapping, SupportsStr
>>> payload = JsonString('{"a": 1}')
>>> tree: RecursiveMapping[str, int] = {"a": 1, "b": {"c": 2}}
>>> def render(value: SupportsStr) -> str:
...     return str(value)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import NewType, Protocol

JsonString = NewType("JsonString", str)
"""
Mark values that hold a serialised JSON document at the type level.

Used as an annotation to differentiate a raw JSON payload awaiting
parsing from an arbitrary :class:`str`, providing stricter static
checks on functions that consume or produce serialised JSON. Because
:func:`typing.NewType` does not create a runtime subclass, the
overhead is zero while type checkers still treat it as a distinct
type.

See Also
--------
JsonParsed : Companion alias representing the decoded mapping form.
typing.NewType : Standard helper used to build this distinct subtype.
json.dumps : Function that typically produces ``JsonString`` values.

Examples
--------
>>> payload = JsonString('{"a": 1}')
>>> isinstance(payload, str)
True
"""

SQL = NewType("SQL", str)
"""
Mark values that hold an inline SQL query at the type level.

Used as an annotation to differentiate a raw SQL string from an
arbitrary :class:`str` or a filesystem :class:`~pathlib.Path`
pointing at a query template file. Inline ``SQL`` values are treated
as Jinja templates by :func:`mayutils.data.read.render_query`, with
``{{ name }}`` placeholders substituted from ``template_kwargs``.
Because :func:`typing.NewType` does not create a runtime subclass,
the overhead is zero while type checkers still treat it as a
distinct type, catching accidental misuse where a file path is
passed as a bare string.

See Also
--------
JsonString : Companion NewType for serialised JSON payloads.
typing.NewType : Standard helper used to build this distinct subtype.
mayutils.data.read.render_query : Primary consumer that dispatches
    on ``SQL`` vs :class:`~pathlib.Path`.
mayutils.data.read.read_query : Query executor accepting ``SQL``
    or :class:`~pathlib.Path`.

Examples
--------
>>> sql = SQL("SELECT * FROM loans")
>>> isinstance(sql, str)
True
"""

type JsonValue = str | int | float | bool | None | Sequence[JsonValue] | Mapping[str, JsonValue]
"""
Represent any value that a JSON document may contain.

This recursive type alias covers the full range of JSON-legal values:
primitive scalars (:class:`str`, :class:`int`, :class:`float`,
:class:`bool`, ``None``), sequences of nested values, and
string-keyed mappings of nested values. The alias uses
:class:`~collections.abc.Sequence` and
:class:`~collections.abc.Mapping` rather than :class:`list` and
:class:`dict` so that concrete containers with narrower element types
(e.g. ``list[int]``) satisfy the annotation covariantly.

See Also
--------
JsonParsed : Companion NewType wrapping an entire parsed JSON object.
JsonString : Companion NewType for the raw serialised form.
json.loads : Function whose return value can be annotated as
    ``JsonValue`` for arbitrary JSON payloads.

Examples
--------
>>> from mayutils.objects.types import JsonValue
>>> value: JsonValue = {"a": [1, 2, True], "b": None}
"""

JsonParsed = NewType("JsonParsed", Mapping[str, JsonValue])
"""
Mark parsed JSON object payloads as a distinct mapping subtype.

Represents the in-memory result of decoding a JSON object into a
string-keyed mapping, keeping parsed payloads typed separately from
generic mappings in the call graph. This enables static separation of
raw string payloads and their decoded counterparts without imposing
any runtime cost, because :func:`typing.NewType` is an identity
function at runtime.

See Also
--------
JsonString : Companion alias representing the raw serialised form.
typing.NewType : Standard helper used to build this distinct subtype.
collections.abc.Mapping : Base protocol that parsed payloads satisfy.

Examples
--------
>>> import json
>>> decoded = JsonParsed(json.loads('{"a": 1}'))
>>> decoded["a"]
1
"""


type RecursiveMapping[Key, Value] = Mapping[Key, Value | RecursiveMapping[Key, Value]]
"""
A mapping whose values are leaves or nested mappings of the same shape.

Expressed as a recursive type alias so that plain ``dict`` and
``Mapping`` literals are assignable via covariance without wrapping.
"""


class SupportsStr(Protocol):
    """
    Describe objects that can be coerced to :class:`str` via ``__str__``.

    Any object exposing a ``__str__`` method returning a :class:`str`
    satisfies this structural protocol, making it usable wherever a
    stringifiable value is expected without requiring a concrete base
    class. Because :class:`typing.Protocol` performs structural
    subtyping, conformance is determined purely by the shape of the
    class and no explicit inheritance is needed.

    See Also
    --------
    typing.Protocol : Base class enabling structural subtyping.
    builtins.str : Callable that delegates to ``__str__`` on the input.
    JsonString : Related alias for already-stringified payloads.

    Examples
    --------
    >>> class Named:
    ...     def __str__(self) -> str:
    ...         return "named"
    >>> def render(value: SupportsStr) -> str:
    ...     return str(value)
    >>> render(Named())
    'named'
    """

    def __str__(
        self,
    ) -> str:
        """
        Return the string representation of the implementing object.

        Implementations should produce a human-readable rendering that
        is safe to embed in logs, error messages, or serialised output.
        The protocol places no constraints on the content beyond the
        return type, so subclasses are free to choose whichever
        formatting best describes the underlying value.

        Returns
        -------
            Human-readable string form of the implementing object.

        See Also
        --------
        builtins.str : Callable that ultimately dispatches to this method.
        SupportsStr : Enclosing protocol describing the contract.
        JsonString : Typed alias for already-stringified payloads.

        Examples
        --------
        >>> class Named:
        ...     def __str__(self) -> str:
        ...         return "named"
        >>> str(Named())
        'named'
        """
        ...
