"""``String`` namespace with case-conversion helpers and empty-string coercion.

The :class:`String` class groups case-style converters
(``snake_case``, ``kebab-case``, ``camelCase``, ``PascalCase``,
``Title Case``, ``Sentence case``) and an empty-to-``None`` coercer,
each exposed as a ``@staticmethod`` that accepts a single positional-only
string argument.

Examples
--------
>>> from mayutils.objects.strings import String
>>> String.to_snake("HelloWorld")
'hello_world'
>>> String.to_camel("hello-world")
'helloWorld'
>>> String.to_none("") is None
True
"""

from __future__ import annotations

from re import sub


class String:
    """Namespace of case-conversion helpers (snake / kebab / camel / pascal / title / sentence)."""

    __slots__ = ()

    @staticmethod
    def _words(
        string: str,
        /,
    ) -> list[str]:
        """Split ``string`` into lowercase word tokens across case, space, and separator boundaries.

        Internal helper used by the camel / pascal / title / sentence
        converters. Delegates to :meth:`String.to_snake` and splits on
        ``"_"``, discarding empty segments introduced by leading, trailing,
        or repeated separators.

        Parameters
        ----------
        string : str
            The input string. May contain a mix of cases, spaces,
            underscores, and hyphens.

        Returns
        -------
        list[str]
            Lowercase word tokens in order. Empty when ``string`` contains
            no word characters.
        """
        return [word for word in String.to_snake(string).split(sep="_") if word]

    @staticmethod
    def to_snake(
        string: str,
        /,
    ) -> str:
        """Convert ``string`` to ``snake_case``.

        Word boundaries are inferred from case transitions
        (``HelloWorld`` → ``hello world``), runs of uppercase letters
        followed by a lowercase letter (``XMLParser`` → ``XML Parser``),
        and hyphens. The result is lower-cased and joined with ``"_"``.

        Parameters
        ----------
        string : str
            The input string in any case style.

        Returns
        -------
        str
            ``string`` normalised to ``snake_case``.

        Examples
        --------
        >>> String.to_snake("HelloWorld")
        'hello_world'
        >>> String.to_snake("XMLParser")
        'xml_parser'
        >>> String.to_snake("hello-world")
        'hello_world'
        """
        return "_".join(
            sub(
                pattern="([A-Z][a-z]+)",
                repl=r" \1",
                string=sub(
                    pattern="([A-Z]+)",
                    repl=r" \1",
                    string=string.replace("-", " "),
                ),
            ).split()
        ).lower()

    @staticmethod
    def to_kebab(
        string: str,
        /,
    ) -> str:
        """Convert ``string`` to ``kebab-case``.

        Handles case transitions (``HelloWorld``), acronym-to-word
        boundaries (``XMLParser`` → ``XML-Parser``), and collapses any
        runs of whitespace, underscores, and hyphens into a single
        delimiter.

        Parameters
        ----------
        string : str
            The input string in any case style.

        Returns
        -------
        str
            ``string`` normalised to ``kebab-case``.

        Examples
        --------
        >>> String.to_kebab("HelloWorld")
        'hello-world'
        >>> String.to_kebab("HTTPResponse")
        'http-response'
        >>> String.to_kebab("hello_world")
        'hello-world'
        """
        split = sub(
            pattern=r"([a-z0-9])([A-Z])",
            repl=r"\1 \2",
            string=sub(
                pattern=r"([A-Z]+)([A-Z][a-z])",
                repl=r"\1 \2",
                string=string,
            ),
        )
        normalised = sub(pattern=r"[\s_-]+", repl=" ", string=split).strip()
        return "-".join(normalised.lower().split())

    @staticmethod
    def to_camel(
        string: str,
        /,
    ) -> str:
        """Convert ``string`` to ``camelCase``.

        The first word is lower-cased; subsequent words are
        title-cased and concatenated without a separator. An empty
        input yields an empty string.

        Parameters
        ----------
        string : str
            The input string in any case style.

        Returns
        -------
        str
            ``string`` normalised to ``camelCase``. Empty string when
            ``string`` contains no word characters.

        Examples
        --------
        >>> String.to_camel("hello_world")
        'helloWorld'
        >>> String.to_camel("XMLParser")
        'xmlParser'
        >>> String.to_camel("")
        ''
        """
        parts = String._words(string)
        if not parts:
            return ""
        return parts[0] + "".join(part.capitalize() for part in parts[1:])

    @staticmethod
    def to_pascal(
        string: str,
        /,
    ) -> str:
        """Convert ``string`` to ``PascalCase``.

        Every word is capitalised and concatenated without a separator.

        Parameters
        ----------
        string : str
            The input string in any case style.

        Returns
        -------
        str
            ``string`` normalised to ``PascalCase``. Empty string when
            ``string`` contains no word characters.

        Examples
        --------
        >>> String.to_pascal("hello_world")
        'HelloWorld'
        >>> String.to_pascal("helloWorld")
        'HelloWorld'
        >>> String.to_pascal("")
        ''
        """
        return "".join(part.capitalize() for part in String._words(string))

    @staticmethod
    def to_title(
        string: str,
        /,
    ) -> str:
        """Convert ``string`` to ``Title Case`` — each word capitalised, space-separated.

        Parameters
        ----------
        string : str
            The input string in any case style.

        Returns
        -------
        str
            ``string`` with every word capitalised and joined by single
            spaces. Empty string when ``string`` contains no word
            characters.

        Examples
        --------
        >>> String.to_title("hello_world")
        'Hello World'
        >>> String.to_title("XMLParser")
        'Xml Parser'
        """
        return " ".join(part.capitalize() for part in String._words(string))

    @staticmethod
    def to_sentence(
        string: str,
        /,
    ) -> str:
        """Convert ``string`` to ``Sentence case``.

        Only the first word is capitalised; subsequent words are
        lower-cased and joined by single spaces.

        Parameters
        ----------
        string : str
            The input string in any case style.

        Returns
        -------
        str
            ``string`` rendered in sentence case. Empty string when
            ``string`` contains no word characters.

        Examples
        --------
        >>> String.to_sentence("hello_world")
        'Hello world'
        >>> String.to_sentence("XMLParser")
        'Xml parser'
        """
        parts = String._words(string)
        if not parts:
            return ""

        return " ".join([parts[0].capitalize(), *parts[1:]])

    @staticmethod
    def to_none(
        string: str | None,
        /,
    ) -> str | None:
        """Coerce empty or ``None`` input to ``None``; otherwise return the string unchanged.

        Useful when an upstream producer returns ``""`` to mean "absent"
        and a downstream consumer expects ``None``.

        Parameters
        ----------
        string : str | None
            The input string, or ``None``.

        Returns
        -------
        str | None
            ``None`` if ``string`` is ``None`` or empty; otherwise
            ``string`` unchanged.

        Examples
        --------
        >>> String.to_none("") is None
        True
        >>> String.to_none(None) is None
        True
        >>> String.to_none("hello")
        'hello'
        """
        return string or None
