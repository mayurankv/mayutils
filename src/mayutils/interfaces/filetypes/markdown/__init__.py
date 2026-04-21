"""Markdown parsing utilities built on top of Mistune.

This module exposes a pre-configured :class:`mistune.Markdown` factory together
with two custom inline plugins. ``plugin_underline`` promotes ``__text__``
spans to an ``underline`` AST node so that double-underscore syntax is not
consumed by Mistune's default bold/emphasis rule, and ``plugin_emoji``
substitutes ``:name:`` shortcodes with Unicode emoji drawn from
:data:`EMOJI_MAP`. Together with the bundled Mistune plugins listed in
:data:`DEFAULT_PLUGINS` (strikethrough, footnotes, task lists, mark,
superscript, subscript), these components give downstream renderers a richer
markdown dialect tailored to the documentation and reporting use cases used
elsewhere in :mod:`mayutils`.
"""

import re
from collections.abc import Iterable

from mayutils.core.extras import may_require_extras

with may_require_extras():
    import mistune
    from mistune import InlineParser, InlineState, Markdown
    from mistune.plugins import Plugin
    from mistune.plugins.footnotes import footnotes
    from mistune.plugins.formatting import (
        mark,
        strikethrough,
        subscript,
        superscript,
    )
    from mistune.plugins.task_lists import task_lists

EMOJI_MAP = {
    "smile": "😊",
    "heart": "❤️",
    "thumbsup": "👍",
    "thumbsdown": "👎",
    "check": "✓",
    "x": "✗",
    "star": "⭐",
    "fire": "🔥",
    "rocket": "🚀",
    "warning": "⚠️",
    "info": "ℹ️",  # noqa: RUF001
    "question": "❓",
    "exclamation": "❗",
    "lightbulb": "💡",
    "chart": "📊",
    "calendar": "📅",
    "clock": "🕐",
    "email": "📧",
    "phone": "📞",
    "link": "🔗",
    "lock": "🔒",
    "unlock": "🔓",
    "key": "🔑",
    "search": "🔍",
    "settings": "⚙️",
    "home": "🏠",
    "user": "👤",
    "users": "👥",
    "folder": "📁",
    "file": "📄",
    "trash": "🗑️",
    "edit": "✏️",
    "save": "💾",
    "download": "⬇️",
    "upload": "⬆️",
    "refresh": "🔄",
    "plus": "➕",  # noqa: RUF001
    "minus": "➖",  # noqa: RUF001
    "arrow_right": "➡️",
    "arrow_left": "⬅️",
    "arrow_up": "⬆️",
    "arrow_down": "⬇️",
    "money": "💰",
    "dollar": "💵",
    "pound": "💷",
    "euro": "💶",
    "chart_up": "📈",
    "chart_down": "📉",
    "target": "🎯",
    "trophy": "🏆",
    "medal": "🏅",
    "checkmark": "✅",
    "crossmark": "❌",
    "hourglass": "⏳",
    "bell": "🔔",
    "pin": "📌",
    "bookmark": "🔖",
    "tag": "🏷️",
    "gift": "🎁",
    "party": "🎉",
    "clap": "👏",
    "muscle": "💪",
    "brain": "🧠",
    "eye": "👁️",
    "hand": "✋",
    "point_right": "👉",
    "point_left": "👈",
    "ok": "👌",
    "wave": "👋",
    "pray": "🙏",
    "think": "🤔",
    "shrug": "🤷",
    "facepalm": "🤦",
    "laugh": "😂",
    "cry": "😢",
    "angry": "😠",
    "cool": "😎",
    "surprised": "😮",
    "worried": "😟",
    "confused": "😕",
    "neutral": "😐",
    "sleeping": "😴",
    "sick": "🤒",
    "mask": "😷",
    "sun": "☀️",
    "moon": "🌙",
    "cloud": "☁️",
    "rain": "🌧️",
    "snow": "❄️",
    "umbrella": "☂️",
    "rainbow": "🌈",
    "tree": "🌳",
    "flower": "🌸",
    "earth": "🌍",
    "mountain": "⛰️",
    "beach": "🏖️",
    "city": "🏙️",
    "car": "🚗",
    "plane": "✈️",
    "train": "🚆",
    "ship": "🚢",
    "bike": "🚲",
    "coffee": "☕",
    "pizza": "🍕",
    "burger": "🍔",
    "cake": "🎂",
    "beer": "🍺",
    "wine": "🍷",
    "apple": "🍎",
    "banana": "🍌",
    "cat": "🐱",
    "dog": "🐕",
    "bird": "🐦",
    "fish": "🐟",
    "bug": "🐛",
    "butterfly": "🦋",
}


