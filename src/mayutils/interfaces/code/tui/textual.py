"""
Provide reusable building blocks for transparent, ANSI-themed Textual apps.

Bundles the pieces needed to build a Textual application that renders
with the terminal's own ANSI palette and a transparent background, so
the app inherits the user's terminal theme rather than painting its own:
:data:`ANSI_DARK_THEME` maps Textual's theme variables onto ANSI
colours, :data:`TRANSPARENT_CSS` restyles the standard widget set
(inputs, selects, tabs, tables, footer) onto a transparent background,
and :class:`TransparentFooter`/:class:`TransparentFooterKey` rebuild the
footer key hints without the opaque background styling baked into the
stock widgets. :class:`TransparentApp` ties all three together — new
apps subclass it, add their ``compose`` and app-specific ``CSS``, and
get the transparent ANSI look for free.

Note that :class:`TransparentFooter` reimplements ``Footer.compose``
using ``textual.widgets._footer`` internals, so it is coupled to the
Textual version pinned in the ``tui`` extra.

See Also
--------
textual.app.App : Base class extended by :class:`TransparentApp`.
textual.theme.Theme : Type of :data:`ANSI_DARK_THEME`.
textual.widgets.Footer : Stock widget replaced by :class:`TransparentFooter`.
mayutils.interfaces.code.tui.tuiplot : First consumer of these building blocks.

Examples
--------
>>> from mayutils.interfaces.code.tui.textual import ANSI_DARK_THEME
>>> ANSI_DARK_THEME.name
'textual-ansi-dark'
"""

from __future__ import annotations

from collections import defaultdict
from itertools import groupby
from typing import TYPE_CHECKING, Any

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from rich.style import Style
    from rich.text import Text
    from textual.app import App
    from textual.theme import Theme
    from textual.widgets import Footer
    from textual.widgets._footer import (  # pyright: ignore[reportPrivateImportUsage]
        FooterKey,
        FooterLabel,
        KeyGroup,
    )

if TYPE_CHECKING:
    from textual import getters
    from textual.app import ComposeResult
    from textual.binding import Binding


ANSI_DARK_THEME = Theme(
    name="textual-ansi-dark",
    primary="ansi_blue",
    secondary="ansi_cyan",
    warning="ansi_yellow",
    error="ansi_red",
    success="ansi_green",
    accent="ansi_bright_blue",
    foreground="ansi_default",
    background="ansi_default",
    surface="ansi_default",
    panel="ansi_default",
    boost="ansi_default",
    dark=True,
    variables={
        "block-cursor-text-style": "b",
        "block-cursor-blurred-text-style": "i",
        "input-selection-background": "ansi_blue",
        "input-cursor-text-style": "reverse",
        "scrollbar": "ansi_blue",
        "border-blurred": "ansi_blue",
        "border": "ansi_bright_blue",
    },
)
"""Theme mapping Textual's design tokens onto the terminal's ANSI palette."""

TRANSPARENT_CSS = """
Screen {
    background: ansi_default;
    scrollbar-color: $surface-lighten-2;
    scrollbar-color-active: $surface-lighten-3;
    scrollbar-color-hover: $surface-lighten-3;
    scrollbar-background: transparent;
    scrollbar-background-hover: transparent;
    scrollbar-background-active: transparent;
}

Header {
    dock: top;
    height: 1;
    background: ansi_default;
}

HeaderIcon {
    display: none;
}

HeaderTitle {
    background: ansi_default;
}

Footer {
    dock: bottom;
    height: 1;
    background: transparent !important;
    border: none !important;
}

FooterKey {
    background: ansi_default !important;
    border: none !important;
}

.footer-key--key {
    background: ansi_default !important;
    border: none !important;
    color: ansi_red !important;
}

.footer-key--description {
    background: ansi_default !important;
    border: none !important;
}

FooterLabel {
    background: ansi_default !important;
    border: none !important;
}

FooterKey.-command-palette {
    background: ansi_default !important;
    border: none !important;
    dock: left;
}

HorizontalGroup.binding-group {
    background: ansi_default !important;
    border: none !important;
}

VerticalScroll {
    background: transparent;
}

Vertical {
    background: transparent;
}

Horizontal {
    background: transparent;
}

TextArea {
    border: round ansi_white;
    background: transparent;
    padding: 0 1;
}

TextArea > .text-area--active-line {
    background: transparent;
}

TextArea > .text-area--cursor-line {
    background: transparent;
}

TextArea > .text-area--cursor {
    background: ansi_white 40%;
}

Input {
    border: round ansi_white;
    background: transparent;
    padding: 0 1;
    height: 3;
}

Select {
    background: transparent;
}

SelectCurrent {
    background: transparent;
    border: round ansi_blue;
}

SelectOverlay {
    background: transparent;
    border: round ansi_blue;
}

SelectOverlay OptionList {
    background: transparent;
    border: none;
}

Switch {
    height: 1;
    background: transparent;
    border: none;
    padding: 0;
}

Switch .switch--slider {
    color: ansi_red;
}

Switch.-on .switch--slider {
    color: ansi_green;
}

Button {
    background: transparent;
}

TabbedContent {
    background: transparent;
    height: auto;
}

TabPane {
    background: transparent;
    padding: 0;
}

Tabs {
    background: transparent;
}

Tab {
    background: transparent;
}

ContentSwitcher {
    background: transparent;
    height: auto;
}

Label {
    padding: 0 1;
    height: 1;
    color: $text-muted;
    text-style: bold;
    background: transparent;
}

Rule {
    background: transparent;
    color: ansi_green;
}

DataTable {
    background: transparent;
}

DataTable > .datatable--header {
    background: ansi_blue;
    color: ansi_white;
    text-style: bold;
}

DataTable > .datatable--even-row {
    background: transparent;
}

DataTable > .datatable--odd-row {
    background: transparent;
}

DataTable > .datatable--cursor {
    background: ansi_red;
    color: ansi_black;
}

DataTable:focus > .datatable--cursor {
    background: ansi_red;
    color: ansi_black;
}

DataTable > .datatable--header-cursor {
    background: ansi_blue 50%;
}

DataTable > .datatable--header-hover {
    background: ansi_blue 50%;
}

DataTable > .datatable--header-cursor.datatable--header-hover {
    background: transparent;
}

.hidden {
    display: none;
}
"""
"""Stylesheet restyling the standard widget set onto a transparent background."""


