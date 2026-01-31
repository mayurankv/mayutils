import re
from typing import Optional

import mistune
from mistune import Markdown, InlineParser, InlineState
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
    "info": "ℹ️",
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
    "plus": "➕",
    "minus": "➖",
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
    underline_end = re.compile(r"(?:[^\s_])__(?!_)")

    def _parse_underline(
        inline: InlineParser,
        m: re.Match[str],
        state: InlineState,
    ) -> Optional[int]:
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
        _parse_underline,
        before="emphasis",
    )


def plugin_emoji(
    md: Markdown,
) -> None:
    def _parse_emoji(
        inline: InlineParser,
        m: re.Match[str],
        state: InlineState,
    ) -> Optional[int]:
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
        _parse_emoji,
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
    renderer: None = None,
    plugins: list = DEFAULT_PLUGINS,
) -> Markdown:
    return mistune.create_markdown(
        renderer=renderer,
        plugins=plugins,
    )