def plugin_underline(
    md: Markdown,
) -> None:
    """Register an inline ``underline`` rule on a Mistune parser.

    The plugin installs a custom inline handler that matches
    ``__text__`` spans and emits an ``underline`` AST token whose children
    are the fully parsed inline contents of ``text``. The rule is inserted
    ahead of Mistune's built-in ``emphasis`` rule so that double-underscore
    sequences are not consumed as bold before the underline rule can see
    them.

    Parameters
    ----------
    md : mistune.Markdown
        Parser instance whose inline lexer should be extended. The plugin
        calls :meth:`md.inline.register` in-place and does not otherwise
        mutate ``md``.

    Returns
    -------
    None
        The function operates by side effect on ``md``.

    Notes
    -----
    The closing ``__`` must be preceded by a non-whitespace, non-underscore
    character and must not be immediately followed by another ``_``; this
    mirrors CommonMark's flanking rules and prevents greedy matches across
    paragraph boundaries.
    """
    underline_end = re.compile(r"(?:[^\s_])__(?!_)")

    def parse_underline(
        inline: InlineParser,
        m: re.Match[str],
        state: InlineState,
    ) -> int | None:
        r"""Consume an opening ``__`` and emit an ``underline`` AST node.

        Scans forward from the match end for the closing ``__`` delimiter,
        recursively renders the enclosed inline content, and appends a
        token of type ``underline`` to ``state``.

        Parameters
        ----------
        inline : mistune.InlineParser
            Active inline parser used to recursively tokenise the span's
            contents so that nested emphasis, code, links, etc. are
            preserved inside the underline node.
        m : re.Match[str]
            Match object produced by the opening ``__(?=[^\\s_])`` pattern;
            its ``end()`` marks the first character of the span body.
        state : mistune.InlineState
            Current inline parsing state. Tokens are appended to this
            state's token list, and ``state.src`` is searched for the
            closing delimiter.

        Returns
        -------
        int or None
            Position in ``state.src`` immediately after the closing ``__``
            when a well-formed span is found, signalling how far the outer
            lexer should advance. ``None`` is returned when no closing
            delimiter is located, causing Mistune to fall back to the next
            inline rule.
        """
        pos = m.end()
        m1 = underline_end.search(state.src, pos)
        if not m1:
            return None

        end_pos = m1.end()
        text = state.src[pos : end_pos - 2]

        new_state = state.copy()
        new_state.src = text
        children = inline.render(new_state)

        state.append_token(
            {
                "type": "underline",
                "children": children,
            }
        )

        return end_pos

    md.inline.register(
        "underline",
        r"__(?=[^\s_])",
        parse_underline,
        before="emphasis",
    )


def plugin_emoji(
    md: Markdown,
) -> None:
    """Register an inline ``emoji`` rule that expands ``:name:`` shortcodes.

    The plugin matches lower-case shortcodes of the form ``:name:`` and
    replaces them with the corresponding Unicode glyph from
    :data:`EMOJI_MAP`. Shortcodes whose ``name`` is not present in the map
    are emitted verbatim (including the surrounding colons) so unrelated
    text such as ``:foo:bar:`` is not silently stripped. The rule is
    registered before ``emphasis`` so that colon-delimited shortcodes are
    resolved before emphasis processing could otherwise interfere.

    Parameters
    ----------
    md : mistune.Markdown
        Parser instance whose inline lexer should be extended. The plugin
        calls :meth:`md.inline.register` in-place and does not otherwise
        mutate ``md``.

    Returns
    -------
    None
        The function operates by side effect on ``md``.
    """

    def parse_emoji(
        inline: InlineParser,  # noqa: ARG001
        m: re.Match[str],
        state: InlineState,
    ) -> int | None:
        """Emit a text token containing the emoji for a ``:name:`` shortcode.

        Looks up the captured ``name`` in :data:`EMOJI_MAP` and appends a
        ``text`` token whose ``raw`` value is either the resolved Unicode
        character or, when the name is unknown, the original
        ``:name:`` string so the source is preserved in the rendered
        output.

        Parameters
        ----------
        inline : mistune.InlineParser
            Active inline parser. Kept for signature compatibility with
            Mistune's inline rule interface; no recursive parsing is
            performed because the replacement is a literal string.
        m : re.Match[str]
            Match object produced by the ``:([a-z_]+):`` pattern. Group 1
            is the shortcode name used as the lookup key.
        state : mistune.InlineState
            Current inline parsing state; the emoji token is appended to
            its token list.

        Returns
        -------
        int
            Position in ``state.src`` immediately after the closing colon
            of the shortcode, telling the outer lexer where to resume.
        """
        pos = m.end()

        emoji_name = m.group(1)
        emoji_char = EMOJI_MAP.get(
            emoji_name,
            f":{emoji_name}:",
        )

        state.append_token(
            {
                "type": "text",
                "raw": emoji_char,
            }
        )

        return pos

    md.inline.register(
        "emoji",
        r":([a-z_]+):",
        parse_emoji,
        before="emphasis",
    )


DEFAULT_PLUGINS = [
    strikethrough,
    footnotes,
    task_lists,
    mark,
    superscript,
    subscript,
    plugin_underline,
    plugin_emoji,
]


def create_markdown_parser(
    *,
    renderer: None = None,
    plugins: Iterable[str | Plugin] | None = DEFAULT_PLUGINS,
) -> Markdown:
    """Build a :class:`mistune.Markdown` parser with the project defaults.

    Wraps :func:`mistune.create_markdown` so callers receive a parser that
    already understands the extended markdown dialect used across
    :mod:`mayutils` — strikethrough, footnotes, GFM task lists, highlight
    (``==mark==``), superscript, subscript, underline (``__text__``) and
    ``:emoji:`` shortcodes.

    Parameters
    ----------
    renderer : None, optional
        Renderer forwarded to :func:`mistune.create_markdown`. Passing
        ``None`` (the default) selects Mistune's built-in HTML renderer;
        supply an alternative object to emit AST, plain text, or any other
        format. Typed as ``None`` here because the call sites in this
        module rely on the default HTML output.
    plugins : list, optional
        Ordered collection of Mistune plugin callables to install on the
        parser. Each entry must accept a :class:`mistune.Markdown` and
        mutate it in place. Defaults to :data:`DEFAULT_PLUGINS`, which
        bundles the six Mistune-shipped plugins along with the
        :func:`plugin_underline` and :func:`plugin_emoji` helpers defined
        in this module.

    Returns
    -------
    mistune.Markdown
        A fully configured parser whose ``__call__`` converts a markdown
        source string into the renderer's output type (HTML by default).
    """
    return mistune.create_markdown(
        renderer=renderer,
        plugins=plugins,
    )