class TransparentFooterKey(FooterKey):
    """FooterKey rendered without the stock opaque background."""

    def render(
        self,
    ) -> Text:
        """
        Render the key hint without background styling.

        Returns
        -------
            The assembled key and description text.
        """
        key_style = self.get_component_rich_style("footer-key--key")
        description_style = self.get_component_rich_style("footer-key--description")
        key_style = Style(color=key_style.color, bold=key_style.bold)
        description_style = Style(color=description_style.color)

        key_display = self.key_display
        key_padding = self.get_component_styles("footer-key--key").padding
        description_padding = self.get_component_styles("footer-key--description").padding

        description = self.description
        if description:
            return Text.assemble(
                (
                    " " * key_padding.left + key_display + " " * key_padding.right,
                    key_style,
                ),
                (
                    " " * description_padding.left + description + " " * description_padding.right,
                    description_style,
                ),
            )

        return Text.assemble((key_display, key_style))


class TransparentFooter(Footer):
    """Footer that uses :class:`TransparentFooterKey` for transparent backgrounds."""

    if TYPE_CHECKING:
        # Re-declare with a parameterised App: the base declaration uses a bare
        # `App`, leaving `self.app` as `App[Unknown]` for type checkers.
        app = getters.app(App[object])

    def compose(
        self,
    ) -> ComposeResult:
        """
        Build the footer from the screen's active bindings.

        Yields
        ------
            One :class:`TransparentFooterKey` per visible binding, with
            group labels where bindings are grouped.
        """
        if self._bindings_ready:
            active_bindings = self.screen.active_bindings
            bindings = [(binding, enabled, tooltip) for (_, binding, enabled, tooltip) in active_bindings.values() if binding.show]
            action_to_bindings: defaultdict[str, list[tuple[Binding, bool, str]]] = defaultdict(list)
            for binding, enabled, tooltip in bindings:
                action_to_bindings[binding.action].append((binding, enabled, tooltip))

            self.styles.grid_size_columns = len(action_to_bindings)

            for group, multi_bindings_iterable in groupby(
                action_to_bindings.values(),
                lambda multi_bindings_: multi_bindings_[0][0].group,
            ):
                multi_bindings_list = list(multi_bindings_iterable)
                if group is not None and len(multi_bindings_list) > 1:
                    with KeyGroup(classes="-compact" if group.compact else ""):
                        for multi_bindings in multi_bindings_list:
                            binding, enabled, tooltip = multi_bindings[0]
                            yield TransparentFooterKey(
                                key=binding.key,
                                key_display=self.app.get_key_display(binding=binding),
                                description="",
                                action=binding.action,
                                disabled=not enabled,
                                tooltip=tooltip or binding.description,
                                classes="-grouped",
                            ).data_bind(compact=Footer.compact)
                    yield FooterLabel(group.description)
                else:
                    for multi_bindings in multi_bindings_list:
                        binding, enabled, tooltip = multi_bindings[0]
                        yield TransparentFooterKey(
                            key=binding.key,
                            key_display=self.app.get_key_display(binding=binding),
                            description=binding.description,
                            action=binding.action,
                            disabled=not enabled,
                            tooltip=tooltip,
                        ).data_bind(compact=Footer.compact)

            if self.show_command_palette and self.app.ENABLE_COMMAND_PALETTE:
                try:
                    _node, binding, enabled, tooltip = active_bindings[self.app.COMMAND_PALETTE_BINDING]
                except KeyError:
                    pass
                else:
                    yield TransparentFooterKey(
                        key=binding.key,
                        key_display=self.app.get_key_display(binding=binding),
                        description=binding.description,
                        action=binding.action,
                        classes="-command-palette",
                        disabled=not enabled,
                        tooltip=binding.tooltip or binding.description,
                    )


class TransparentApp[ReturnType](App[ReturnType]):
    """
    Textual app preconfigured for transparent ANSI terminal rendering.

    Subclasses inherit :data:`TRANSPARENT_CSS` (supplied via
    ``DEFAULT_CSS``, so their own ``CSS`` adds to rather than replaces
    it), run with ``ansi_color`` enabled by default, and start on
    :data:`ANSI_DARK_THEME`.
    """

    DEFAULT_CSS = TRANSPARENT_CSS

    def __init__(
        self,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        kwargs.setdefault("ansi_color", True)
        super().__init__(*args, **kwargs)

        self.register_theme(ANSI_DARK_THEME)
        self.theme = ANSI_DARK_THEME.name


__all__ = [
    "ANSI_DARK_THEME",
    "TRANSPARENT_CSS",
    "TransparentApp",
    "TransparentFooter",
    "TransparentFooterKey",
]
