"""
Provide string case-conversion and empty-value coercion helpers.

This module exposes a single :class:`String` namespace that groups stateless
utilities for normalising arbitrary input strings into a canonical case style
(``snake_case``, ``kebab-case``, ``camelCase``, ``PascalCase``, ``Title Case``,
``Sentence case``) together with a coercer that maps empty strings and
``None`` onto a uniform ``None`` sentinel. The converters are intentionally
tolerant of mixed input: they accept any combination of case transitions,
whitespace, underscores and hyphens, infer word boundaries from case and
separator changes, and re-emit the tokens in the requested style. Every
helper is exposed as a ``@staticmethod`` so the class itself never needs to
be instantiated; it serves purely as a namespace that keeps the conversion
surface discoverable under a single symbol.

See Also
--------
re.sub : Regular expression substitution used internally to inject word
    boundaries before splitting.
str.split : Whitespace-aware splitter applied after the boundary-injecting
    regular expression substitutions.
str.capitalize : Standard library title-casing used to re-case individual
    word tokens back into the requested style.
string : Standard library module with additional ASCII character constants
    occasionally useful alongside these helpers.
textwrap : Standard library module for wrapping or dedenting strings after
    case normalisation.
unicodedata : Standard library module for performing Unicode normalisation
    of inputs prior to passing through these helpers.

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
    """
    Group stateless string case-conversion and coercion helpers as a namespace.

    The class is never instantiated; it exists to group a family of related,
    side-effect-free converters under a single discoverable symbol. Every
    helper is a ``@staticmethod`` taking a single positional-only string
    argument and returning a newly allocated string (or ``None`` for
    :meth:`to_none`). Word boundaries are inferred consistently across all
    converters via :meth:`_words`, which delegates to :meth:`to_snake`, so
    every converter accepts the full range of mixed-case, spaced, underscored
    and hyphenated inputs. The empty ``__slots__`` declaration prevents
    per-instance attribute allocation, reinforcing the namespace-only role.

    Attributes
    ----------
    __slots__
        Empty slots declaration preventing per-instance attribute
        allocation, reinforcing that the class is a pure namespace and
        instances carry no state.

    See Also
    --------
    re.sub : Regular expression substitution used by the case converters to
        inject word boundaries around case transitions.
    str.capitalize : Standard library helper used by the word-token
        re-casers.
    string : Standard library module with ASCII character constants useful
        alongside this namespace.
    textwrap : Standard library module for further post-processing the
        output of these converters.
    unicodedata : Standard library module for Unicode normalisation that
        complements the ASCII-focused transformations here.

    Examples
    --------
    >>> String.to_snake("HelloWorld")
    'hello_world'
    >>> String.to_kebab("HTTPResponse")
    'http-response'
    >>> String.to_pascal("hello_world")
    'HelloWorld'
    """

    __slots__ = ()

    @staticmethod
    def _words(
        string: str,
        /,
    ) -> list[str]:
        """
        Split an input string into lowercase word tokens.

        The function funnels the input through :meth:`to_snake` so that case
        transitions, acronym boundaries, spaces, underscores and hyphens are
        all normalised to underscore-delimited lowercase segments. It then
        splits on ``"_"`` and drops empty fragments introduced by leading,
        trailing, or repeated separators. This is an internal helper used by
        the ``camel`` / ``pascal`` / ``title`` / ``sentence`` converters to
        obtain a canonical token stream prior to re-casing.

        Parameters
        ----------
        string
            Source text whose word tokens should be extracted. May use any
            mix of case styles and separator characters; empty or
            separator-only inputs are accepted and yield an empty list.

        Returns
        -------
            Ordered sequence of lowercase word tokens as they appear in the
            input, with every separator stripped. Empty when the input
            contains no word characters.

        See Also
        --------
        String.to_snake : Underlying converter that performs the initial
            normalisation into underscore-delimited lowercase tokens.
        String.to_camel : Downstream consumer that re-cases the tokens
            produced here into ``camelCase``.
        String.to_pascal : Downstream consumer that re-cases the tokens
            produced here into ``PascalCase``.
        re.sub : Regular expression substitution used indirectly via
            :meth:`to_snake` to inject word boundaries.
        str.split : Standard library splitter used to fragment the snake
            form on underscore separators.

        Examples
        --------
        >>> String._words("HelloWorld")
        ['hello', 'world']
        >>> String._words("__mixed--Case__")
        ['mixed', 'case']
        >>> String._words("")
        []
        """
        return [word for word in String.to_snake(string).split(sep="_") if word]

    @staticmethod
    def to_snake(
        string: str,
        /,
    ) -> str:
        """
        Convert an arbitrary input string to ``snake_case``.

        Word boundaries are inferred from three signals: case transitions
        from lowercase to uppercase (``HelloWorld`` becomes ``hello world``),
        a run of uppercase letters followed by an uppercase-then-lowercase
        sequence (``XMLParser`` becomes ``XML Parser``), and explicit hyphen
        separators. The resulting tokens are lower-cased and joined with
        underscores. Two successive regular expression passes inject spaces
        around the detected boundaries before :meth:`str.split` collapses
        any run of whitespace and the final :meth:`str.lower` normalises the
        case uniformly.

        Parameters
        ----------
        string
            Source text in any case style. Hyphens are treated as word
            separators; whitespace and existing underscores are preserved as
            separators through the split-and-join pass.

        Returns
        -------
            The input normalised to lowercase words joined by single
            underscore characters. Empty input yields an empty string.

        See Also
        --------
        String.to_kebab : Sibling converter that produces hyphen-separated
            lowercase output from the same boundary inference.
        String.to_camel : Sibling converter that consumes the tokens
            produced by :meth:`_words` to build ``camelCase``.
        String.to_pascal : Sibling converter that builds ``PascalCase`` from
            the same token stream.
        re.sub : Regular expression substitution used to inject spaces at
            detected word boundaries.
        str.lower : Standard library method used for the final
            case-normalisation pass.

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
        """
        Convert an arbitrary input string to ``kebab-case``.

        Word boundaries are inferred from lowercase-to-uppercase transitions
        and from acronym-to-word boundaries such as ``HTTPResponse``, which
        is split as ``HTTP Response``. Any run of whitespace, underscores or
        hyphens collapses into a single boundary before the tokens are
        lower-cased and joined with hyphens. The implementation uses two
        regular expression passes to inject spaces at case boundaries, then
        a third pass to unify the separator set before the final join.

        Parameters
        ----------
        string
            Source text in any case style. Mixed separators
            (``" "``, ``"_"``, ``"-"``) are all accepted and treated
            uniformly as word boundaries.

        Returns
        -------
            The input normalised to lowercase words joined by single hyphen
            characters. Empty input yields an empty string.

        See Also
        --------
        String.to_snake : Sibling converter producing underscore-separated
            output from the same boundary inference.
        String.to_title : Sibling converter producing space-separated
            Title-Case output from the same token stream.
        re.sub : Regular expression substitution used to inject spaces at
            detected word boundaries.
        str.strip : Standard library method used to drop leading and
            trailing whitespace prior to the final join.
        str.lower : Standard library method used for the final
            case-normalisation pass.

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
        """
        Convert an arbitrary input string to ``camelCase``.

        Tokens are extracted via :meth:`_words`; the first token is emitted
        lower-cased to match camel-case convention and every subsequent
        token is capitalised, then all tokens are concatenated without any
        separator. Callers should note that :meth:`str.capitalize` keeps
        only the leading character in uppercase, so ``XMLParser`` is first
        snake-cased to ``xml_parser`` and then re-assembled as
        ``xmlParser`` rather than preserving the acronym.

        Parameters
        ----------
        string
            Source text in any case style. Inputs containing only separators
            or no word characters are treated as empty.

        Returns
        -------
            The input re-cased so that the leading word is lowercase and
            each following word begins with an uppercase letter, with no
            separators between words. Returns ``""`` when the input yields
            no word tokens.

        See Also
        --------
        String.to_pascal : Sibling converter that also capitalises the
            leading word for PascalCase output.
        String.to_snake : Sibling converter whose tokenisation this helper
            indirectly relies on via :meth:`_words`.
        String._words : Internal tokeniser that produces the canonical
            lowercase word stream consumed here.
        str.capitalize : Standard library method applied to each non-leading
            token.
        re.sub : Regular expression substitution used upstream in
            :meth:`to_snake` to split on case transitions.

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
        """
        Convert an arbitrary input string to ``PascalCase``.

        Every word token extracted by :meth:`_words` is capitalised (first
        character upper, remainder lower) and the tokens are concatenated
        without a separator. Unlike :meth:`to_camel`, the leading token is
        also capitalised, producing the upper-camel variant frequently used
        for class names. Acronyms in the source are folded to their
        capitalised-only form because the tokenisation pass lower-cases
        every character before re-casing.

        Parameters
        ----------
        string
            Source text in any case style. Inputs with no word characters
            are treated as empty.

        Returns
        -------
            The input re-cased so that every word begins with an uppercase
            letter and the remaining characters are lower-cased, with no
            separators between words. Returns ``""`` when the input yields
            no word tokens.

        See Also
        --------
        String.to_camel : Sibling converter producing ``camelCase`` by
            leaving the leading token lower-cased.
        String.to_title : Sibling converter that emits the same capitalised
            tokens separated by single spaces.
        String._words : Internal tokeniser that produces the canonical
            lowercase word stream consumed here.
        str.capitalize : Standard library method applied to each token.
        re.sub : Regular expression substitution used upstream to split on
            case transitions.

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
        """
        Convert an arbitrary input string to ``Title Case``.

        Every word token extracted by :meth:`_words` is capitalised and the
        tokens are joined by single space characters. The behaviour matches
        :meth:`to_pascal` but substitutes a space separator for
        human-readable output. As with the other re-casers, acronym input
        is not preserved: ``XMLParser`` is first normalised to two lowercase
        tokens before :meth:`str.capitalize` restores only the leading
        letter of each.

        Parameters
        ----------
        string
            Source text in any case style. Inputs with no word characters
            are treated as empty.

        Returns
        -------
            The input re-cased so that every word begins with an uppercase
            letter and the words are separated by single spaces. Returns
            ``""`` when the input yields no word tokens.

        See Also
        --------
        String.to_sentence : Sibling converter that capitalises only the
            leading word rather than every word.
        String.to_pascal : Sibling converter that emits the same
            capitalised tokens without any separator.
        String._words : Internal tokeniser that produces the canonical
            lowercase word stream consumed here.
        str.capitalize : Standard library method applied to each token.
        re.sub : Regular expression substitution used upstream to split on
            case transitions.

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
        """
        Convert an arbitrary input string to ``Sentence case``.

        The first word token extracted by :meth:`_words` is capitalised to
        begin the sentence; all remaining tokens are kept as produced by
        :meth:`_words` (already lowercase) and the tokens are joined by
        single space characters. No trailing punctuation is appended, so the
        caller is responsible for any sentence-terminating characters their
        downstream formatting requires.

        Parameters
        ----------
        string
            Source text in any case style. Inputs with no word characters
            are treated as empty.

        Returns
        -------
            The input re-cased so that only the leading word is capitalised
            and subsequent words are lowercase, separated by single spaces.
            Returns ``""`` when the input yields no word tokens.

        See Also
        --------
        String.to_title : Sibling converter that capitalises every word
            rather than just the leading word.
        String.to_camel : Sibling converter that also lower-cases everything
            after the leading token but joins without separators.
        String._words : Internal tokeniser that produces the canonical
            lowercase word stream consumed here.
        str.capitalize : Standard library method applied to the leading
            token.
        re.sub : Regular expression substitution used upstream to split on
            case transitions.

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
    def to_slug(
        string: str,
        /,
        *,
        max_length: int | None = None,
    ) -> str:
        """
        Convert an arbitrary input string to a filesystem-safe slug.

        Replaces every non-alphanumeric character with an underscore,
        collapses runs of underscores, strips leading and trailing
        underscores, and truncates to *max_length* without leaving a
        trailing underscore.

        Parameters
        ----------
        string
            Source text in any format.
        max_length
            Maximum character count for the returned slug.

        Returns
        -------
            Lowercased string containing only ``[a-z0-9_]``.

        See Also
        --------
        String.to_snake : Sibling converter that infers word boundaries
            from case transitions rather than replacing all non-alphanum.

        Examples
        --------
        >>> String.to_slug("SELECT * FROM loans")
        'select_from_loans'
        >>> String.to_slug("a///b///c")
        'a_b_c'
        >>> String.to_slug("  --hello--  ")
        'hello'
        """
        slug = sub(r"[^a-z0-9]+", "_", string.lower()).strip("_")
        slug = sub(r"_+", "_", slug)
        if max_length is not None:
            slug = slug[:max_length]

        return slug.rstrip("_")

    @staticmethod
    def to_none(
        string: str | None,
        /,
    ) -> str | None:
        """
        Coerce an empty string or ``None`` to ``None``, preserving other values.

        Bridge APIs where upstream producers emit ``""`` as a marker for
        "absent" while downstream consumers expect the dedicated ``None``
        sentinel, eliminating ambiguity between an empty string and a
        missing value. The implementation relies on Python truthiness: any
        falsy input (``None`` or ``""``) is folded to ``None`` and any
        truthy string is returned unchanged by reference. Whitespace-only
        inputs are considered truthy and therefore pass through untouched.

        Parameters
        ----------
        string
            Candidate value that may be ``None``, an empty string, or a
            non-empty string. Truthiness determines the outcome.

        Returns
        -------
            ``None`` when the input is ``None`` or an empty string;
            otherwise the original string reference is returned unchanged.

        See Also
        --------
        String.to_snake : Sibling converter for normalising case rather
            than emptiness.
        String.to_kebab : Sibling converter for normalising case rather
            than emptiness.
        str : Built-in string type whose truthiness rule drives the
            coercion.
        re.sub : Regular expression substitution commonly paired with this
            helper when cleaning up optional text fields.

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
