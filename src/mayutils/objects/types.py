"""
Provide shared typing primitives for structured data containers.

This module defines reusable typing constructs used across ``mayutils`` for
representing JSON payloads, recursively nested mappings and lightweight
structural protocols. ``JsonString`` and ``JsonParsed`` distinguish the
raw serialised form of JSON from its parsed Python representation at the
type level, while :class:`RecursiveDict` models tree-shaped data whose
leaves share a common value type. The :class:`SupportsStr` protocol is
used to constrain inputs to anything that can be coerced to ``str`` via
``__str__``.

See Also
--------
typing : Standard library module providing ``NewType`` and ``Protocol``.
collections.abc : Abstract base classes such as ``Mapping`` reused here.
mayutils.objects.dataframes : Consumers of structurally typed payloads.

Examples
--------
>>> from mayutils.objects.types import JsonString, RecursiveDict, SupportsStr
>>> payload = JsonString('{"a": 1}')
>>> tree: RecursiveDict[str, int] = RecursiveDict({"a": 1, "b": {"c": 2}})
>>> def render(value: SupportsStr) -> str:
...     return str(value)
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NewType, Protocol

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

JsonParsed = NewType("JsonParsed", Mapping[str, Any])
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


class RecursiveDict[K, V](
    dict[K, "V | RecursiveDict[K, V]"],
):
    """
    Represent a dictionary whose values are leaves or nested dictionaries.

    This class is a generic subclass of :class:`dict` whose value type is
    the recursive union ``V | RecursiveDict[K, V]``. It is intended for
    tree-shaped payloads such as nested configuration trees or
    hierarchical chart data where each node may carry either a terminal
    value or a further mapping of the same shape. The recursion is
    expressed purely at the type level via the PEP 695 generic syntax,
    binding ``K`` to the key type and ``V`` to the leaf value type so
    that existing ``dict`` literals continue to work at runtime without
    conversion.

    See Also
    --------
    dict : Concrete base class extended by this recursive variant.
    collections.abc.Mapping : Structural interface shared by nested nodes.
    JsonParsed : Related type for decoded JSON mappings.

    Examples
    --------
    >>> tree: RecursiveDict[str, int] = RecursiveDict(
    ...     {"a": 1, "b": {"c": 2}},
    ... )
    >>> tree["a"]
    1
    >>> tree["b"]["c"]
    2
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
