"""Tests for ``mayutils.export.html``."""

from __future__ import annotations

from mayutils.export.html import html_pill, markdown_to_html


class TestMarkdownToHtml:
    """Tests for :func:`markdown_to_html` — render Markdown while preserving newlines."""

    def test_headings(self) -> None:
        """A Markdown heading is rewritten to the matching ``<h1>`` element."""
        result = markdown_to_html("# Hello")
        assert "<h1>Hello</h1>" in result

    def test_emphasis(self) -> None:
        """Asterisks promote to the ``<em>`` element."""
        result = markdown_to_html("This is *emphasis*.")
        assert "<em>emphasis</em>" in result

    def test_literal_newlines_become_br(self) -> None:
        """Stray newlines in the HTML are replaced with ``<br>`` tags."""
        result = markdown_to_html("line1\n\nline2")
        assert "\n" not in result


class TestHtmlPill:
    """Tests for :func:`html_pill` — build an inline pill-styled ``<span>``."""

    def test_embeds_text(self) -> None:
        """The supplied text appears inside the returned span."""
        result = html_pill("READY", background_colour="#00ff00")
        assert ">READY<" in result

    def test_is_span_element(self) -> None:
        """The returned markup is a single ``<span>`` element."""
        result = html_pill("x", background_colour="red")
        assert result.startswith("<span")
        assert result.endswith("</span>")

    def test_applies_background_colour(self) -> None:
        """The background colour is embedded as an inline style declaration."""
        result = html_pill("x", background_colour="#123456")
        assert "background-color: #123456" in result

    def test_default_is_bold(self) -> None:
        """``bold=True`` (default) produces ``font-weight: bold``."""
        result = html_pill("x", background_colour="red")
        assert "font-weight: bold" in result

    def test_bold_false_is_normal(self) -> None:
        """``bold=False`` produces ``font-weight: normal``."""
        result = html_pill("x", background_colour="red", bold=False)
        assert "font-weight: normal" in result

    def test_padding_and_rounding_included(self) -> None:
        """Caller-supplied padding and rounding appear in the inline style."""
        result = html_pill(
            "x",
            background_colour="red",
            padding=(1.0, 2.0),
            rounding=3.25,
        )
        assert "padding: 1.0em 2.0em" in result
        assert "border-radius: 3.25em" in result

    def test_custom_text_colour_and_font_size(self) -> None:
        """Text colour and relative font size propagate into the span style."""
        result = html_pill(
            "x",
            background_colour="red",
            text_colour="white",
            relative_font_size=0.75,
        )
        assert "color: white" in result
        assert "font-size: 0.75em" in result
