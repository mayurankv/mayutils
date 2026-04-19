"""String case-conversion and empty-value coercion helpers.

This module exposes a single :class:`String` namespace that groups
stateless utilities for normalising arbitrary input strings into a
canonical case style (``snake_case``, ``kebab-case``, ``camelCase``,
``PascalCase``, ``Title Case``, ``Sentence case``) together with a
coercer that maps empty strings and ``None`` onto a uniform ``None``
sentinel.

The converters are intentionally tolerant of mixed input: they accept
any combination of case transitions, whitespace, underscores and
hyphens, infer word boundaries from case and separator changes, and
re-emit the tokens in the requested style. All helpers are exposed as
``@staticmethod`` members so the class itself never needs to be
instantiated; it serves purely as a namespace that keeps the
conversion surface discoverable under a single symbol.

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
    """Namespace of stateless string case-conversion and coercion helpers.

    The class is never instantiated; it exists to group a family of
    related, side-effect-free converters under a single discoverable
    symbol. Every helper is a ``@staticmethod`` taking a single
    positional-only string argument and returning a newly allocated
    string (or ``None`` for :meth:`to_none`).

    Attributes
    ----------
    __slots__ : tuple
        Empty slots declaration preventing per-instance attribute
        allocation, reinforcing that the class is a pure namespace and
        instances carry no state.

    Notes
    -----
    Word boundaries are inferred consistently across all converters
    via :meth:`_words`, which delegates to :meth:`to_snake`. Any
    converter therefore accepts the full range of mixed-case, spaced,
    underscored and hyphenated inputs.
    """

    __slots__ = ()

    @staticmethod
    def _words(
        string: str,
        /,
    ) -> list[str]:
        """Split an input string into lowercase word tokens.

        The function funnels the input through :meth:`to_snake` so that
        case transitions, acronym boundaries, spaces, underscores and
        hyphens are all normalised to underscore-delimited lowercase
        segments, then splits on ``"_"`` and drops empty fragments
        introduced by leading, trailing, or repeated separators.

        Parameters
        ----------
        string : str
            Source text whose word tokens should be extracted. May use
            any mix of case styles and separator characters; empty or
            separator-only inputs are accepted and yield an empty list.

        Returns
        -------
        list[str]
            Ordered sequence of lowercase word tokens as they appear in
            the input, with every separator stripped. Empty when the
            input contains no word characters.

        Notes
        -----
        This is an internal helper used by the ``camel`` / ``pascal`` /
        ``title`` / ``sentence`` converters to obtain a canonical token
        stream prior to re-casing.
        """
        return [word for word in String.to_snake(string).split(sep="_") if word]

    @staticmethod
    def to_snake(
        string: str,
        /,
    ) -> str:
        """Convert an arbitrary input string to ``snake_case``.

        Word boundaries are inferred from three signals: case
        transitions from lowercase to uppercase (``HelloWorld`` becomes
        ``hello world``), a run of uppercase letters followed by an
        uppercase-then-lowercase sequence (``XMLParser`` becomes
        ``XML Parser``), and explicit hyphen separators. The resulting
        tokens are lower-cased and joined with underscores.

        Parameters
        ----------
        string : str
            Source text in any case style. Hyphens are treated as word
            separators; whitespace and existing underscores are
            preserved as separators through the split-and-join pass.

        Returns
        -------
        str
            The input normalised to lowercase words joined by single
            underscore characters. Empty input yields an empty string.

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
        """Convert an arbitrary input string to ``kebab-case``.

        Word boundaries are inferred from lowercase-to-uppercase
        transitions and from acronym-to-word boundaries such as
        ``HTTPResponse``, which is split as ``HTTP Response``. Any run
        of whitespace, underscores or hyphens collapses into a single
        boundary before the tokens are lower-cased and joined with
        hyphens.

        Parameters
        ----------
        string : str
            Source text in any case style. Mixed separators
            (``" "``, ``"_"``, ``"-"``) are all accepted and treated
            uniformly as word boundaries.

        Returns
        -------
        str
            The input normalised to lowercase words joined by single
            hyphen characters. Empty input yields an empty string.

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
        """Convert an arbitrary input string to ``camelCase``.

        Tokens are extracted via :meth:`_words`; the first token is
        emitted lower-cased to match camel-case convention and every
        subsequent token is capitalised, then all tokens are
        concatenated without any separator.

        Parameters
        ----------
        string : str
            Source text in any case style. Inputs containing only
            separators or no word characters are treated as empty.

        Returns
        -------
        str
            The input re-cased so that the leading word is lowercase
            and each following word begins with an uppercase letter,
            with no separators between words. Returns ``""`` when the
            input yields no word tokens.

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
        """Convert an arbitrary input string to ``PascalCase``.

        Every word token extracted by :meth:`_words` is capitalised
        (first character upper, remainder lower) and the tokens are
        concatenated without a separator. Unlike :meth:`to_camel`, the
        leading token is also capitalised.

        Parameters
        ----------
        string : str
            Source text in any case style. Inputs with no word
            characters are treated as empty.

        Returns
        -------
        str
            The input re-cased so that every word begins with an
            uppercase letter and the remaining characters are
            lower-cased, with no separators between words. Returns
            ``""`` when the input yields no word tokens.

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
        """Convert an arbitrary input string to ``Title Case``.

        Every word token extracted by :meth:`_words` is capitalised and
        the tokens are joined by single space characters. The behaviour
        matches :meth:`to_pascal` but substitutes a space separator for
        human-readable output.

        Parameters
        ----------
        string : str
            Source text in any case style. Inputs with no word
            characters are treated as empty.

        Returns
        -------
        str
            The input re-cased so that every word begins with an
            uppercase letter and the words are separated by single
            spaces. Returns ``""`` when the input yields no word
            tokens.

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
        """Convert an arbitrary input string to ``Sentence case``.

        The first word token extracted by :meth:`_words` is capitalised
        to begin the sentence; all remaining tokens are kept as
        produced by :meth:`_words` (already lowercase) and the tokens
        are joined by single space characters.

        Parameters
        ----------
        string : str
            Source text in any case style. Inputs with no word
            characters are treated as empty.

        Returns
        -------
        str
            The input re-cased so that only the leading word is
            capitalised and subsequent words are lowercase, separated
            by single spaces. Returns ``""`` when the input yields no
            word tokens.

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
        """Coerce an empty string or ``None`` to ``None``, leaving other values untouched.

        Bridges APIs where upstream producers emit ``""`` as a marker
        for "absent" while downstream consumers expect the dedicated
        ``None`` sentinel, eliminating ambiguity between an empty
        string and a missing value.

        Parameters
        ----------
        string : str or None
            Candidate value that may be ``None``, an empty string, or
            a non-empty string. Truthiness determines the outcome.

        Returns
        -------
        str or None
            ``None`` when the input is ``None`` or an empty string;
            otherwise the original string reference is returned
            unchanged.

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
